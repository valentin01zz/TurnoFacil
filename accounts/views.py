from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from .forms import SignupForm
from .verification import can_resend, read_token, send_verification, verify

User = get_user_model()


def home(request):
    if request.user.is_authenticated:
        return redirect("panel")
    return render(request, "home.html")


def signup(request):
    if request.user.is_authenticated:
        return redirect("panel")
    form = SignupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        send_verification(request, user)
        return redirect("verify_email_pending")
    return render(request, "accounts/signup.html", {"form": form})


@login_required
def verify_email_pending(request):
    if request.user.is_email_verified:
        return redirect("panel")
    return render(request, "accounts/verify_pending.html")


@login_required
@require_POST
def resend_verification(request):
    user = request.user
    if user.is_email_verified:
        return redirect("panel")
    if not can_resend(user):
        messages.warning(request, "Ya te mandamos un link hace un momento. Esperá un minuto.")
    elif send_verification(request, user):
        messages.success(request, f"Te mandamos un link nuevo a {user.email}.")
    else:
        messages.warning(request, "No pudimos enviar el email. Probá de nuevo en unos minutos.")
    return redirect("verify_email_pending")


def verify_email(request, token):
    payload = read_token(token)
    user = None
    if payload:
        user = User.objects.filter(pk=payload.get("u"), email_canonical=payload.get("e")).first()
    if user is None:
        return render(request, "accounts/verify_invalid.html", status=400)

    already = user.is_email_verified
    verify(user)
    if request.user.is_authenticated and request.user.pk == user.pk:
        if not already:
            messages.success(request, "¡Listo! Confirmaste tu email y empezó tu prueba gratis.")
        return redirect("panel")
    messages.success(request, "¡Listo! Confirmaste tu email. Ingresá para empezar.")
    return redirect("login")
