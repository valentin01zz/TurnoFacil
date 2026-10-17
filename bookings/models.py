from django.contrib.postgres.constraints import ExclusionConstraint
from django.contrib.postgres.fields import DateTimeRangeField, RangeOperators
from django.db import models

from businesses.models import Business, Professional, Service


class TsTzRange(models.Func):
    function = "TSTZRANGE"
    output_field = DateTimeRangeField()


class Appointment(models.Model):
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    STATUSES = [(CONFIRMED, "Confirmado"), (CANCELLED, "Cancelado")]

    ONLINE = "online"
    MANUAL = "manual"
    SOURCES = [(ONLINE, "Online"), (MANUAL, "Manual")]

    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="appointments")
    professional = models.ForeignKey(
        Professional, on_delete=models.PROTECT, related_name="appointments"
    )
    service = models.ForeignKey(Service, on_delete=models.PROTECT, related_name="appointments")
    customer_name = models.CharField("nombre", max_length=100)
    customer_phone = models.CharField("teléfono", max_length=30)
    customer_email = models.EmailField("email", blank=True)
    start_at = models.DateTimeField()
    end_at = models.DateTimeField()
    status = models.CharField(max_length=10, choices=STATUSES, default=CONFIRMED)
    source = models.CharField(max_length=10, choices=SOURCES, default=ONLINE)
    manage_token = models.CharField(max_length=64, unique=True)
    reminder_due_at = models.DateTimeField(null=True, blank=True)
    reminder_sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["start_at"]
        indexes = [
            models.Index(fields=["business", "start_at"]),
            models.Index(fields=["reminder_due_at"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(end_at__gt=models.F("start_at")),
                name="appointment_end_after_start",
            ),
            # The database, not the app, guarantees one professional is never double-booked.
            ExclusionConstraint(
                name="appointment_no_overlap",
                expressions=[
                    ("professional", RangeOperators.EQUAL),
                    (TsTzRange("start_at", "end_at"), RangeOperators.OVERLAPS),
                ],
                condition=models.Q(status="confirmed"),
            ),
        ]

    def __str__(self):
        return f"{self.customer_name} - {self.start_at:%Y-%m-%d %H:%M}"
