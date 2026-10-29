"""Income and reports (HU-35): figures for a period, compared with the previous one, and the export.

Income is an estimate from each appointment's saved price, never a tax document.
"""

import csv
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date as date_cls
from datetime import datetime, timedelta
from decimal import Decimal

from django.utils import timezone

from bookings.booking_calendar import MONTHS, WEEKDAYS_SHORT, shift_month
from bookings.models import Appointment
from bookings.whatsapp import whatsapp_number

PERIODS = [
    ("week", "Esta semana"),
    ("month", "Este mes"),
    ("last_month", "Mes anterior"),
    ("quarter", "Últimos 3 meses"),
]
DEFAULT_PERIOD = "month"
ZERO = Decimal("0")


@dataclass(frozen=True)
class Period:
    first_day: date_cls
    end_day: date_cls  # exclusive
    label: str

    @property
    def last_day(self):
        return self.end_day - timedelta(days=1)


def period_for(code, today):
    """The chosen period and the previous one of the same length, as (current, previous)."""
    if code == "week":
        monday = today - timedelta(days=today.weekday())
        current = Period(monday, monday + timedelta(days=7), "Esta semana")
        previous = Period(monday - timedelta(days=7), monday, "la semana anterior")
        return current, previous
    month = today.replace(day=1)
    if code == "last_month":
        month = shift_month(month, -1)
    months = 3 if code == "quarter" else 1
    first = shift_month(month, -(months - 1))
    current = Period(first, shift_month(month, 1), month_label(first, month))
    previous_first = shift_month(first, -months)
    previous = Period(
        previous_first,
        first,
        "el mes anterior" if months == 1 else "los 3 meses anteriores",
    )
    return current, previous


def month_label(first, last):
    if first == last:
        return f"{MONTHS[first.month - 1].capitalize()} {first.year}"
    return f"{MONTHS[first.month - 1].capitalize()} a {MONTHS[last.month - 1]} {last.year}"


def local_midnight(day):
    return timezone.make_aware(datetime.combine(day, datetime.min.time()))


def appointments_in(business, period, professional=None):
    queryset = Appointment.objects.filter(
        business=business,
        start_at__gte=local_midnight(period.first_day),
        start_at__lt=local_midnight(period.end_day),
    )
    if professional is not None:
        queryset = queryset.filter(professional=professional)
    return queryset.select_related("service", "professional").order_by("start_at")


def customer_key(phone):
    """Same customer across bookings: the WhatsApp form of the phone, or its digits."""
    return whatsapp_number(phone) or re.sub(r"\D", "", phone)


def totals(appointments, now):
    """Counts and income for a list of appointments (any status)."""
    result = {
        "attended": 0,
        "no_show": 0,
        "pending": 0,
        "upcoming": 0,
        "cancelled": 0,
        "income_attended": ZERO,
        "income_pending": ZERO,
        "income_upcoming": ZERO,
    }
    for appointment in appointments:
        price = appointment.price or ZERO
        if not appointment.is_confirmed:
            result["cancelled"] += 1
        elif appointment.start_at > now:
            result["upcoming"] += 1
            result["income_upcoming"] += price
        elif appointment.attendance == Appointment.ATTENDED:
            result["attended"] += 1
            result["income_attended"] += price
        elif appointment.attendance == Appointment.NO_SHOW:
            result["no_show"] += 1
        else:
            result["pending"] += 1
            result["income_pending"] += price
    marked = result["attended"] + result["no_show"]
    total = len(appointments)
    result["total"] = total
    result["no_show_rate"] = percent(result["no_show"], marked)
    result["cancel_rate"] = percent(result["cancelled"], total)
    return result


def percent(part, whole):
    return round(part * 100 / whole) if whole else None


def change(current, previous):
    """Percent change against the previous period, or None when there is nothing to compare."""
    if not previous:
        return None
    return round((current - previous) * 100 / previous)


def ranking(appointments, key, label):
    """Per professional or service: appointments kept (not cancelled), attended and their income."""
    rows = defaultdict(lambda: {"count": 0, "attended": 0, "income": ZERO})
    names = {}
    for appointment in appointments:
        if not appointment.is_confirmed:
            continue
        pk = key(appointment)
        names[pk] = label(appointment)
        row = rows[pk]
        row["count"] += 1
        if appointment.attendance == Appointment.ATTENDED:
            row["attended"] += 1
            row["income"] += appointment.price or ZERO
    ordered = sorted(rows.items(), key=lambda item: (-item[1]["income"], -item[1]["count"]))
    top = max((row["count"] for _, row in ordered), default=0) or 1
    return [
        {"name": names[pk], **row, "width": max(round(row["count"] / top * 100), 4)}
        for pk, row in ordered
    ]


