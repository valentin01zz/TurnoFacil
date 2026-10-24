"""Seña: conditions, what the customer sees before booking, and the owner's "seña recibida" mark.

The seña is a direct transfer from the customer to the business; TurnoFacil never receives or checks
it (docs/agentic/legal/LEGAL_REVIEW.md, H17 to H22).
"""

from datetime import timedelta

from django.core import mail
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from billing.tests.helpers import set_active
from bookings.emails import send_cancelled
from bookings.models import Appointment
from bookings.tests.helpers import (
    create_appointment,
    create_business,
    create_professional,
    create_service,
    future_date,
    local_dt,
)

from .test_deposit import VALID, enable_deposit

CONDITIONS = "Se devuelve si cancelás con 24 horas de anticipación."


class DepositConditionsTests(TestCase):
    def setUp(self):
        self.business = create_business()
        self.ana = create_professional(self.business)
        self.service = create_service(self.business)
        set_active(self.business, "profesional", timezone.now() + timedelta(days=20))

    def booking_page(self):
        return self.client.get(reverse("booking_page", args=[self.business.slug]))

    def test_conditions_are_optional(self):
        self.client.force_login(self.business.owner)
        response = self.client.post(reverse("deposit_settings"), VALID)
        self.assertRedirects(response, reverse("deposit_settings"))
        self.assertEqual(self.business.deposit.conditions, "")

    def test_conditions_are_saved_on_one_line(self):
        self.client.force_login(self.business.owner)
        self.client.post(
            reverse("deposit_settings"), {**VALID, "conditions": "Se devuelve\nsi avisás"}
        )
        self.business.deposit.refresh_from_db()
        self.assertEqual(self.business.deposit.conditions, "Se devuelve si avisás")

    def test_before_booking_the_customer_sees_amount_holder_conditions_and_who_receives_it(self):
        enable_deposit(self.business, conditions=CONDITIONS)
        page = self.booking_page()
        for text in (
            "Seña de $ 5.000",
            "por transferencia a Ana Pérez",
            CONDITIONS,
            "TurnoFacil no recibe el dinero ni verifica el pago",
            "Tu turno queda confirmado al reservar",
        ):
            self.assertContains(page, text)
        # The account number itself still comes after confirming.
        self.assertNotContains(page, "estetica.luna")

    def test_without_conditions_the_customer_is_told_to_ask(self):
        enable_deposit(self.business)
        self.assertContains(self.booking_page(), "no cargó condiciones para la seña")

    def test_no_seña_no_note(self):
        self.assertNotContains(self.booking_page(), "Seña de $")

    def test_the_privacy_notice_names_the_business_as_responsible(self):
        self.assertContains(self.booking_page(), f"Tus datos los usa {self.business.name}")
        # The full notice sits next to the contact fields, shown once a time is chosen.
        query = {
            "service": self.service.pk,
            "professional": self.ana.pk,
            "date": future_date().isoformat(),
        }
        page = self.client.get(reverse("booking_page", args=[self.business.slug]), query)
        self.assertContains(page, f"{self.business.name} usa tus datos para gestionar este turno")

    def test_cancelling_reminds_the_customer_who_returns_the_seña(self):
        enable_deposit(self.business, conditions=CONDITIONS)
        appointment = create_appointment(self.ana, self.service, local_dt(future_date(), 10))
        page = self.client.get(reverse("cancel_appointment", args=[appointment.manage_token]))
        self.assertContains(page, "su devolución depende de")
        self.assertContains(page, CONDITIONS)

        send_cancelled(appointment, "https://turnofacil.example/t/x/")
        self.assertIn("su devolución depende de", mail.outbox[0].body)
        self.assertIn(CONDITIONS, mail.outbox[0].body)
        self.assertIn("TurnoFacil no recibe el dinero", mail.outbox[0].body)

    def test_cancellation_email_without_seña_says_nothing_about_it(self):
        appointment = create_appointment(self.ana, self.service, local_dt(future_date(), 10))
        send_cancelled(appointment, "https://turnofacil.example/t/x/")
        self.assertNotIn("seña", mail.outbox[0].body)


class DepositReceivedTests(TestCase):
    def setUp(self):
        self.business = create_business()
        self.ana = create_professional(self.business)
        self.service = create_service(self.business)
        set_active(self.business, "profesional", timezone.now() + timedelta(days=20))
        enable_deposit(self.business)
        self.date = future_date()
        self.appointment = create_appointment(self.ana, self.service, local_dt(self.date, 10))
        self.client.force_login(self.business.owner)

    def mark(self, received="1", appointment=None):
        appointment = appointment or self.appointment
        return self.client.post(
            reverse("appointment_deposit", args=[appointment.pk]), {"received": received}
        )

    def agenda(self):
        return self.client.get(reverse("panel"), {"date": self.date.isoformat()})

    def test_the_agenda_shows_pending_and_the_owner_marks_it_received(self):
        self.assertContains(self.agenda(), "Seña pendiente")
        self.mark()
        self.appointment.refresh_from_db()
        self.assertIsNotNone(self.appointment.deposit_received_at)
        self.assertContains(self.agenda(), "Seña recibida")

    def test_it_can_be_undone_and_never_changes_the_appointment(self):
        self.mark()
        self.mark("0")
        self.appointment.refresh_from_db()
        self.assertIsNone(self.appointment.deposit_received_at)
        self.assertEqual(self.appointment.status, Appointment.CONFIRMED)

    def test_the_customer_sees_that_the_business_recorded_it_never_a_verified_payment(self):
        detail = reverse("appointment_detail", args=[self.appointment.manage_token])
        self.assertContains(self.client.get(detail), "puede cancelarlo según sus condiciones")
        self.mark()
        page = self.client.get(detail)
        self.assertContains(page, "registró que recibió tu seña")
        self.assertNotContains(page, "verificado")

    def test_only_by_post_and_only_the_owner_of_that_business(self):
        url = reverse("appointment_deposit", args=[self.appointment.pk])
        self.assertEqual(self.client.get(url).status_code, 405)
        other = create_business(email="otro@example.com", name="Otro")
        self.client.force_login(other.owner)
        self.assertEqual(self.mark().status_code, 404)
        self.appointment.refresh_from_db()
        self.assertIsNone(self.appointment.deposit_received_at)

    def test_without_a_seña_there_is_no_mark(self):
        self.business.deposit.delete()
        self.assertNotContains(self.agenda(), "Seña pendiente")
