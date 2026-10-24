"""Access, export and deletion of personal data, for the operator commands.

Procedure: docs/agentic/legal/PROCEDIMIENTO_DERECHOS.md. Nothing here runs on its own.
"""

from datetime import timedelta

from django.db import connection, transaction
from django.utils import timezone

from bookings.models import Appointment

from .models import LegalAcceptance

ERASED_NAME = "(datos eliminados)"


def iso(value):
    return value.isoformat() if value else None


def appointment_data(appointment, with_business=False):
    data = {
        "servicio": appointment.service.name,
        "profesional": appointment.professional.name,
        "inicio": iso(appointment.start_at),
        "estado": appointment.get_status_display(),
        "origen": appointment.get_source_display(),
        "cliente": {
            "nombre": appointment.customer_name,
            "telefono": appointment.customer_phone,
            "email": appointment.customer_email,
        },
        "creado": iso(appointment.created_at),
        "sena_recibida_marcada": iso(appointment.deposit_received_at),
    }
    if with_business:
        data["negocio"] = appointment.business.name
    return data


def business_data(business):
    owner = business.owner
    subscription = getattr(business, "subscription", None)
    deposit = getattr(business, "deposit", None)
    appointments = business.appointments.select_related("service", "professional")
    return {
        "cuenta": {
            "email": owner.email,
            "alta": iso(owner.date_joined),
            "email_verificado": iso(owner.email_verified_at),
        },
        "negocio": {"nombre": business.name, "slug": business.slug, "direccion": business.address},
        "servicios": [
            {"nombre": s.name, "duracion_minutos": s.duration_minutes, "activo": s.is_active}
            for s in business.services.all()
        ],
        "profesionales": [
            {"nombre": p.name, "activo": p.is_active} for p in business.professionals.all()
        ],
        "sena": None
        if deposit is None
        else {
            "activa": deposit.enabled,
            "monto": str(deposit.amount) if deposit.amount is not None else None,
            "titular": deposit.holder_name,
            "alias": deposit.transfer_alias,
            "cbu_cvu": deposit.cbu_cvu,
            "cuit_cuil": deposit.holder_tax_id,
            "indicaciones": deposit.instructions,
            "condiciones": deposit.conditions,
        },
        "suscripcion": None
        if subscription is None
        else {
            "plan": subscription.plan.name,
            "estado": subscription.get_status_display(),
            "prueba_hasta": iso(subscription.trial_ends_at),
            "periodo_hasta": iso(subscription.current_period_end),
            "proveedor": subscription.provider,
        },
        "aceptaciones": [
            {
                "documento": str(a.document),
                "sha256": a.document.body_sha256,
                "accion": a.get_action_display(),
                "contexto": a.get_context_display(),
                "fecha": iso(a.created_at),
            }
            for a in LegalAcceptance.objects.filter(user=owner).select_related("document")
        ],
        "turnos": [appointment_data(a) for a in appointments],
    }


def customer_appointments(email):
    """Appointments booked with `email`, across businesses (for a customer's own request)."""
    return Appointment.objects.filter(customer_email__iexact=email.strip()).select_related(
        "business", "service", "professional"
    )


def erase_customer(email, now=None):
    """Erase the customer's details from their past and cancelled appointments.

    Future confirmed ones are left alone: the business is responsible for that booking and has to
    cancel it first. Returns (erased, kept_future).
    """
    now = now or timezone.now()
    appointments = customer_appointments(email)
    future = appointments.filter(status=Appointment.CONFIRMED, end_at__gt=now)
    with transaction.atomic():
        erased = appointments.exclude(pk__in=future).update(
            customer_name=ERASED_NAME, customer_phone="", customer_email=""
        )
    return erased, future.count()


def delete_business(business):
    """Delete a business, its owner account and everything that hangs from them.

    The only place that may delete legal acceptances: the database refuses it otherwise
    (migration legal.0005). The permission is opened and closed inside this transaction.
    """
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL legal.allow_evidence_delete = 'on'")
        # Appointments protect their professional and service, so they go first.
        business.appointments.all().delete()
        owner = business.owner
        business.delete()
        owner.delete()
        # Closed again at once, also when this runs inside an outer transaction.
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL legal.allow_evidence_delete = 'off'")


def purge_appointments(days, now=None):
    """Delete appointments that ended more than `days` days ago. Returns how many."""
    now = now or timezone.now()
    deleted, _ = Appointment.objects.filter(end_at__lt=now - timedelta(days=days)).delete()
    return deleted
