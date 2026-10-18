from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from bookings.models import Appointment
from bookings.tests.helpers import (
    create_appointment,
    create_business,
    create_professional,
    create_service,
    future_date,
    local_dt,
)


class AgendaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.business = create_business()
        cls.ana = create_professional(cls.business, name="Ana")
        cls.bruno = create_professional(cls.business, name="Bruno")
        cls.service = create_service(cls.business, name="Limpieza facial", duration=50)
        cls.date = future_date()

        cls.morning = create_appointment(cls.ana, cls.service, local_dt(cls.date, 10, 0))
        cls.morning.customer_name = "Laura Gómez"
        cls.morning.customer_phone = "11 5555 1234"
        cls.morning.save()
        cls.bruno_turn = create_appointment(cls.bruno, cls.service, local_dt(cls.date, 9, 0))
        cls.bruno_turn.customer_name = "Marta Ruiz"
        cls.bruno_turn.save()

        other_day = create_appointment(
            cls.ana, cls.service, local_dt(cls.date + timedelta(days=1), 10, 0)
        )
        other_day.customer_name = "Otro Día"
        other_day.save()
        cancelled = create_appointment(
            cls.ana, cls.service, local_dt(cls.date, 15, 0), status=Appointment.CANCELLED
        )
        cancelled.customer_name = "Turno Cancelado"
        cancelled.save()

        other_business = create_business("b@example.com", "Taller Sur")
        carlos = create_professional(other_business, name="Carlos")
        foreign = create_appointment(
            carlos, create_service(other_business, name="Aceite"), local_dt(cls.date, 10, 0)
        )
        foreign.customer_name = "Cliente Ajeno"
        foreign.save()
        cls.carlos = carlos

    def setUp(self):
        self.client.force_login(self.business.owner)

    def agenda(self, **params):
        return self.client.get(reverse("panel"), params)

    def test_day_shows_its_appointments_with_details(self):
        response = self.agenda(date=self.date.isoformat())

        self.assertContains(response, "10:00–10:50")
        self.assertContains(response, "Laura Gómez")
        self.assertContains(response, "11 5555 1234")
        self.assertContains(response, "Limpieza facial · Ana")
        self.assertContains(response, "Marta Ruiz")
        self.assertEqual(list(response.context["appointments"]), [self.bruno_turn, self.morning])

    def test_other_days_cancelled_and_other_business_are_not_shown(self):
        response = self.agenda(date=self.date.isoformat())

        self.assertNotContains(response, "Otro Día")
        self.assertNotContains(response, "Turno Cancelado")
        self.assertNotContains(response, "Cliente Ajeno")

    def test_filter_by_professional(self):
        response = self.agenda(date=self.date.isoformat(), professional=self.ana.pk)

        self.assertContains(response, "Laura Gómez")
        self.assertNotContains(response, "Marta Ruiz")

    def test_professional_of_another_business_is_ignored(self):
        response = self.agenda(date=self.date.isoformat(), professional=self.carlos.pk)

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Cliente Ajeno")
        self.assertIsNone(response.context["professional"])

    def test_defaults_to_today(self):
        response = self.agenda()

        self.assertEqual(response.context["date"], timezone.localdate())
        self.assertContains(response, ">Hoy<")
        self.assertContains(response, f'value="{timezone.localdate().isoformat()}"')

    def test_invalid_date_falls_back_to_today(self):
        response = self.agenda(date="not-a-date")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["date"], timezone.localdate())

    def test_empty_day_says_so(self):
        response = self.agenda(date=(self.date + timedelta(days=2)).isoformat())

        self.assertContains(response, "No hay turnos para este día.")

    def test_day_navigation_links_keep_the_filter(self):
        response = self.agenda(date=self.date.isoformat(), professional=self.ana.pk)

        previous_day = (self.date - timedelta(days=1)).isoformat()
        next_day = (self.date + timedelta(days=1)).isoformat()
        self.assertContains(response, f"?date={previous_day}&amp;professional={self.ana.pk}")
        self.assertContains(response, f"?date={next_day}&amp;professional={self.ana.pk}")

    def test_single_professional_hides_the_professional_column_and_filter(self):
        Appointment.objects.filter(professional=self.bruno).delete()
        self.bruno.delete()

        response = self.agenda(date=self.date.isoformat())

        self.assertContains(response, "Laura Gómez")
        self.assertNotContains(response, "Limpieza facial · Ana")
        self.assertNotContains(response, 'name="professional"')
