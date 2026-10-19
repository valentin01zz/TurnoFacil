from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from django.db import models
from django.utils import timezone

from .identity import canonical_email


class UserManager(BaseUserManager):
    def create_user(self, email, password, verified=False):
        email = email.strip().lower()
        user = self.model(
            email=email,
            email_canonical=canonical_email(email),
            email_verified_at=timezone.now() if verified else None,
        )
        user.set_password(password)
        user.save(using=self._db)
        return user


class User(AbstractBaseUser):
    email = models.EmailField("email", unique=True)
    # The mailbox behind the address (no "+tags", no Gmail dots): one account per mailbox.
    email_canonical = models.CharField(max_length=254, unique=True)
    email_verified_at = models.DateTimeField(null=True, blank=True)
    verification_sent_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    date_joined = models.DateTimeField(default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = "email"

    def __str__(self):
        return self.email

    @property
    def is_email_verified(self):
        return self.email_verified_at is not None


class Attempt(models.Model):
    """One counted action (failed login, reset request, signup, booking), for rate limits."""

    scope = models.CharField(max_length=20)
    key = models.CharField(max_length=254)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        indexes = [
            models.Index(fields=["scope", "key", "created_at"], name="attempt_lookup"),
            models.Index(fields=["created_at"], name="attempt_cleanup"),
        ]
