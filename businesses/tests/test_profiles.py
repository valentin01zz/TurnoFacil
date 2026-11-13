"""Separate agendas per professional (HU-37, ADR-0006): profiles with a PIN inside one account."""

from datetime import timedelta

from django.core import mail
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
from businesses.models import Business, TimeOff
from businesses.profile_views import reset_token
from businesses.profiles import SESSION_KEY, hash_pin, pin_matches, pin_problem

OWNER_PIN = "2580"
MARIA_PIN = "7391"
MARIANO_PIN = "4826"


def turn_on(business):
    Business.objects.filter(pk=business.pk).update(
        separate_agendas=True, owner_pin=hash_pin(OWNER_PIN)
    )
    business.refresh_from_db()


def set_pin(professional, pin):
    professional.pin = hash_pin(pin)
    professional.save(update_fields=["pin"])


class PinRulesTests(TestCase):
    def test_pin_rules(self):
        for pin in ("123", "1234567", "12a4", "", "1111", "1234", "654321"):
            with self.subTest(pin=pin):
                self.assertIsNotNone(pin_problem(pin))
        for pin in ("2580", "73914", "482613"):
            self.assertIsNone(pin_problem(pin))

    def test_pins_are_stored_hashed(self):
        hashed = hash_pin("2580")
        self.assertNotIn("2580", hashed)
        self.assertTrue(pin_matches("2580", hashed))
        self.assertFalse(pin_matches("2581", hashed))
        self.assertFalse(pin_matches("2580", ""))


class ProfilesTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.business = create_business(name="Consultorio Pies")
        cls.maria = create_professional(cls.business, name="María")
        cls.mariano = create_professional(cls.business, name="Mariano")
        cls.service = create_service(cls.business, name="Consulta", duration=30)
        cls.date = future_date()

    def setUp(self):
        turn_on(self.business)
        set_pin(self.maria, MARIA_PIN)
        set_pin(self.mariano, MARIANO_PIN)
        self.client.force_login(self.business.owner)
        self.maria_appt = create_appointment(self.maria, self.service, local_dt(self.date, 10))
        Appointment.objects.filter(pk=self.maria_appt.pk).update(customer_name="Paciente de María")
        self.mariano_appt = create_appointment(self.mariano, self.service, local_dt(self.date, 10))
        Appointment.objects.filter(pk=self.mariano_appt.pk).update(
            customer_name="Paciente de Mariano"
        )

    def choose(self, profile, pin, next_url=""):
        return self.client.post(
            reverse("choose_profile"), {"profile": profile, "pin": pin, "next": next_url}
        )

    def as_maria(self):
        response = self.choose(str(self.maria.pk), MARIA_PIN)
        self.assertRedirects(response, reverse("panel"), fetch_redirect_response=False)

    def as_owner(self):
        response = self.choose("owner", OWNER_PIN)
        self.assertRedirects(response, reverse("panel"), fetch_redirect_response=False)

    def agenda(self, **params):
        return self.client.get(reverse("panel"), {"date": self.date.isoformat(), **params})


