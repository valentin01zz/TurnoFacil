from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render

from accounts import throttle

from .forms import AcceptTermsForm, ServiceRequestForm
from .models import LegalDocument, ServiceRequest
from .services import (
    accept_terms,
    confirm_request,
    create_request,
    pending_terms,
    read_confirm_token,
    send_request_done,
    send_request_received,
)
from .text import render_document


def render_legal_document(request, document):
    versions = LegalDocument.objects.filter(
        kind=document.kind, effective_at__lte=document.effective_at
    )
    return render(
        request,
        "legal/document.html",
        {
            "document": document,
            "body": render_document(document.body),
            "is_current": document == LegalDocument.current(document.kind),
            "other_versions": versions.exclude(pk=document.pk),
        },
    )


def legal_document(request, kind):
    document = LegalDocument.current(kind)
    if document is None:
        raise Http404("Not published yet")
    return render_legal_document(request, document)


def legal_document_version(request, kind, version):
    return render_legal_document(
        request, get_object_or_404(LegalDocument, kind=kind, version=version)
    )


def contact(request):
    if not settings.LEGAL_CONTACT_EMAIL:
        raise Http404("Contact details not configured")
    return render(request, "legal/contact.html", {"owner": owner_details()})


def owner_details():
    return {
        "name": settings.LEGAL_OWNER_NAME,
        "tax_id": settings.LEGAL_OWNER_TAX_ID,
        "address": settings.LEGAL_OWNER_ADDRESS,
        "email": settings.LEGAL_CONTACT_EMAIL,
        "privacy_email": settings.LEGAL_PRIVACY_EMAIL or settings.LEGAL_CONTACT_EMAIL,
        "phone": settings.LEGAL_CONTACT_PHONE,
        "hours": settings.LEGAL_SUPPORT_HOURS,
    }


def service_request(request, kind):
    """Public cancellation and withdrawal buttons: no login, no prior registration."""
    form = ServiceRequestForm(request.POST if request.method == "POST" else None)
    context = {"form": form, "kind": kind, "is_withdrawal": kind == ServiceRequest.WITHDRAWAL}
    if request.method == "POST":
        ip = throttle.client_ip(request)
        if throttle.is_limited("service_request_ip", ip):
            form.is_valid()
            form.add_error(
                None, "Recibimos muchas solicitudes desde tu conexión. Probá en una hora."
            )
            return render(request, "legal/service_request.html", context, status=429)
        if form.is_valid():
            throttle.record("service_request_ip", ip)
            created = create_request(kind, form.cleaned_data["email"])
            send_request_received(request, created)
            # The same answer whether or not the email has an account.
            return render(request, "legal/service_request_sent.html", {"service_request": created})
    return render(request, "legal/service_request.html", context)


def service_request_confirm(request, token):
    found = read_confirm_token(token)
    if found is None:
        return render(request, "legal/service_request_invalid.html", status=400)
    if request.method == "POST":
        found, applied = confirm_request(found)
        if applied:
            send_request_done(found)
        return render(request, "legal/service_request_done.html", {"service_request": found})
    if found.confirmed_at is not None:
        return render(request, "legal/service_request_done.html", {"service_request": found})
    # A button, not the link itself, applies it: mail scanners open links on their own.
    return render(request, "legal/service_request_confirm.html", {"service_request": found})


@login_required
def accept_new_terms(request):
    terms = pending_terms(request.user)
    if terms is None:
        return redirect("panel")
    form = AcceptTermsForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        accept_terms(request.user, terms)
        return redirect("panel")
    return render(request, "legal/accept_terms.html", {"form": form, "terms": terms})
