from datetime import datetime, timedelta

from django.conf import settings
from django.db.models import Q
from django.utils import timezone

from businesses.models import TimeOff

from .models import Appointment


def booking_window(today=None):
    """First and last dates a customer can book."""
    today = today or timezone.localdate()
    return today, today + timedelta(days=settings.BOOKING_WINDOW_DAYS)


def time_off_ranges(professional, start, end):
    """(start, end) of the blocks that touch [start, end): the professional's and the business's."""
    return list(
        TimeOff.objects.filter(
            Q(professional=professional) | Q(professional__isnull=True),
            business_id=professional.business_id,
            start_at__lt=end,
            end_at__gt=start,
        ).values_list("start_at", "end_at")
    )


def is_covered(start, end, ranges):
    """Whether `ranges` together leave no free moment in [start, end)."""
    reached = start
    for range_start, range_end in sorted(ranges):
        if range_start > reached:
            break
        reached = max(reached, range_end)
        if reached >= end:
            return True
    return reached >= end


def available_slots(professional, service, date, now=None, ignore=None):
    """Start times on `date` where `service` fits in the professional's free working hours.

    Free means no confirmed appointment and no time off (the professional's or the business's).

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
    busy += time_off_ranges(professional, day_start, day_start + timedelta(days=1))

    # Every range of the day (split shifts have several); a set so ranges never repeat a start.
    slots = set()
    for hours in professional.working_hours.filter(weekday=date.weekday()):
        start = timezone.make_aware(datetime.combine(date, hours.start_time), tz)
        end = timezone.make_aware(datetime.combine(date, hours.end_time), tz)
        while start + duration <= end:
            finish = start + duration
            overlaps = any(
                start < busy_end and busy_start < finish for busy_start, busy_end in busy
            )
            if start > now and not overlaps:
                slots.add(start)
            start += step
    return sorted(slots)