class ChoosingTests(ProfilesTestCase):
    def test_option_off_keeps_the_panel_as_before(self):
        Business.objects.filter(pk=self.business.pk).update(separate_agendas=False)
        response = self.agenda()
        self.assertContains(response, "Paciente de María")
        self.assertContains(response, "Paciente de Mariano")
        self.assertRedirects(
            self.client.get(reverse("choose_profile")),
            reverse("panel"),
            fetch_redirect_response=False,
        )

    def test_every_panel_page_asks_for_a_profile_first(self):
        for name in ("panel", "reports", "time_off_list", "service_list", "plans"):
            with self.subTest(page=name):
                response = self.client.get(reverse(name))
                self.assertEqual(response.status_code, 302)
                self.assertTrue(response["Location"].startswith(reverse("choose_profile")))

    def test_picker_lists_owner_and_professionals_and_returns_to_next(self):
        page = self.client.get(reverse("choose_profile"))
        self.assertContains(page, "Dueño")
        self.assertContains(page, "María")
        self.assertNotContains(page, "Paciente de")
        response = self.choose(str(self.maria.pk), MARIA_PIN, next_url="/panel/reports/")
        self.assertRedirects(response, "/panel/reports/", fetch_redirect_response=False)

    def test_outside_next_urls_are_ignored(self):
        response = self.choose("owner", OWNER_PIN, next_url="https://evil.example/")
        self.assertRedirects(response, reverse("panel"), fetch_redirect_response=False)

    def test_wrong_pin_or_foreign_profile_is_rejected(self):
        other = create_professional(create_business("b@example.com", "Otro"), name="Zoe")
        set_pin(other, "9999")
        for profile, pin in (
            ("owner", "0000"),
            (str(self.maria.pk), MARIANO_PIN),
            (str(other.pk), "9999"),
        ):
            with self.subTest(profile=profile):
                response = self.choose(profile, pin)
                self.assertEqual(response.status_code, 200)
        self.assertNotIn(SESSION_KEY, self.client.session)

    def test_professional_without_pin_or_inactive_cannot_enter(self):
        nopin = create_professional(self.business, name="Nuevo")
        self.mariano.is_active = False
        self.mariano.save()
        self.assertContains(self.client.get(reverse("choose_profile")), "Sin PIN")
        self.assertEqual(self.choose(str(nopin.pk), "").status_code, 200)
        self.assertEqual(self.choose(str(self.mariano.pk), MARIANO_PIN).status_code, 200)
        self.assertNotIn(SESSION_KEY, self.client.session)

    def test_five_wrong_pins_lock_that_profile(self):
        for _ in range(5):
            self.choose(str(self.maria.pk), "0000")
        response = self.choose(str(self.maria.pk), MARIA_PIN)
        self.assertContains(response, "Demasiados intentos")
        self.assertNotIn(SESSION_KEY, self.client.session)
        self.as_owner()  # another profile is not locked

    def test_switching_profile_closes_it(self):
        self.as_maria()
        self.client.post(reverse("switch_profile"))
        self.assertEqual(self.agenda().status_code, 302)

    def test_new_pin_closes_open_sessions(self):
        self.as_maria()
        self.maria.pin = hash_pin("1593")
        self.maria.pin_version += 1
        self.maria.save()
        self.assertEqual(self.agenda().status_code, 302)


