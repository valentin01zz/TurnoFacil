import secrets
from datetime import datetime, time, timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone

from bookings.models import Appointment
from businesses.models import Business, Professional, Service, WorkingHours

User = get_user_model()


def create_business(email="a@example.com", name="Estética Luna"):
    user = User.objects.create_user(email, "correct-horse-battery")
    return Business.objects.create(owner=user, name=name)


def create_professional(business, name="Ana", ranges=((time(9), time(13)), (time(14), time(18)))):
    """Professional working the given ranges every day of the week."""
    professional = Professional.objects.create(business=business, name=name)
    for weekday in range(7):
        for start, end in ranges:
            WorkingHours.objects.create(
                professional=professional, weekday=weekday, start_time=start, end_time=end
            )
    return professional


def create_service(business, name="Limpieza facial", duration=50):
    return Service.objects.create(business=business, name=name, duration_minutes=duration)


def local_dt(date, hour, minute=0):
    return timezone.make_aware(datetime.combine(date, time(hour, minute)))


def future_date(days=7):
    return timezone.localdate() + timedelta(days=days)


def create_appointment(professional, service, start_at, status=Appointment.CONFIRMED):
    return Appointment.objects.create(
        business=professional.business,
        professional=professional,
        service=service,
        customer_name="Cliente",
        customer_phone="11 5555 5555",
        customer_email="cliente@example.com",
        start_at=start_at,
        end_at=start_at + timedelta(minutes=service.duration_minutes),
        status=status,
        manage_token=secrets.token_urlsafe(32),
    )
