"""Time off (HU-13): days or hours when the business or one professional takes no bookings."""

from datetime import time, timedelta

from django.core import mail
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from billing.tests.helpers import end_trial
from bookings.availability import available_slots, is_covered
from bookings.booking_calendar import month_strip
from bookings.models import Appointment
from bookings.tests.helpers import (
    create_appointment,
    create_business,
    create_professional,
    create_service,
    future_date,
    local_dt,
)
from businesses.forms import MAX_TIME_OFF_DAYS
from businesses.models import TimeOff


def block(business, start_at, end_at, professional=None, reason=""):
    return TimeOff.objects.create(
        business=business,
        professional=professional,
        start_at=start_at,
        end_at=end_at,
        reason=reason,
    )


def whole_day(business, date, professional=None):
    return block(business, local_dt(date, 0), local_dt(date + timedelta(days=1), 0), professional)


def strip_day(strip, date):
    return next(day for day in strip["days"] if day["date"] == date)


class CoverageTests(TestCase):
    def test_ranges_cover_only_without_gaps(self):
        date = future_date()
        nine, one, two, six = (local_dt(date, h) for h in (9, 13, 14, 18))
        self.assertTrue(is_covered(nine, six, [(nine, two), (one, six)]))
        self.assertFalse(is_covered(nine, six, [(nine, one), (two, six)]))
        self.assertFalse(is_covered(nine, six, [(one, six)]))
        self.assertFalse(is_covered(nine, six, []))


class AvailabilityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.business = create_business()
        cls.ana = create_professional(cls.business, name="Ana")
        cls.bruno = create_professional(cls.business, name="Bruno")
        cls.service = create_service(cls.business, duration=50)
        cls.date = future_date()

    def test_business_wide_day_leaves_nobody_free(self):
        whole_day(self.business, self.date)
        self.assertEqual(available_slots(self.ana, self.service, self.date), [])
        self.assertEqual(available_slots(self.bruno, self.service, self.date), [])
        self.assertNotEqual(available_slots(self.ana, self.service, self.date + timedelta(1)), [])

    def test_professional_block_leaves_the_others_free(self):
        whole_day(self.business, self.date, self.ana)
        self.assertEqual(available_slots(self.ana, self.service, self.date), [])
        self.assertNotEqual(available_slots(self.bruno, self.service, self.date), [])

    def test_hour_block_removes_only_overlapping_times(self):
        block(self.business, local_dt(self.date, 10), local_dt(self.date, 12), self.ana)
        starts = {
            timezone.localtime(s).time() for s in available_slots(self.ana, self.service, self.date)
        }
        self.assertIn(time(9, 0), starts)
        self.assertNotIn(time(9, 30), starts)  # would end 10:20, inside the block
        self.assertNotIn(time(11, 0), starts)
        self.assertIn(time(12, 0), starts)

    def test_other_business_blocks_do_not_count(self):
        other = create_business("b@example.com", "Otro")
        whole_day(other, self.date)
        self.assertNotEqual(available_slots(self.ana, self.service, self.date), [])

    def test_day_strip_disables_fully_blocked_days_only(self):
        whole_day(self.business, self.date, self.ana)
        later = self.date + timedelta(days=1)
        # Both of Ana's ranges (09-13 and 14-18) blocked, with a gap at lunch: still no free time.
        block(self.business, local_dt(later, 9), local_dt(later, 13), self.ana)
        block(self.business, local_dt(later, 14), local_dt(later, 18), self.ana)
        partial = self.date + timedelta(days=2)
        block(self.business, local_dt(partial, 9), local_dt(partial, 13), self.ana)

        for date, enabled in ((self.date, False), (later, False), (partial, True)):
            strip = month_strip(date.replace(day=1), [self.ana], selected=date)
            self.assertEqual(strip_day(strip, date)["enabled"], enabled, date)
        strip = month_strip(self.date.replace(day=1), [self.bruno])
        self.assertTrue(strip_day(strip, self.date)["enabled"])


class BookingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.business = create_business()
        cls.ana = create_professional(cls.business, name="Ana")
        cls.service = create_service(cls.business, duration=50)
        cls.date = future_date()

    def test_forged_booking_in_a_blocked_time_is_rejected(self):
        block(self.business, local_dt(self.date, 9), local_dt(self.date, 11), reason="Médico")
        start_at = local_dt(self.date, 9)
        response = self.client.post(
            reverse("book", args=[self.business.slug]),
            {
                "service": self.service.pk,
                "professional": self.ana.pk,
                "date": self.date.isoformat(),
                "start_at": start_at.isoformat(),
                "customer_name": "Laura Gómez",
                "customer_phone": "+54 11 5555-1234",
                "customer_email": "laura@example.com",
                "website": "",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Appointment.objects.exists())
        self.assertNotContains(response, "Médico")

    def test_reschedule_into_a_blocked_time_is_rejected(self):
        appointment = create_appointment(self.ana, self.service, local_dt(self.date, 15))
        new_date = self.date + timedelta(days=2)
        whole_day(self.business, new_date, self.ana)
        response = self.client.post(
            reverse("reschedule_appointment", args=[appointment.manage_token]),
            {"date": new_date.isoformat(), "start_at": local_dt(new_date, 9).isoformat()},
        )
        self.assertContains(response, "Ese horario ya no está disponible.")
        appointment.refresh_from_db()
        self.assertEqual(appointment.start_at, local_dt(self.date, 15))
        self.assertEqual(len(mail.outbox), 0)


class TimeOffPanelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.business = create_business()
        cls.ana = create_professional(cls.business, name="Ana")
        cls.service = create_service(cls.business, duration=50)
        cls.date = future_date()

    def setUp(self):
        self.client.force_login(self.business.owner)

    def add(self, **data):
        fields = {"professional": "", "start_date": self.date.isoformat(), "reason": ""}
        fields.update(data)
        return self.client.post(reverse("time_off_list"), fields)

    def test_whole_days_for_the_business(self):
        end = self.date + timedelta(days=2)
        response = self.add(end_date=end.isoformat(), reason="  Vacaciones\n de verano ")
        self.assertRedirects(response, reverse("time_off_list"))
        saved = TimeOff.objects.get()
        self.assertIsNone(saved.professional)
        self.assertEqual(saved.start_at, local_dt(self.date, 0))
        self.assertEqual(saved.end_at, local_dt(end + timedelta(days=1), 0))
        self.assertEqual(saved.reason, "Vacaciones de verano")
        self.assertTrue(saved.is_full_days)
        self.assertEqual(saved.last_day, end)

    def test_hours_for_one_professional(self):
        self.add(professional=self.ana.pk, start_time="10:00", end_time="12:30")
        saved = TimeOff.objects.get()
        self.assertEqual(saved.professional, self.ana)
        self.assertEqual(saved.start_at, local_dt(self.date, 10))
        self.assertEqual(saved.end_at, local_dt(self.date, 12, 30))
        self.assertFalse(saved.is_full_days)

    def test_invalid_periods_are_rejected(self):
        yesterday = timezone.localdate() - timedelta(days=1)
        cases = [
            {"start_time": "10:00"},
            {"start_time": "12:00", "end_time": "10:00"},
            {"end_date": (self.date - timedelta(days=1)).isoformat()},
            {"end_date": (self.date + timedelta(days=MAX_TIME_OFF_DAYS)).isoformat()},
            {"start_date": yesterday.isoformat()},
            {"start_date": ""},
            {"reason": "x" * 101},
        ]
        for data in cases:
            with self.subTest(data=data):
                response = self.add(**data)
                self.assertEqual(response.status_code, 200)
        self.assertFalse(TimeOff.objects.exists())

    def test_professional_of_another_business_is_rejected(self):
        other = create_professional(create_business("b@example.com", "Otro"), name="Zoe")
        response = self.add(professional=other.pk)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(TimeOff.objects.exists())

    def test_confirmed_appointments_stay_until_the_owner_chooses(self):
        appointment = create_appointment(self.ana, self.service, local_dt(self.date, 10))
        response = self.add()
        saved = TimeOff.objects.get()
        self.assertRedirects(response, reverse("time_off_appointments", args=[saved.pk]))
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, Appointment.CONFIRMED)
        self.assertEqual(len(mail.outbox), 0)

    def test_without_affected_appointments_goes_back_to_the_list(self):
        create_appointment(self.ana, self.service, local_dt(self.date + timedelta(days=1), 10))
        self.assertRedirects(self.add(), reverse("time_off_list"))

    def test_list_shows_upcoming_and_hides_past(self):
        day_end = local_dt(self.date + timedelta(days=1), 0)
        block(self.business, local_dt(self.date, 0), day_end, self.ana, reason="Turno médico")
        past = timezone.localdate() - timedelta(days=3)
        block(self.business, local_dt(past, 9), local_dt(past, 10), reason="Viejo")
        response = self.client.get(reverse("time_off_list"))
        self.assertContains(response, "Turno médico")
        self.assertContains(response, "todo el día")
        self.assertNotContains(response, "Viejo")

    def test_delete_own_block_only(self):
        mine = whole_day(self.business, self.date)
        other = whole_day(create_business("b@example.com", "Otro"), self.date)
        response = self.client.post(reverse("time_off_delete", args=[other.pk]))
        self.assertEqual(response.status_code, 404)
        self.client.post(reverse("time_off_delete", args=[mine.pk]))
        self.assertEqual(list(TimeOff.objects.all()), [other])

    def test_delete_needs_post(self):
        mine = whole_day(self.business, self.date)
        response = self.client.get(reverse("time_off_delete", args=[mine.pk]))
        self.assertEqual(response.status_code, 405)
        self.assertTrue(TimeOff.objects.exists())

    def test_read_only_account_cannot_create_or_delete(self):
        mine = whole_day(self.business, self.date)
        end_trial(self.business)
        self.assertRedirects(self.add(), reverse("plans"), fetch_redirect_response=False)
        response = self.client.post(reverse("time_off_delete", args=[mine.pk]))
        self.assertRedirects(response, reverse("plans"), fetch_redirect_response=False)
        self.assertEqual(TimeOff.objects.count(), 1)
        page = self.client.get(reverse("time_off_list"))
        self.assertNotContains(page, "Nuevo bloqueo")

    def test_login_required(self):
        self.client.logout()
        response = self.client.get(reverse("time_off_list"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response["Location"])

    def test_agenda_shows_the_day_blocks(self):
        block(self.business, local_dt(self.date, 10), local_dt(self.date, 12), self.ana)
        response = self.client.get(reverse("panel"), {"date": self.date.isoformat()})
        self.assertContains(response, "Día con bloqueos")
        self.assertContains(response, "de 10:00 a 12:00")
        response = self.client.get(
            reverse("panel"), {"date": (self.date + timedelta(days=1)).isoformat()}
        )
        self.assertNotContains(response, "Día con bloqueos")


class CancelAffectedTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.business = create_business()
        cls.ana = create_professional(cls.business, name="Ana")
        cls.bruno = create_professional(cls.business, name="Bruno")
        cls.service = create_service(cls.business, duration=50)
        cls.date = future_date()

    def setUp(self):
        self.client.force_login(self.business.owner)
        self.time_off = whole_day(self.business, self.date, self.ana)
        self.first = create_appointment(self.ana, self.service, local_dt(self.date, 10))
        self.second = create_appointment(self.ana, self.service, local_dt(self.date, 15))

    def url(self, time_off=None):
        return reverse("time_off_appointments", args=[(time_off or self.time_off).pk])

    def cancel(self, appointments, reason=""):
        return self.client.post(
            self.url(), {"appointments": [a.pk for a in appointments], "reason": reason}
        )

    def status(self, appointment):
        appointment.refresh_from_db()
        return appointment.status

    def test_page_lists_only_appointments_inside_the_block_all_checked(self):
        outside = create_appointment(self.ana, self.service, local_dt(self.date + timedelta(1), 10))
        other_pro = create_appointment(self.bruno, self.service, local_dt(self.date, 10))
        response = self.client.get(self.url())
        choices = list(response.context["form"].fields["appointments"].queryset)
        self.assertEqual(choices, [self.first, self.second])
        self.assertNotIn(outside, choices)
        self.assertNotIn(other_pro, choices)
        self.assertContains(response, "checked", count=2)

    def test_cancels_the_chosen_ones_and_emails_the_reason(self):
        response = self.cancel([self.first], reason="  Se cortó\n la luz ")
        self.assertRedirects(response, self.url())
        self.assertEqual(self.status(self.first), Appointment.CANCELLED)
        self.assertEqual(self.status(self.second), Appointment.CONFIRMED)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["cliente@example.com"])
        self.assertIn("Motivo: Se cortó la luz", mail.outbox[0].body)

    def test_without_reason_the_email_has_no_reason_line(self):
        self.cancel([self.first, self.second])
        self.assertEqual(len(mail.outbox), 2)
        self.assertNotIn("Motivo", mail.outbox[0].body)

    def test_private_time_off_reason_never_reaches_customers(self):
        TimeOff.objects.filter(pk=self.time_off.pk).update(reason="Peleé con el socio")
        self.cancel([self.first])
        self.assertNotIn("socio", mail.outbox[0].body)

    def test_customer_without_email_gets_a_phone_warning(self):
        Appointment.objects.filter(pk=self.first.pk).update(customer_email="")
        response = self.cancel([self.first], reason="Feriado")
        self.assertEqual(self.status(self.first), Appointment.CANCELLED)
        self.assertEqual(len(mail.outbox), 0)
        messages = [str(m) for m in response.wsgi_request._messages]
        self.assertTrue(any("avisales por teléfono" in m for m in messages), messages)

    def test_requires_a_choice_and_a_short_reason(self):
        for data in ({"appointments": []}, {"appointments": [self.first.pk], "reason": "x" * 201}):
            with self.subTest(data=data):
                response = self.client.post(self.url(), data)
                self.assertEqual(response.status_code, 200)
        self.assertEqual(self.status(self.first), Appointment.CONFIRMED)

    def test_appointments_outside_the_block_cannot_be_cancelled(self):
        outside = create_appointment(self.ana, self.service, local_dt(self.date + timedelta(1), 10))
        other_business = create_business("b@example.com", "Otro")
        foreign = create_appointment(
            create_professional(other_business, name="Zoe"),
            create_service(other_business),
            local_dt(self.date, 10),
        )
        for appointment in (outside, foreign):
            with self.subTest(appointment=appointment.pk):
                response = self.cancel([appointment])
                self.assertEqual(response.status_code, 200)
                self.assertEqual(self.status(appointment), Appointment.CONFIRMED)
        self.assertEqual(len(mail.outbox), 0)

    def test_already_cancelled_is_not_emailed_again(self):
        self.first.cancel()
        response = self.cancel([self.first])
        self.assertEqual(response.status_code, 200)  # no longer a valid choice
        self.assertEqual(len(mail.outbox), 0)

    def test_other_business_block_is_not_found(self):
        other = whole_day(create_business("b@example.com", "Otro"), self.date)
        self.assertEqual(self.client.get(self.url(other)).status_code, 404)

    def test_read_only_account_cannot_cancel(self):
        end_trial(self.business)
        response = self.cancel([self.first])
        self.assertRedirects(response, reverse("plans"), fetch_redirect_response=False)
        self.assertEqual(self.status(self.first), Appointment.CONFIRMED)

    def test_list_links_to_the_affected_appointments(self):
        response = self.client.get(reverse("time_off_list"))
        self.assertContains(response, "2 turnos confirmados en este período")
        self.assertContains(response, self.url())
