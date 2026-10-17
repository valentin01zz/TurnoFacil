from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase
from django.urls import reverse

from businesses.models import Business, Service

User = get_user_model()


def create_business(email, name):
    user = User.objects.create_user(email, "correct-horse-battery")
    return Business.objects.create(owner=user, name=name)


class ServiceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.business = create_business("a@example.com", "Estética Luna")
        cls.other = create_business("b@example.com", "Taller Sur")
        cls.other_service = Service.objects.create(
            business=cls.other, name="Cambio de aceite", duration_minutes=40
        )

    def setUp(self):
        self.client.force_login(self.business.owner)

    def booking_page(self):
        return self.client.get(reverse("booking_page", args=[self.business.slug]))

    def test_service_pages_require_login(self):
        self.client.logout()

        for url in [reverse("service_list"), reverse("service_create")]:
            response = self.client.get(url)
            self.assertRedirects(response, f"{reverse('login')}?next={url}")

    def test_create_service_shows_it_on_the_public_page(self):
        response = self.client.post(
            reverse("service_create"),
            {"name": "Limpieza facial", "duration_minutes": 50, "is_active": "on"},
        )

        self.assertRedirects(response, reverse("service_list"))
        service = Service.objects.get(name="Limpieza facial")
        self.assertEqual(service.business, self.business)
        self.assertEqual(service.duration_minutes, 50)
        self.assertContains(self.booking_page(), "Limpieza facial")

    def test_invalid_durations_are_rejected(self):
        for duration in ["", "0", "-5", "abc"]:
            response = self.client.post(
                reverse("service_create"),
                {"name": "Masaje", "duration_minutes": duration, "is_active": "on"},
            )
            self.assertEqual(response.status_code, 200, duration)
            self.assertTrue(response.context["form"].errors["duration_minutes"], duration)

        self.assertFalse(Service.objects.filter(name="Masaje").exists())

    def test_missing_name_is_rejected(self):
        response = self.client.post(
            reverse("service_create"), {"name": "  ", "duration_minutes": 30, "is_active": "on"}
        )

        self.assertTrue(response.context["form"].errors["name"])
        self.assertEqual(self.business.services.count(), 0)

    def test_edit_service_updates_the_public_page(self):
        service = Service.objects.create(
            business=self.business, name="Depilación", duration_minutes=30
        )

        response = self.client.post(
            reverse("service_edit", args=[service.pk]),
            {"name": "Depilación definitiva", "duration_minutes": 45, "is_active": "on"},
        )

        self.assertRedirects(response, reverse("service_list"))
        service.refresh_from_db()
        self.assertEqual(service.name, "Depilación definitiva")
        self.assertEqual(service.duration_minutes, 45)
        self.assertContains(self.booking_page(), "Depilación definitiva")

    def test_deactivated_service_leaves_the_public_page(self):
        service = Service.objects.create(
            business=self.business, name="Depilación", duration_minutes=30
        )
        Service.objects.create(business=self.business, name="Manicura", duration_minutes=40)

        self.client.post(
            reverse("service_edit", args=[service.pk]),
            {"name": "Depilación", "duration_minutes": 30},
        )

        service.refresh_from_db()
        self.assertFalse(service.is_active)
        page = self.booking_page()
        self.assertNotContains(page, "Depilación")
        self.assertContains(page, "Manicura")
        self.assertContains(self.client.get(reverse("service_list")), "Inactivo")

    def test_public_page_without_active_services_is_not_taking_bookings(self):
        Service.objects.create(
            business=self.business, name="Depilación", duration_minutes=30, is_active=False
        )

        self.assertContains(self.booking_page(), "todavía no está tomando reservas")

    def test_list_shows_only_own_services(self):
        Service.objects.create(business=self.business, name="Manicura", duration_minutes=40)

        response = self.client.get(reverse("service_list"))

        self.assertContains(response, "Manicura")
        self.assertNotContains(response, "Cambio de aceite")

    def test_other_business_service_returns_404(self):
        url = reverse("service_edit", args=[self.other_service.pk])

        get_response = self.client.get(url)
        post_response = self.client.post(
            url, {"name": "Hackeado", "duration_minutes": 1, "is_active": "on"}
        )

        self.assertEqual(get_response.status_code, 404)
        self.assertEqual(post_response.status_code, 404)
        self.other_service.refresh_from_db()
        self.assertEqual(self.other_service.name, "Cambio de aceite")

    def test_database_rejects_zero_duration(self):
        with self.assertRaises(IntegrityError):
            Service.objects.create(business=self.business, name="Roto", duration_minutes=0)
