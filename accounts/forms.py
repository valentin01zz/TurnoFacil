import logging

from django import forms
from django.contrib.auth import get_user_model, password_validation
from django.contrib.auth.forms import AuthenticationForm, PasswordResetForm
from django.db import transaction

from businesses.models import Business

from . import throttle
from .identity import canonical_email

User = get_user_model()
logger = logging.getLogger(__name__)

LOGIN_LOCKED_MESSAGE = (
    "Hubo demasiados intentos fallidos. Por seguridad, esperá 15 minutos y probá de nuevo, "
    "o recuperá tu contraseña."
)


class SignupForm(forms.Form):
    business_name = forms.CharField(label="Nombre del negocio", max_length=80)
    email = forms.EmailField(label="Email")
    password = forms.CharField(label="Contraseña", widget=forms.PasswordInput, strip=False)

    def clean_business_name(self):
        # Collapse line breaks, tabs and repeated spaces: the name goes into email subjects.
        name = " ".join(self.cleaned_data["business_name"].split())
        if not name:
            raise forms.ValidationError("Este campo es obligatorio.")
        return name

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        # Aliases of the same mailbox (dots in Gmail, "+tags") count as the same account.
        if User.objects.filter(email_canonical=canonical_email(email)).exists():
            raise forms.ValidationError("Ya existe una cuenta con ese email.")
        return email

    def clean_password(self):
        password = self.cleaned_data["password"]
        password_validation.validate_password(password)
        return password

    @transaction.atomic
    def save(self):
        # The account starts unverified; the trial starts when the owner confirms the email.
        user = User.objects.create_user(self.cleaned_data["email"], self.cleaned_data["password"])
        Business.objects.create(owner=user, name=self.cleaned_data["business_name"])
        return user


class LoginForm(AuthenticationForm):
    def clean_username(self):
        return self.cleaned_data["username"].lower()

    def clean(self):
        account = canonical_email(self.data.get("username", ""))
        ip = throttle.client_ip(self.request) if self.request else ""
        # Checked before the password, so a locked account answers the same either way.
        if throttle.is_limited("login", account) or throttle.is_limited("login_ip", ip):
            raise forms.ValidationError(LOGIN_LOCKED_MESSAGE, code="throttled")
        try:
            cleaned = super().clean()
        except forms.ValidationError:
            throttle.record("login", account)
            throttle.record("login_ip", ip)
            raise
        throttle.clear("login", account)
        return cleaned


class ThrottledPasswordResetForm(PasswordResetForm):
    """Same answer for everyone, but at most a few reset emails per account and per IP."""

    def save(self, *args, request=None, **kwargs):
        account = canonical_email(self.cleaned_data["email"])
        ip = throttle.client_ip(request) if request else ""
        if throttle.is_limited("reset", account) or throttle.is_limited("reset_ip", ip):
            return
        throttle.record("reset", account)
        throttle.record("reset_ip", ip)
        return super().save(*args, request=request, **kwargs)
