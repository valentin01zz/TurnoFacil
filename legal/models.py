"""Legal documents, the evidence of what each owner accepted, and cancellation requests.

See docs/agentic/legal/PLAN_IMPLEMENTACION.md. The database, not the templates, is the source of
truth for the published text: a published version is never edited, a new one is published instead.
"""

import hashlib

from django.conf import settings
from django.db import models
from django.utils import timezone

from businesses.models import Business


class ImmutableError(Exception):
    """A row that serves as legal evidence was about to be changed."""


class LegalDocument(models.Model):
    TERMS = "terms"
    PRIVACY = "privacy"
    KINDS = [(TERMS, "Términos y Condiciones"), (PRIVACY, "Política de Privacidad")]

    kind = models.CharField(max_length=10, choices=KINDS)
    version = models.CharField(max_length=20)
    body = models.TextField()
    # Integrity check of the exact text shown; a complement to keeping the text, not a proof alone.
    body_sha256 = models.CharField(max_length=64, editable=False)
    effective_at = models.DateTimeField(default=timezone.now)
    published_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["kind", "-effective_at", "-published_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["kind", "version"], name="legal_document_unique_version"
            )
        ]

    def __str__(self):
        return f"{self.get_kind_display()} v{self.version}"

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise ImmutableError(
                "A published legal document is never edited; publish a new version."
            )
        self.body_sha256 = hashlib.sha256(self.body.encode()).hexdigest()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ImmutableError("A published legal document is never deleted.")

    @classmethod
    def current(cls, kind, now=None):
        """The version in force now, or None when none was published."""
        now = now or timezone.now()
        return cls.objects.filter(kind=kind, effective_at__lte=now).first()


class LegalAcceptance(models.Model):
    """What an owner did with one exact document version. Created by the server, never by hand.

    ACCEPTED: the owner ticked the box for that version. INFORMED: the version was linked in the
    form the owner submitted (the privacy notice), which records notice, not consent.
    No IP or user agent: they are not needed for this purpose (see the plan).
    """

    ACCEPTED = "accepted"
    INFORMED = "informed"
    ACTIONS = [(ACCEPTED, "Aceptó"), (INFORMED, "Informado")]

    SIGNUP = "signup"
    REACCEPTANCE = "reacceptance"
    CONTEXTS = [(SIGNUP, "Registro"), (REACCEPTANCE, "Nueva versión")]

    # Deleting an account (a data deletion request) deletes its evidence too.
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="legal_acceptances"
    )
    document = models.ForeignKey(LegalDocument, on_delete=models.PROTECT, related_name="+")
    action = models.CharField(max_length=10, choices=ACTIONS)
    context = models.CharField(max_length=15, choices=CONTEXTS)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["created_at", "pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "document", "action"], name="legal_acceptance_once_per_version"
            )
        ]

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise ImmutableError("An acceptance record is never edited.")
        return super().save(*args, **kwargs)


class ServiceRequest(models.Model):
    """A cancellation (baja) or withdrawal (arrepentimiento) asked for from the public buttons.

    Saved and answered with its code before anything else happens (Disposición 954/2025, art. 5).
    It takes effect when the account's mailbox confirms it, so nobody can cancel someone else's plan
    by typing their email. Pending ones are listed for the operator (`service_requests`).
    """

    CANCEL = "cancel"
    WITHDRAWAL = "withdrawal"
    KINDS = [(CANCEL, "Baja de servicio"), (WITHDRAWAL, "Arrepentimiento")]

    # What confirming did.
    RENEWAL_STOPPED = "renewal_stopped"
    NOTHING_TO_CHARGE = "nothing_to_charge"
    MANUAL_REVIEW = "manual_review"
    REFUND_DUE = "refund_due"
    OUT_OF_TERM = "out_of_term"
    OUTCOMES = [
        (RENEWAL_STOPPED, "Se cortó la renovación"),
        (NOTHING_TO_CHARGE, "No había cobros activos"),
        (MANUAL_REVIEW, "Revisión del operador"),
        (REFUND_DUE, "Reembolso pendiente"),
        (OUT_OF_TERM, "Fuera de plazo: tramitado como baja"),
    ]

    kind = models.CharField(max_length=10, choices=KINDS)
    code = models.CharField(max_length=20, unique=True)
    email = models.EmailField()
    business = models.ForeignKey(
        Business, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    created_at = models.DateTimeField(default=timezone.now)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    outcome = models.CharField(max_length=20, choices=OUTCOMES, blank=True)
    # A withdrawal in term owes a refund, apart from whether the renewal could be stopped.
    refund_due = models.BooleanField(default=False)
    # When each email went out; empty means it failed (or is not due yet) and the operator resends.
    received_email_sent_at = models.DateTimeField(null=True, blank=True)
    done_email_sent_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution_note = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.code} · {self.get_kind_display()}"

    @property
    def needs_operator(self):
        return self.resolved_at is None and (
            self.refund_due or self.outcome in (self.MANUAL_REVIEW, self.REFUND_DUE)
        )

    @property
    def email_failed(self):
        if self.received_email_sent_at is None:
            return True
        return self.confirmed_at is not None and self.done_email_sent_at is None