class ProfessionalScopeTests(ProfilesTestCase):
    def setUp(self):
        super().setUp()
        self.as_maria()

    def test_agenda_shows_only_their_appointments_even_with_another_filter(self):
        for params in ({}, {"professional": self.mariano.pk}):
            with self.subTest(params=params):
                response = self.agenda(**params)
                self.assertContains(response, "Paciente de María")
                self.assertNotContains(response, "Paciente de Mariano")

    def test_header_has_their_own_tabs(self):
        response = self.agenda()
        self.assertContains(response, "Mi agenda")
        self.assertContains(response, "Cambiar mi PIN")
        self.assertNotContains(response, reverse("service_list"))
        self.assertNotContains(response, reverse("plans"))

    def test_owner_pages_are_closed(self):
        names = [
            ("business_edit", []),
            ("deposit_settings", []),
            ("agenda_settings", []),
            ("service_list", []),
            ("service_create", []),
            ("professional_list", []),
            ("professional_create", []),
            ("professional_edit", [self.maria.pk]),
            ("plans", []),
        ]
        for name, args in names:
            with self.subTest(page=name):
                response = self.client.get(reverse(name, args=args))
                self.assertRedirects(response, reverse("panel"), fetch_redirect_response=False)

    def test_another_professionals_appointment_cannot_be_touched(self):
        pk = self.mariano_appt.pk
        requests = [
            ("get", "appointment_reschedule", {}),
            ("post", "appointment_reschedule", {"professional": self.maria.pk}),
            ("get", "appointment_cancel", {}),
            ("post", "appointment_cancel", {}),
            ("post", "appointment_attendance", {"attendance": "attended"}),
        ]
        for method, name, data in requests:
            with self.subTest(request=(method, name)):
                response = getattr(self.client, method)(reverse(name, args=[pk]), data)
                self.assertEqual(response.status_code, 404)
        self.mariano_appt.refresh_from_db()
        self.assertTrue(self.mariano_appt.is_confirmed)
        self.assertEqual(self.mariano_appt.professional, self.mariano)

    def test_their_own_appointment_can_be_cancelled(self):
        self.client.post(reverse("appointment_cancel", args=[self.maria_appt.pk]))
        self.maria_appt.refresh_from_db()
        self.assertFalse(self.maria_appt.is_confirmed)

    def test_cannot_book_or_move_into_another_agenda(self):
        data = {
            "customer_name": "Forzado",
            "customer_phone": "11 4444 4444",
            "customer_email": "",
            "service": self.service.pk,
            "professional": self.mariano.pk,
            "date": self.date.isoformat(),
            "time": "15:00",
        }
        self.assertEqual(self.client.post(reverse("appointment_create"), data).status_code, 200)
        self.assertFalse(Appointment.objects.filter(customer_name="Forzado").exists())
        data["professional"] = self.maria.pk
        self.client.post(reverse("appointment_create"), data)
        self.assertEqual(Appointment.objects.get(customer_name="Forzado").professional, self.maria)

    def test_time_off_only_for_themselves(self):
        base = {"start_date": self.date.isoformat(), "reason": ""}
        self.client.post(reverse("time_off_list"), {**base, "professional": ""})
        self.client.post(reverse("time_off_list"), {**base, "professional": self.mariano.pk})
        self.assertFalse(TimeOff.objects.exists())
        self.client.post(reverse("time_off_list"), {**base, "professional": self.maria.pk})
        self.assertEqual(TimeOff.objects.get().professional, self.maria)

    def test_time_off_of_others_is_hidden_or_read_only(self):
        start = timezone.now() + timedelta(days=2)
        holiday = TimeOff.objects.create(
            business=self.business, start_at=start, end_at=start + timedelta(days=1)
        )
        theirs = TimeOff.objects.create(
            business=self.business,
            professional=self.mariano,
            start_at=start,
            end_at=start + timedelta(hours=2),
            reason="Turno de Mariano",
        )
        page = self.client.get(reverse("time_off_list"))
        self.assertContains(page, "Todo el negocio")
        self.assertNotContains(page, "Turno de Mariano")
        self.assertNotContains(page, reverse("time_off_delete", args=[holiday.pk]))
        for target in (holiday, theirs):
            with self.subTest(time_off=target.pk):
                response = self.client.post(reverse("time_off_delete", args=[target.pk]))
                self.assertEqual(response.status_code, 404)
                response = self.client.get(reverse("time_off_appointments", args=[target.pk]))
                self.assertEqual(response.status_code, 404)
        self.assertEqual(TimeOff.objects.count(), 2)

    def test_reports_and_export_only_have_their_figures(self):
        past = timezone.localdate() - timedelta(days=1)
        create_appointment(self.maria, self.service, local_dt(past, 9))
        other = create_appointment(self.mariano, self.service, local_dt(past, 9))
        Appointment.objects.filter(pk=other.pk).update(customer_name="Paciente pasado de Mariano")
        response = self.client.get(
            reverse("reports"), {"professional": self.mariano.pk, "period": "month"}
        )
        self.assertEqual(response.context["professional"], self.maria)
        export = self.client.get(reverse("reports_export"), {"professional": self.mariano.pk})
        body = export.content.decode("utf-8")
        self.assertNotIn("Mariano", body)

    def test_change_my_pin(self):
        url = reverse("my_pin")
        wrong = {"current": "0000", "pin": "1593", "pin_again": "1593"}
        self.assertEqual(self.client.post(url, wrong).status_code, 200)
        right = {"current": MARIA_PIN, "pin": "1593", "pin_again": "1593"}
        self.assertRedirects(self.client.post(url, right), reverse("panel"))
        self.maria.refresh_from_db()
        self.assertTrue(pin_matches("1593", self.maria.pin))
        self.assertEqual(self.agenda().status_code, 200)  # this session stays open


