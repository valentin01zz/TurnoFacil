from datetime import datetime, timedelta

from django.conf import settings
from django.utils import timezone

from .models import Appointment


def booking_window(today=None):
    """First and last dates a customer can book."""
    today = today or timezone.localdate()
    return today, today + timedelta(days=settings.BOOKING_WINDOW_DAYS)


def available_slots(professional, service, date, now=None, ignore=None):
    """Start times on `date` where `service` fits in the professional's free working hours.

    `ignore` is an appointment being moved: its own time does not count as busy.
    """
    now = now or timezone.now()
    first_day, last_day = booking_window(timezone.localdate(now))
    if not first_day <= date <= last_day:
        return []

    duration = timedelta(minutes=service.duration_minutes)
    step = timedelta(minutes=settings.SLOT_STEP_MINUTES)
    tz = timezone.get_current_timezone()
    day_start = timezone.make_aware(datetime.combine(date, datetime.min.time()), tz)

    appointments = Appointment.objects.filter(
        professional=professional,
        status=Appointment.CONFIRMED,
        start_at__lt=day_start + timedelta(days=1),
        end_at__gt=day_start,
    )
    if ignore is not None:
        appointments = appointments.exclude(pk=ignore.pk)
    busy = list(appointments.values_list("start_at", "end_at"))

    slots = []
    for hours in professional.working_hours.filter(weekday=date.weekday()):
        start = timezone.make_aware(datetime.combine(date, hours.start_time), tz)
        end = timezone.make_aware(datetime.combine(date, hours.end_time), tz)
        while start + duration <= end:
            finish = start + duration
            overlaps = any(
                start < busy_end and busy_start < finish for busy_start, busy_end in busy
            )
            if start > now and not overlaps:
                slots.append(start)
            start += step
    return slots
