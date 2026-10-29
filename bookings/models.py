from datetime import timedelta

from django.conf import settings
from django.contrib.postgres.constraints import ExclusionConstraint
from django.contrib.postgres.fields import DateTimeRangeField, RangeOperators
from django.db import models
from django.utils import timezone

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

    # Marked by the owner once the appointment has started; empty means not marked yet.
    NOT_MARKED = ""
    ATTENDED = "attended"
    NO_SHOW = "no_show"
    ATTENDANCES = [(NOT_MARKED, "Sin marcar"), (ATTENDED, "Asistió"), (NO_SHOW, "No asistió")]

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
    # Marked by hand by the business. TurnoFacil never checks a transfer; this only records it.
    deposit_received_at = models.DateTimeField(null=True, blank=True)
    # The service's price when it was booked, so later price changes keep past income as it was.
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    # db_default too: code still running during a deploy inserts rows without this column.
    attendance = models.CharField(
        max_length=10, choices=ATTENDANCES, default=NOT_MARKED, db_default=NOT_MARKED, blank=True
    )
    attendance_marked_at = models.DateTimeField(null=True, blank=True)

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
            # Only confirmed appointments carry an attendance mark.
            models.CheckConstraint(
                condition=models.Q(attendance="")
                | (models.Q(status="confirmed") & models.Q(attendance__in=["attended", "no_show"])),
                name="appointment_attendance_valid",
            ),
        ]

    def __str__(self):
        return f"{self.customer_name} - {self.start_at:%Y-%m-%d %H:%M}"

    @property
    def is_confirmed(self):
        return self.status == self.CONFIRMED

    @property
    def is_past(self):
        return self.start_at <= timezone.now()

    def can_mark_attendance(self, now=None):
        return self.is_confirmed and self.start_at <= (now or timezone.now())

    def mark_attendance(self, attendance, now=None):
        """Set (or clear, with NOT_MARKED) whether the customer came."""
        self.attendance = attendance
        self.attendance_marked_at = None if attendance == self.NOT_MARKED else now or timezone.now()
        self.save(update_fields=["attendance", "attendance_marked_at", "updated_at"])

    def customer_can_change(self, now=None):
        """Customers may change a confirmed appointment until the configured limit before it."""
        now = now or timezone.now()
        limit = timedelta(hours=settings.CUSTOMER_CHANGE_LIMIT_HOURS)
        return self.is_confirmed and self.start_at - now >= limit

    def move_to(self, start_at, professional=None, now=None):
        """Move to a new start time (and professional), resetting the reminder."""
        now = now or timezone.now()
        if professional is not None and professional.business_id != self.business_id:
            raise ValueError(
                f"Professional {professional.pk} is not from business {self.business_id}"
            )
        self.professional = professional or self.professional
        reminder_due_at = start_at - timedelta(hours=settings.REMINDER_HOURS_BEFORE)
        self.start_at = start_at
        self.end_at = start_at + timedelta(minutes=self.service.duration_minutes)
        self.reminder_due_at = reminder_due_at if reminder_due_at > now else None
        self.reminder_sent_at = None
        # A new time is a new visit: any attendance mark belonged to the old one.
        self.attendance = self.NOT_MARKED
        self.attendance_marked_at = None
        self.save(
            update_fields=[
                "professional",
                "start_at",
                "end_at",
                "reminder_due_at",
                "reminder_sent_at",
                "attendance",
                "attendance_marked_at",
                "updated_at",
            ]
        )

    def cancel(self, now=None):
        self.status = self.CANCELLED
        self.cancelled_at = now or timezone.now()
        self.reminder_due_at = None
        self.attendance = self.NOT_MARKED
        self.attendance_marked_at = None
        self.save(
            update_fields=[
                "status",
                "cancelled_at",
                "reminder_due_at",
                "attendance",
                "attendance_marked_at",
                "updated_at",
            ]
        )