def demand(appointments):
    """Appointments kept, by weekday (Monday first) and by starting hour."""
    kept = [timezone.localtime(a.start_at) for a in appointments if a.is_confirmed]
    by_day = Counter(start.weekday() for start in kept)
    by_hour = Counter(start.hour for start in kept)
    day_peak = max(by_day.values(), default=0) or 1
    hour_peak = max(by_hour.values(), default=0) or 1
    hours = range(min(by_hour), max(by_hour) + 1) if by_hour else []
    return {
        "days": [
            {
                "label": WEEKDAYS_SHORT[day],
                "count": by_day[day],
                "height": max(round(by_day[day] / day_peak * 100), 6),
            }
            for day in range(7)
        ],
        "hours": [
            {
                "label": f"{hour:02d}",
                "count": by_hour[hour],
                "height": max(round(by_hour[hour] / hour_peak * 100), 6),
            }
            for hour in hours
        ],
    }


def customers(business, appointments, period):
    """Distinct customers kept in the period, split into first-timers and returning ones."""
    keys = {customer_key(a.customer_phone) for a in appointments if a.is_confirmed}
    keys.discard("")
    earlier = {
        customer_key(phone)
        for phone in Appointment.objects.filter(
            business=business,
            status=Appointment.CONFIRMED,
            start_at__lt=local_midnight(period.first_day),
        ).values_list("customer_phone", flat=True)
    }
    returning = len(keys & earlier)
    return {"total": len(keys), "new": len(keys) - returning, "returning": returning}


def build_report(business, period_code, professional=None, now=None):
    now = now or timezone.now()
    current, previous = period_for(period_code, timezone.localdate(now))
    appointments = list(appointments_in(business, current, professional))
    before = totals(list(appointments_in(business, previous, professional)), now)
    figures = totals(appointments, now)
    return {
        "period": current,
        "previous": previous,
        "totals": figures,
        "changes": {
            "income_attended": change(figures["income_attended"], before["income_attended"]),
            "attended": change(figures["attended"], before["attended"]),
        },
        "previous_totals": before,
        "professionals": ranking(
            appointments, lambda a: a.professional_id, lambda a: a.professional.name
        ),
        "services": ranking(appointments, lambda a: a.service_id, lambda a: a.service.name),
        "demand": demand(appointments),
        "customers": customers(business, appointments, current),
        "unpriced_services": business.services.filter(is_active=True, price__isnull=True).count(),
        "has_appointments": bool(appointments),
    }


# Excel in Spanish reads ";" as the column separator and "," as the decimal mark.
EXPORT_COLUMNS = [
    "Fecha",
    "Hora",
    "Cliente",
    "Teléfono",
    "Email",
    "Servicio",
    "Profesional",
    "Precio",
    "Estado",
    "Asistencia",
    "Origen",
]
FORMULA_START = ("=", "+", "-", "@", "\t", "\r")


def safe_cell(value):
    """Text a spreadsheet will not run as a formula (CSV injection)."""
    text = str(value)
    return f"'{text}" if text.startswith(FORMULA_START) else text


def money(value):
    return "" if value is None else f"{value:.2f}".replace(".", ",")


def export_rows(appointments):
    statuses = dict(Appointment.STATUSES)
    attendances = dict(Appointment.ATTENDANCES)
    sources = dict(Appointment.SOURCES)
    for appointment in appointments:
        start = timezone.localtime(appointment.start_at)
        yield [
            f"{start:%d/%m/%Y}",
            f"{start:%H:%M}",
            safe_cell(appointment.customer_name),
            safe_cell(appointment.customer_phone),
            safe_cell(appointment.customer_email),
            safe_cell(appointment.service.name),
            safe_cell(appointment.professional.name),
            money(appointment.price),
            statuses[appointment.status],
            attendances[appointment.attendance] if appointment.is_confirmed else "",
            sources[appointment.source],
        ]


def write_export(response, appointments):
    response.write("﻿")  # BOM: Excel then reads the accents as UTF-8
    writer = csv.writer(response, delimiter=";")
    writer.writerow(EXPORT_COLUMNS)
    writer.writerows(export_rows(appointments))
    return response
