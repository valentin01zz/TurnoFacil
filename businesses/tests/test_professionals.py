from datetime import time

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase
from django.urls import reverse

from businesses.models import Business, Professional, Service, WorkingHours

User = get_user_model()


def create_business(email, name):
    user = User.objects.create_user(email, "correct-horse-battery")
    return Business.objects.create(owner=user, name=name)


def professional_data(name, rows, is_active=True, initial=0):
    """Build the POST payload for the professional form and its hours formset."""
    data = {
        "name": name,
        "hours-TOTAL_FORMS": str(len(rows)),
        "hours-INITIAL_FORMS": str(initial),
        "hours-MIN_NUM_FORMS": "0",
        "hours-MAX_NUM_FORMS": "1000",
    }
    if is_active:
        data["is_active"] = "on"
    for index, row in enumerate(rows):
        for key, value in row.items():
            data[f"hours-{index}-{key}"] = value
    return data


class ProfessionalTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.business = create_business("a@example.com", "Estética Luna")
        cls.other = create_business("b@example.com", "Taller Sur")
        cls.other_professional = Professional.objects.create(business=cls.other, name="Carlos")

    def setUp(self):
        self.client.force_login(self.business.owner)

    def create(self, name, rows):
        return self.client.post(reverse("professional_create"), professional_data(name, rows))

    def test_professional_pages_require_login(self):
        self.client.logout()

        for url in [reverse("professional_list"), reverse("professional_create")]:
            response = self.client.get(url)
            self.assertRedirects(response, f"{reverse('login')}?next={url}")

    def test_create_professional_with_working_hours(self):
        response = self.create(
            "Ana",
            [
                {"weekday": "0", "start_time": "09:00", "end_time": "13:00"},
                {"weekday": "0", "start_time": "14:00", "end_time": "18:00"},
                {"weekday": "2", "start_time": "10:00", "end_time": "16:00"},
                {"weekday": "", "start_time": "", "end_time": ""},
            ],
        )

        self.assertRedirects(response, reverse("professional_list"))
        professional = Professional.objects.get(name="Ana")
        self.assertEqual(professional.business, self.business)
        hours = list(professional.working_hours.values_list("weekday", "start_time", "end_time"))
        self.assertEqual(
            hours,
            [
                (0, time(9), time(13)),
                (0, time(14), time(18)),
                (2, time(10), time(16)),
            ],
        )
        listing = self.client.get(reverse("professional_list"))
        self.assertContains(listing, "Lunes 09:00 a 13:00")
        self.assertContains(listing, "Miércoles 10:00 a 16:00")

    def test_end_time_before_start_is_rejected(self):
        for end in ["09:00", "08:00"]:
            response = self.create(
                "Ana", [{"weekday": "1", "start_time": "09:00", "end_time": end}]
            )
            self.assertEqual(response.status_code, 200, end)
            self.assertContains(response, "La hora de fin tiene que ser posterior a la de inicio.")

        self.assertFalse(Professional.objects.filter(name="Ana").exists())

    def test_overlapping_hours_on_the_same_day_are_rejected(self):
        response = self.create(
            "Ana",
            [
                {"weekday": "3", "start_time": "09:00", "end_time": "13:00"},
                {"weekday": "3", "start_time": "12:00", "end_time": "18:00"},
            ],
        )

        self.assertContains(response, "Hay horarios superpuestos el jueves.")
        self.assertFalse(Professional.objects.filter(name="Ana").exists())

    def test_same_hours_on_different_days_are_allowed(self):
        response = self.create(
            "Ana",
            [
                {"weekday": "3", "start_time": "09:00", "end_time": "13:00"},
                {"weekday": "4", "start_time": "09:00", "end_time": "13:00"},
            ],
        )

        self.assertRedirects(response, reverse("professional_list"))

    def test_incomplete_hours_row_is_rejected(self):
        response = self.create("Ana", [{"weekday": "1", "start_time": "09:00", "end_time": ""}])

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Professional.objects.filter(name="Ana").exists())

    def test_edit_changes_and_removes_hours(self):
        professional = Professional.objects.create(business=self.business, name="Ana")
        monday = WorkingHours.objects.create(
            professional=professional, weekday=0, start_time=time(9), end_time=time(13)
        )
        tuesday = WorkingHours.objects.create(
            professional=professional, weekday=1, start_time=time(9), end_time=time(13)
        )

        response = self.client.post(
            reverse("professional_edit", args=[professional.pk]),
            professional_data(
                "Ana María",
                [
                    {
                        "id": str(monday.pk),
                        "weekday": "0",
                        "start_time": "10:00",
                        "end_time": "14:00",
                    },
                    {
                        "id": str(tuesday.pk),
                        "weekday": "1",
                        "start_time": "09:00",
                        "end_time": "13:00",
                        "DELETE": "on",
                    },
                ],
                initial=2,
            ),
        )

        self.assertRedirects(response, reverse("professional_list"))
        professional.refresh_from_db()
        self.assertEqual(professional.name, "Ana María")
        hours = list(professional.working_hours.values_list("weekday", "start_time", "end_time"))
        self.assertEqual(hours, [(0, time(10), time(14))])

    def test_deactivate_professional(self):
        professional = Professional.objects.create(business=self.business, name="Ana")

        self.client.post(
            reverse("professional_edit", args=[professional.pk]),
            professional_data("Ana", [], is_active=False),
        )

        professional.refresh_from_db()
        self.assertFalse(professional.is_active)
        self.assertContains(self.client.get(reverse("professional_list")), "Inactivo")

    def test_list_shows_only_own_professionals(self):
        Professional.objects.create(business=self.business, name="Ana")

        response = self.client.get(reverse("professional_list"))

        self.assertContains(response, "Ana")
        self.assertNotContains(response, "Carlos")

    def test_other_business_professional_returns_404(self):
        url = reverse("professional_edit", args=[self.other_professional.pk])

        get_response = self.client.get(url)
        post_response = self.client.post(url, professional_data("Hackeado", []))

        self.assertEqual(get_response.status_code, 404)
        self.assertEqual(post_response.status_code, 404)
        self.other_professional.refresh_from_db()
        self.assertEqual(self.other_professional.name, "Carlos")

    def test_cannot_edit_hours_of_another_professional(self):
        own = Professional.objects.create(business=self.business, name="Ana")
        foreign_hours = WorkingHours.objects.create(
            professional=self.other_professional, weekday=0, start_time=time(9), end_time=time(13)
        )

        response = self.client.post(
            reverse("professional_edit", args=[own.pk]),
            professional_data(
                "Ana",
                [
                    {
                        "id": str(foreign_hours.pk),
                        "weekday": "0",
                        "start_time": "06:00",
                        "end_time": "07:00",
                    }
                ],
                initial=1,
            ),
        )

        # Django skips formset rows whose id is outside the professional's own hours.
        self.assertRedirects(response, reverse("professional_list"))
        foreign_hours.refresh_from_db()
        self.assertEqual(foreign_hours.start_time, time(9))
        self.assertEqual(foreign_hours.professional, self.other_professional)
        self.assertFalse(own.working_hours.exists())

    def test_database_rejects_end_before_start(self):
        professional = Professional.objects.create(business=self.business, name="Ana")

        with self.assertRaises(IntegrityError):
            WorkingHours.objects.create(
                professional=professional, weekday=0, start_time=time(13), end_time=time(9)
            )


class BookingPageProfessionalsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.business = create_business("a@example.com", "Estética Luna")

    def booking_page(self):
        return self.client.get(reverse("booking_page", args=[self.business.slug]))

    def test_services_without_professionals_is_not_taking_bookings(self):
        Service.objects.create(business=self.business, name="Manicura", duration_minutes=40)

        self.assertContains(self.booking_page(), "todavía no está tomando reservas")

    def test_professionals_without_services_is_not_taking_bookings(self):
        Professional.objects.create(business=self.business, name="Ana")

        self.assertContains(self.booking_page(), "todavía no está tomando reservas")

    def test_single_professional_is_not_offered_as_a_choice(self):
        Service.objects.create(business=self.business, name="Manicura", duration_minutes=40)
        Professional.objects.create(business=self.business, name="Ana")

        response = self.booking_page()

        self.assertContains(response, "Manicura")
        self.assertNotContains(response, "Profesionales")
        self.assertNotContains(response, "Ana")

    def test_several_professionals_are_offered_as_choices(self):
        Service.objects.create(business=self.business, name="Manicura", duration_minutes=40)
        Professional.objects.create(business=self.business, name="Ana")
        Professional.objects.create(business=self.business, name="Bruno")
        Professional.objects.create(business=self.business, name="Ciro", is_active=False)

        response = self.booking_page()

        self.assertContains(response, "Ana")
        self.assertContains(response, "Bruno")
        self.assertNotContains(response, "Ciro")
