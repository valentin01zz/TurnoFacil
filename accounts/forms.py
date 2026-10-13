from django import forms
from django.contrib.auth import get_user_model, password_validation
from django.contrib.auth.forms import AuthenticationForm
from django.db import transaction

from businesses.models import Business

User = get_user_model()


class SignupForm(forms.Form):
    business_name = forms.CharField(label="Nombre del negocio", max_length=80)
    email = forms.EmailField(label="Email")
    password = forms.CharField(label="Contraseña", widget=forms.PasswordInput, strip=False)

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("Ya existe una cuenta con ese email.")
        return email

    def clean_password(self):
        password = self.cleaned_data["password"]
        password_validation.validate_password(password)
        return password

    @transaction.atomic
    def save(self):
        user = User.objects.create_user(self.cleaned_data["email"], self.cleaned_data["password"])
        Business.objects.create(owner=user, name=self.cleaned_data["business_name"])
        return user


class LoginForm(AuthenticationForm):
    def clean_username(self):
        return self.cleaned_data["username"].lower()
