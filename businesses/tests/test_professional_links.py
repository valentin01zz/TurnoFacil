"""Professional links and notices (HU-37 part 2, ADR-0006): /b/<business>/<professional>/ and
appointment notices to each professional's confirmed email."""

from django.core import mail
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from bookings.models import Appointment
from bookings.tests.helpers import (
    create_business,
    create_professional,
    create_service,
    future_date,
    local_dt,
    sent_to,
)
from businesses.models import Business, Professional
from businesses.professional_email import make_token
from businesses.profiles import hash_pin

OWNER = "a@example.com"


class SlugTests(TestCase):
    def test_slug_from_the_name_unique_per_business_and_never_reserved(self):
        business = create_business()
        first = create_professional(business, name="María José")
        second = create_professional(business, name="María José")
        book = create_professional(business, name="Book")
        self.assertEqual(first.slug, "maria-jose")
        self.assertEqual(second.slug, "maria-jose-2")
        self.assertEqual(book.slug, "book-2")
        other = create_professional(create_business("b@example.com", "Otro"), name="María José")
        self.assertEqual(other.slug, "maria-jose")

    def test_renaming_keeps_the_link(self):
        professional = create_professional(create_business(), name="Ana")
        professional.name = "Ana Laura"
        professional.save()
        self.assertEqual(Professional.objects.get(pk=professional.pk).slug, "ana")


class PersonalLinkTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.business = create_business(OWNER, name="Consultorio Pies")
        cls.maria = create_professional(cls.business, name="María")
        cls.mariano = create_professional(cls.business, name="Mariano")
        cls.service = create_service(cls.business, name="Consulta", duration=30)
        cls.date = future_date()

    def url(self, professional=None, slug=None):
        return reverse(
            "professional_booking_page",
            args=[self.business.slug, slug or (professional or self.maria).slug],
        )

    def book_data(self, professional, hour=10):
        return {
            "service": self.service.pk,
            "professional": professional.pk,
            "date": self.date.isoformat(),
            "start_at": local_dt(self.date, hour).isoformat(),
            "customer_name": "Laura",
            "customer_phone": "11 5555 1234",
            "customer_email": "laura@example.com",
        }

    def test_personal_page_shows_only_that_professional(self):
        response = self.client.get(self.url())
        self.assertContains(response, "Turnos con María")
        self.assertNotContains(response, "Mariano")
        self.assertContains(
            response, reverse("professional_book", args=[self.business.slug, self.maria.slug])
        )

    def test_general_link_still_offers_everyone(self):
        response = self.client.get(reverse("booking_page", args=[self.business.slug]))
        self.assertContains(response, "María")
        self.assertContains(response, "Mariano")

    def test_unknown_inactive_or_foreign_professional_is_not_found(self):
        foreign = create_professional(create_business("b@example.com", "Otro"), name="Zoe")
        inactive = create_professional(self.business, name="Inactiva")
        inactive.is_active = False
        inactive.save()
        for slug in ("nadie", inactive.slug, foreign.slug):
            with self.subTest(slug=slug):
                self.assertEqual(self.client.get(self.url(slug=slug)).status_code, 404)

    def test_booking_from_the_personal_link(self):
        book_url = reverse("professional_book", args=[self.business.slug, self.maria.slug])
        response = self.client.post(book_url, self.book_data(self.maria))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Appointment.objects.get().professional, self.maria)

    def test_a_forged_professional_on_a_personal_link_books_nothing(self):
        book_url = reverse("professional_book", args=[self.business.slug, self.maria.slug])
        response = self.client.post(book_url, self.book_data(self.mariano))
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Appointment.objects.exists())

    def test_month_navigation_stays_on_the_personal_link(self):
        response = self.client.get(
            self.url(), {"service": self.service.pk, "date": self.date.isoformat()}
        )
        links = [
            response.context["strip"][key]
            for key in ("previous_url", "next_url")
            if response.context["strip"][key]
        ]
        for link in links:
            self.assertTrue(link.startswith(self.url()), link)


class ProfessionalEmailTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.business = create_business(OWNER, name="Consultorio Pies")
        cls.maria = create_professional(cls.business, name="María")

    def setUp(self):
        self.client.force_login(self.business.owner)

    def save_email(self, email):
        hours = list(self.maria.working_hours.all())
        data = {
            "name": "María",
            "is_active": "on",
            "email": email,
            "hours-TOTAL_FORMS": str(len(hours)),
            "hours-INITIAL_FORMS": str(len(hours)),
            "hours-MIN_NUM_FORMS": "0",
            "hours-MAX_NUM_FORMS": "50",
        }
        for i, row in enumerate(hours):
            data.update(
                {
                    f"hours-{i}-id": row.pk,
                    f"hours-{i}-weekday": row.weekday,
                    f"hours-{i}-start_time": row.start_time.strftime("%H:%M"),
                    f"hours-{i}-end_time": row.end_time.strftime("%H:%M"),
                }
            )
        response = self.client.post(reverse("professional_edit", args=[self.maria.pk]), data)
        self.assertRedirects(response, reverse("professional_list"))
        self.maria.refresh_from_db()

    def test_new_email_gets_a_confirmation_link(self):
        self.save_email("Maria@Example.com")
        self.assertEqual(self.maria.email, "maria@example.com")
        self.assertIsNone(self.maria.email_verified_at)
        [message] = sent_to("maria@example.com")
        link = reverse("confirm_professional_email", args=[make_token(self.maria)])
        self.assertIn(link, message.body)
        self.assertNotIn("Laura", message.body)  # no customer data before confirming

        self.client.logout()  # opened from the professional's own phone
        response = self.client.get(link)
        self.assertContains(response, "Confirmamos tu email")
        self.maria.refresh_from_db()
        self.assertTrue(self.maria.email_confirmed)

    def test_changing_the_email_asks_again_and_the_old_link_dies(self):
        self.save_email("maria@example.com")
        old_link = reverse("confirm_professional_email", args=[make_token(self.maria)])
        self.client.get(old_link)
        self.save_email("otra@example.com")
        self.assertIsNone(self.maria.email_verified_at)
        response = self.client.get(old_link)
        self.assertEqual(response.status_code, 400)
        self.maria.refresh_from_db()
        self.assertFalse(self.maria.email_confirmed)

    def test_same_email_sends_nothing_again(self):
        self.save_email("maria@example.com")
        mail.outbox.clear()
        self.save_email("maria@example.com")
        self.assertEqual(mail.outbox, [])

    def test_altered_link_is_rejected(self):
        response = self.client.get(reverse("confirm_professional_email", args=["nope"]))
        self.assertContains(response, "Este link no sirve", status_code=400)


class NoticeRecipientTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.business = create_business(OWNER, name="Consultorio Pies")
        cls.maria = create_professional(cls.business, name="María")
        cls.service = create_service(cls.business, name="Consulta", duration=30)
        cls.date = future_date()

    def book(self):
        self.client.post(
            reverse("book", args=[self.business.slug]),
            {
                "service": self.service.pk,
                "professional": self.maria.pk,
                "date": self.date.isoformat(),
                "start_at": local_dt(self.date, 10).isoformat(),
                "customer_name": "Laura",
                "customer_phone": "11 5555 1234",
                "customer_email": "laura@example.com",
            },
        )

    def setup(self, separate, email="maria@example.com", confirmed=True):
        Business.objects.filter(pk=self.business.pk).update(
            separate_agendas=separate, owner_pin=hash_pin("2580")
        )
        Professional.objects.filter(pk=self.maria.pk).update(
            email=email, email_verified_at=timezone.now() if confirmed else None
        )

    def test_separate_agendas_and_confirmed_email_go_to_the_professional(self):
        self.setup(separate=True)
        self.book()
        self.assertEqual(len(sent_to("maria@example.com")), 1)
        self.assertEqual(sent_to(OWNER), [])

    def test_unconfirmed_email_goes_to_the_owner(self):
        self.setup(separate=True, confirmed=False)
        self.book()
        self.assertEqual(sent_to("maria@example.com"), [])
        self.assertEqual(len(sent_to(OWNER)), 1)

    def test_one_shared_agenda_goes_to_the_owner(self):
        self.setup(separate=False)
        self.book()
        self.assertEqual(sent_to("maria@example.com"), [])
        self.assertEqual(len(sent_to(OWNER)), 1)


class PanelLinkTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.business = create_business(OWNER, name="Consultorio Pies")
        cls.maria = create_professional(cls.business, name="María")
        create_professional(cls.business, name="Mariano")

    def setUp(self):
        Business.objects.filter(pk=self.business.pk).update(
            separate_agendas=True, owner_pin=hash_pin("2580")
        )
        self.maria.pin = hash_pin("7391")
        self.maria.save()
        self.client.force_login(self.business.owner)

    def test_a_professional_shares_their_own_link(self):
        self.client.post(reverse("choose_profile"), {"profile": self.maria.pk, "pin": "7391"})
        response = self.client.get(reverse("panel"))
        own = reverse("professional_booking_page", args=[self.business.slug, self.maria.slug])
        self.assertEqual(response.context["booking_url"], f"http://testserver{own}")

    def test_owner_sees_every_professional_link(self):
        self.client.post(reverse("choose_profile"), {"profile": "owner", "pin": "2580"})
        response = self.client.get(reverse("professional_list"))
        self.assertContains(response, f"/b/{self.business.slug}/maria/")
        self.assertContains(response, f"/b/{self.business.slug}/mariano/")
