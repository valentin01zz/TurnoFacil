"""WhatsApp click-to-chat links (HU-32): the owner opens their own WhatsApp with a message ready.

Nothing is sent from TurnoFacil and no WhatsApp API is used, so there is no per-message cost.
"""

import re
from urllib.parse import quote

from django.utils import timezone

from .booking_calendar import long_date

# Argentine national numbers (area code + subscriber) have 10 digits.
NATIONAL_DIGITS = 10
# A mobile number written locally adds "15" after an area code of 2, 3 or 4 digits.
AREA_CODE_LENGTHS = (2, 3, 4)


def whatsapp_number(phone):
    """Digits wa.me expects (country code, no '+'), or None when the number is not certain.

    Argentina: 54 + 9 (mobile) + area code + number, without the trunk 0 or the local 15.
    Numbers starting with '+' and another country code are used as typed.
    """
    raw = phone.strip()
    digits = re.sub(r"\D", "", raw)
    if digits.startswith("00"):
        digits, raw = digits[2:], "+"
    if raw.startswith("+") and not digits.startswith("54"):
        return digits if 8 <= len(digits) <= 15 else None
    if digits.startswith("54") and (raw.startswith("+") or len(digits) > NATIONAL_DIGITS + 1):
        digits = digits[2:]
        if digits.startswith("9"):
            digits = digits[1:]
    digits = digits.removeprefix("0")
    national = without_local_mobile_prefix(digits)
    # No area code starts with 15: "15 5555 1234" is a local number missing its area code.
    if national is None or len(national) != NATIONAL_DIGITS or national.startswith("15"):
        return None
    return f"549{national}"


def without_local_mobile_prefix(digits):
    """Drop the "15" written after the area code; None if it could sit in more than one place."""
    if len(digits) != NATIONAL_DIGITS + 2:
        return digits
    candidates = {
        digits[:size] + digits[size + 2 :]
        for size in AREA_CODE_LENGTHS
        if digits[size : size + 2] == "15"
    }
    return candidates.pop() if len(candidates) == 1 else None


def chat_url(phone, text):
    number = whatsapp_number(phone)
    return f"https://wa.me/{number}?text={quote(text)}" if number else None


def first_name(appointment):
    return appointment.customer_name.split()[0] if appointment.customer_name.strip() else ""


def when(appointment):
    start = timezone.localtime(appointment.start_at)
    day = long_date(start.date())
    return f"el {day[0].lower()}{day[1:]} a las {start:%H:%M}"


def details(appointment):
    """Service, professional, day and address. Never the customer's private management link."""
    business = appointment.business
    text = f"{appointment.service.name} con {appointment.professional.name}, {when(appointment)}."
    if business.address:
        text += f" Dirección: {business.address}."
    return text


def confirmation_url(appointment):
    business = appointment.business
    text = (
        f"Hola {first_name(appointment)}, te escribimos de {business.name}. "
        f"Tu turno quedó confirmado: {details(appointment)} ¡Te esperamos!"
    )
    return chat_url(appointment.customer_phone, text)


def reminder_url(appointment):
    business = appointment.business
    text = (
        f"Hola {first_name(appointment)}, te escribimos de {business.name} para recordarte tu "
        f"turno: {details(appointment)} Si no podés venir, avisanos. ¡Gracias!"
    )
    return chat_url(appointment.customer_phone, text)