class OwnerTests(ProfilesTestCase):
    def test_owner_sees_everything(self):
        self.as_owner()
        response = self.agenda()
        self.assertContains(response, "Paciente de María")
        self.assertContains(response, "Paciente de Mariano")
        for name in ("service_list", "professional_list", "agenda_settings", "plans"):
            with self.subTest(page=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 200)

    def test_owner_sets_a_professional_pin_which_closes_their_sessions(self):
        self.as_owner()
        version = self.maria.pin_version
        hours = self.maria.working_hours.all()
        data = {
            "name": "María",
            "is_active": "on",
            "pin": "3698",
            "pin_again": "3698",
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
        self.assertTrue(pin_matches("3698", self.maria.pin))
        self.assertEqual(self.maria.pin_version, version + 1)

    def test_turning_on_needs_an_owner_pin_and_keeps_the_owner_in(self):
        Business.objects.filter(pk=self.business.pk).update(separate_agendas=False, owner_pin="")
        url = reverse("agenda_settings")
        self.assertEqual(self.client.post(url, {"separate_agendas": "on"}).status_code, 200)
        self.business.refresh_from_db()
        self.assertFalse(self.business.separate_agendas)
        response = self.client.post(
            url, {"separate_agendas": "on", "pin": "2580", "pin_again": "2580"}
        )
        self.assertRedirects(response, url, fetch_redirect_response=False)
        self.business.refresh_from_db()
        self.assertTrue(self.business.separate_agendas)
        self.assertEqual(self.agenda().status_code, 200)  # the owner stays in

    def test_turning_off_goes_back_to_one_agenda(self):
        self.as_owner()
        self.client.post(reverse("agenda_settings"), {})
        self.business.refresh_from_db()
        self.assertFalse(self.business.separate_agendas)


class OwnerPinRecoveryTests(ProfilesTestCase):
    def test_link_goes_to_the_account_email_and_works_once(self):
        response = self.client.post(reverse("owner_pin_forgot"))
        self.assertRedirects(response, reverse("choose_profile"), fetch_redirect_response=False)
        [message] = mail.outbox
        self.assertEqual(message.to, [self.business.owner.email])
        link = reverse("owner_pin_reset", args=[reset_token(self.business)])
        self.assertIn(link, message.body)

        response = self.client.post(link, {"pin": "9517", "pin_again": "9517"})
        self.assertRedirects(response, reverse("panel"), fetch_redirect_response=False)
        self.business.refresh_from_db()
        self.assertTrue(pin_matches("9517", self.business.owner_pin))
        self.assertEqual(self.agenda().status_code, 200)

        again = self.client.post(link, {"pin": "7539", "pin_again": "7539"})
        self.assertRedirects(again, reverse("choose_profile"), fetch_redirect_response=False)
        self.business.refresh_from_db()
        self.assertTrue(pin_matches("9517", self.business.owner_pin))

    def test_altered_link_is_rejected(self):
        response = self.client.get(reverse("owner_pin_reset", args=["not-a-token"]))
        self.assertRedirects(response, reverse("choose_profile"), fetch_redirect_response=False)

    def test_recovery_emails_are_limited(self):
        for _ in range(5):
            self.client.post(reverse("owner_pin_forgot"))
        self.assertEqual(len(mail.outbox), 3)


class HeaderOutsideThePanelTests(ProfilesTestCase):
    def test_without_a_profile_the_header_shows_no_tabs(self):
        response = self.client.get(reverse("choose_profile"))
        self.assertNotContains(response, 'aria-label="Panel"')
