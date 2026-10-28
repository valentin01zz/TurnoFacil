"""Calendar helpers for the booking screens: Spanish labels, the month day strip and slot groups."""

import calendar
from collections import defaultdict
from datetime import date as date_cls
from datetime import datetime

from django.utils import timezone

from businesses.models import WorkingHours

from .availability import booking_window, is_covered, time_off_ranges

WEEKDAYS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
WEEKDAYS_SHORT = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
MONTHS = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]  # fmt: skip
AFTERNOON_FROM_HOUR = 13


def long_date(day):
    """'Lunes 19 de octubre'."""
    return f"{WEEKDAYS[day.weekday()]} {day.day} de {MONTHS[day.month - 1]}"


def parse_month(value):
    """First day of the month from 'YYYY-MM', or None if the value is missing or malformed."""
    try:
        year, month = (int(part) for part in value.split("-"))
        return date_cls(year, month, 1)
    except (AttributeError, TypeError, ValueError):
        return None


def local_midnight(day, tz):
    return timezone.make_aware(datetime.combine(day, datetime.min.time()), tz)


def shift_month(first_day, months):
    index = first_day.year * 12 + first_day.month - 1 + months
    return date_cls(index // 12, index % 12 + 1, 1)


def month_strip(month, professionals, selected=None, today=None):
    """Every day of `month`, flagged as bookable when it is inside the booking window and one of
    `professionals` has working hours that day not fully covered by time off. The month is clamped
    to the months the window touches."""
    today = today or timezone.localdate()
    first_day, last_day = booking_window(today)
    first_month, last_month = first_day.replace(day=1), last_day.replace(day=1)
    month = min(max(month or first_month, first_month), last_month)
    month_end = shift_month(month, 1)

    hours_by_weekday = defaultdict(list)
    for hours in WorkingHours.objects.filter(professional__in=professionals):
        hours_by_weekday[(hours.professional_id, hours.weekday)].append(hours)
    tz = timezone.get_current_timezone()
    blocks = {
        pro.pk: time_off_ranges(pro, local_midnight(month, tz), local_midnight(month_end, tz))
        for pro in professionals
    }

    def is_bookable(day):
        for pro in professionals:
            for hours in hours_by_weekday[(pro.pk, day.weekday())]:
                start = timezone.make_aware(datetime.combine(day, hours.start_time), tz)
                end = timezone.make_aware(datetime.combine(day, hours.end_time), tz)
                if not is_covered(start, end, blocks[pro.pk]):
                    return True
        return False

    days = []
    for number in range(1, calendar.monthrange(month.year, month.month)[1] + 1):
        day = month.replace(day=number)
        days.append(
            {
                "date": day,
                "iso": day.isoformat(),
                "weekday": WEEKDAYS_SHORT[day.weekday()],
                "number": number,
                "long": long_date(day),
                "enabled": first_day <= day <= last_day and is_bookable(day),
                "selected": day == selected,
                "is_today": day == today,
            }
        )
    return {
        "month": month,
        "label": f"{MONTHS[month.month - 1].capitalize()} {month.year}",
        "days": days,
        "previous": shift_month(month, -1) if month > first_month else None,
        "next": shift_month(month, 1) if month < last_month else None,
    }


def slot_groups(slots, checked_value=""):
    """Split free start times into morning and afternoon for display."""
    groups = {"morning": [], "afternoon": []}
    for slot in slots:
        local = timezone.localtime(slot)
        key = "morning" if local.hour < AFTERNOON_FROM_HOUR else "afternoon"
        value = slot.isoformat()
        groups[key].append(
            {"value": value, "label": f"{local:%H:%M}", "checked": value == checked_value}
        )
    return [
        {"key": key, "label": label, "slots": groups[key]}
        for key, label in (("morning", "Mañana"), ("afternoon", "Tarde"))
        if groups[key]
    ]
