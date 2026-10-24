import logging
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import signing
from django.core.mail import send_mail
from django.db import transaction
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from accounts.identity import canonical_email
from billing.access import get_access
from billing.models import Subscription, SubscriptionEvent
from billing.payments import PaymentError, get_provider
from billing.services import InvalidTransition

from .models import LegalAcceptance, LegalDocument, ServiceRequest

User = get_user_model()
logger = logging.getLogger(__name__)

# Withdrawal term: 10 calendar days from the contract (Ley 24.240 art. 34, CCyC art. 1110).
WITHDRAWAL_DAYS = 10
CONFIRM_MAX_AGE = timedelta(days=3)
CONFIRM_SALT = "legal.service_request"
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def record_signup_documents(user, terms, privacy):
    """Evidence for a new account, saved in the same transaction as the account."""
    if terms is not None:
        LegalAcceptance.objects.create(
            user=user,
            document=terms,
            action=LegalAcceptance.ACCEPTED,
            context=LegalAcceptance.SIGNUP,
        )
    if privacy is not None:
        LegalAcceptance.objects.create(
            user=user,
            document=privacy,
            action=LegalAcceptance.INFORMED,
            context=LegalAcceptance.SIGNUP,
        )


def pending_terms(user):
    """The terms version `user` still has to accept, or None."""
    terms = LegalDocument.current(LegalDocument.TERMS)
    if terms is None:
        return None
    accepted = LegalAcceptance.objects.filter(
        user=user, document=terms, action=LegalAcceptance.ACCEPTED
    ).exists()
    return None if accepted else terms


def accept_terms(user, terms):
    LegalAcceptance.objects.get_or_create(
        user=user,
        document=terms,
        action=LegalAcceptance.ACCEPTED,
        defaults={"context": LegalAcceptance.REACCEPTANCE},
    )


def new_code():
    return "TF-" + "".join(secrets.choice(CODE_ALPHABET) for _ in range(8))


def find_business(email):
    user = User.objects.filter(email_canonical=canonical_email(email)).first()
    return getattr(user, "business", None) if user else None


def create_request(kind, email):
    email = email.strip().lower()
    for _ in range(5):
        code = new_code()
        if not ServiceRequest.objects.filter(code=code).exists():
            break
    return ServiceRequest.objects.create(
        kind=kind, code=code, email=email, business=find_business(email)
    )


def confirm_token(service_request):
    return signing.dumps({"r": service_request.pk, "c": service_request.code}, salt=CONFIRM_SALT)


def read_confirm_token(token):
    try:
        payload = signing.loads(token, salt=CONFIRM_SALT, max_age=CONFIRM_MAX_AGE.total_seconds())
    except signing.BadSignature:
        return None
    return ServiceRequest.objects.filter(pk=payload.get("r"), code=payload.get("c")).first()


def send_legal_email(subject, template, recipient, context):
    try:
        send_mail(
            subject=" ".join(subject.split()),
            message=render_to_string(template, context),
            from_email=None,
            recipient_list=[recipient],
        )
    except Exception:
        logger.exception("Could not send legal email (%s)", template)
        return False
    return True


def send_request_received(request, service_request):
    """The identification code, by the same channel, at once (the rule allows 24 hours)."""
    confirm_url = None
    if service_request.business is not None:
        confirm_url = request.build_absolute_uri(
            reverse("service_request_confirm", args=[confirm_token(service_request)])
        )
    return send_legal_email(
        f"{service_request.get_kind_display()}: código {service_request.code}",
        "legal/emails/request_received.txt",
        service_request.email,
        {"service_request": service_request, "confirm_url": confirm_url},
    )


def contracted_at(subscription):
    """When the current paid period of `subscription` began, or None if it never paid."""
    event = (
        SubscriptionEvent.objects.filter(subscription=subscription, to_status=Subscription.ACTIVE)
        .exclude(from_status__in=[Subscription.ACTIVE, Subscription.PAST_DUE])
        .order_by("-created_at", "-pk")
        .first()
    )
    return event.created_at if event else None


def stop_renewal(subscription):
    """Stop the recurring charge. Returns the outcome to record."""
    if subscription is None:
        return ServiceRequest.NOTHING_TO_CHARGE
    if subscription.renews_automatically:
        try:
            get_provider().cancel(subscription)
        except (InvalidTransition, PaymentError):
            logger.exception("Could not cancel subscription %s from a request", subscription.pk)
            return ServiceRequest.MANUAL_REVIEW
        return ServiceRequest.RENEWAL_STOPPED
    if subscription.status in (Subscription.ACTIVE, Subscription.PAST_DUE):
        # Paid by arrangement (no provider charge to stop): the operator ends it.
        return ServiceRequest.MANUAL_REVIEW
    return ServiceRequest.NOTHING_TO_CHARGE


def withdrawal_outcome(service_request, subscription):
    started = contracted_at(subscription) if subscription else None
    if started is None:
        return stop_renewal(subscription)
    # The right is exercised when the request is made, not when the email is confirmed.
    if service_request.created_at - started > timedelta(days=WITHDRAWAL_DAYS):
        stopped = stop_renewal(subscription)
        return ServiceRequest.OUT_OF_TERM if stopped != ServiceRequest.MANUAL_REVIEW else stopped
    stop_renewal(subscription)
    return ServiceRequest.REFUND_DUE


def confirm_request(service_request, now=None):
    """Apply a request once its mailbox confirmed it. Repeating it changes nothing."""
    now = now or timezone.now()
    with transaction.atomic():
        service_request = ServiceRequest.objects.select_for_update().get(pk=service_request.pk)
        if service_request.confirmed_at is not None:
            return service_request, False
        business = service_request.business
        subscription = get_access(business).subscription if business else None
        if service_request.kind == ServiceRequest.WITHDRAWAL:
            outcome = withdrawal_outcome(service_request, subscription)
        else:
            outcome = stop_renewal(subscription)
        service_request.confirmed_at = now
        service_request.outcome = outcome
        service_request.save(update_fields=["confirmed_at", "outcome"])
    return service_request, True


def send_request_done(service_request):
    """Written record of the cancellation (Ley 24.240 art. 10 ter) and, if needed, the operator."""
    subscription = None
    if service_request.business is not None:
        subscription = get_access(service_request.business).subscription
    context = {
        "service_request": service_request,
        "subscription": subscription,
        "contact_email": settings.LEGAL_CONTACT_EMAIL or settings.BILLING_CONTACT_EMAIL,
    }
    send_legal_email(
        f"Constancia {service_request.code}: {service_request.get_kind_display()}",
        "legal/emails/request_done.txt",
        service_request.email,
        context,
    )
    operator = settings.BILLING_CONTACT_EMAIL or settings.LEGAL_CONTACT_EMAIL
    if service_request.needs_operator and operator:
        send_legal_email(
            f"Revisar solicitud {service_request.code}",
            "legal/emails/operator_notice.txt",
            operator,
            context,
        )
