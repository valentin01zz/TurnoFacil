import calendar
from datetime import date, time, timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from bookings.booking_calendar import long_date, month_strip, parse_month, slot_groups
from businesses.models import WorkingHours

from .helpers import (
    create_appointment,
    create_business,
    create_professional,
    create_service,
    future_date,
    local_dt,
)


class MonthStripTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.business = create_business()
        # Works Monday to Friday only.
        cls.ana = create_professional(cls.business, name="Ana", ranges=())
        for weekday in range(5):
            WorkingHours.objects.create(
                professional=cls.ana, weekday=weekday, start_time=time(9), end_time=time(13)
            )
        cls.today = date(2026, 10, 20)

    def strip(self, month=None, selected=None):
        return month_strip(month, [self.ana], selected=selected, today=self.today)

    def test_lists_every_day_of_the_month(self):
        strip = self.strip()

        self.assertEqual(strip["label"], "Octubre 2026")
        self.assertEqual(len(strip["days"]), 31)
        self.assertEqual(strip["days"][0]["date"], date(2026, 10, 1))

    def test_only_working_days_inside_the_window_are_enabled(self):
        days = {d["date"]: d for d in self.strip()["days"]}

        self.assertFalse(days[date(2026, 10, 19)]["enabled"], "yesterday")
        self.assertTrue(days[date(2026, 10, 20)]["enabled"], "today, a Tuesday")
        self.assertFalse(days[date(2026, 10, 24)]["enabled"], "Saturday")
        self.assertTrue(days[date(2026, 10, 26)]["enabled"], "Monday")
        self.assertTrue(days[date(2026, 10, 20)]["is_today"])

    def test_window_end_is_respected(self):
        # 2026-10-20 + 60 days = Saturday 2026-12-19; the next weekdays are outside the window.
        days = {d["date"]: d for d in self.strip(month=date(2026, 12, 1))["days"]}

        self.assertTrue(days[date(2026, 12, 18)]["enabled"], "Friday, last day inside")
        self.assertFalse(days[date(2026, 12, 21)]["enabled"], "Monday, outside the window")

    def test_month_navigation_stays_inside_the_window(self):
        first = self.strip()
        last = self.strip(month=date(2026, 12, 1))

        self.assertIsNone(first["previous"])
        self.assertEqual(first["next"], date(2026, 11, 1))
        self.assertEqual(last["previous"], date(2026, 11, 1))
        self.assertIsNone(last["next"])

    def test_out_of_range_months_are_clamped(self):
        self.assertEqual(self.strip(month=date(2026, 1, 1))["month"], date(2026, 10, 1))
        self.assertEqual(self.strip(month=date(2027, 6, 1))["month"], date(2026, 12, 1))

    def test_selected_day_is_flagged(self):
        days = self.strip(selected=date(2026, 10, 22))["days"]

        self.assertEqual([d["number"] for d in days if d["selected"]], [22])

    def test_helpers(self):
        self.assertEqual(parse_month("2026-11"), date(2026, 11, 1))
        self.assertIsNone(parse_month("noviembre"))
        self.assertIsNone(parse_month(None))
        self.assertEqual(long_date(date(2026, 10, 19)), "Lunes 19 de octubre")
        self.assertEqual(calendar.monthrange(2026, 2)[1], len(self.strip_feb()))

    def strip_feb(self):
        return month_strip(date(2027, 2, 1), [self.ana], today=date(2027, 1, 20))["days"]


class SlotGroupsTests(TestCase):
    def test_morning_and_afternoon(self):
        day = future_date()
        groups = slot_groups(
            [local_dt(day, 9), local_dt(day, 12, 30), local_dt(day, 14)],
            local_dt(day, 14).isoformat(),
        )

        self.assertEqual([g["label"] for g in groups], ["Mañana", "Tarde"])
        self.assertEqual([s["label"] for s in groups[0]["slots"]], ["09:00", "12:30"])
        self.assertTrue(groups[1]["slots"][0]["checked"])


class StripOnPagesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.business = create_business()
        cls.ana = create_professional(cls.business, name="Ana")
        cls.bruno = create_professional(cls.business, name="Bruno")
        cls.service = create_service(cls.business)
        cls.date = future_date()

    def page(self, **params):
        return self.client.get(reverse("booking_page", args=[self.business.slug]), params)

    def test_strip_appears_after_choosing_service_and_professional(self):
        before = self.page(service=self.service.pk)
        after = self.page(service=self.service.pk, professional=self.ana.pk)

        today = timezone.localdate().isoformat()
        self.assertNotContains(before, 'name="date" value=')
        self.assertContains(after, f'name="date" value="{today}"')
        self.assertContains(after, "Mes siguiente")

    def test_choosing_a_day_shows_its_free_times(self):
        response = self.page(
            service=self.service.pk, professional=self.ana.pk, date=self.date.isoformat()
        )

        self.assertContains(response, "Horarios disponibles")
        self.assertContains(response, local_dt(self.date, 9).isoformat())
        self.assertContains(response, 'aria-pressed="true"')

    def test_month_parameter_moves_the_strip(self):
        next_month = (self.date.replace(day=1) + timedelta(days=32)).replace(day=1)

        response = self.page(
            service=self.service.pk,
            professional=self.ana.pk,
            month=next_month.strftime("%Y-%m"),
        )

        self.assertContains(response, f'value="{next_month.isoformat()}"')

    def test_reschedule_uses_the_same_strip(self):
        appointment = create_appointment(self.ana, self.service, local_dt(self.date, 10))

        response = self.client.get(
            reverse("reschedule_appointment", args=[appointment.manage_token])
        )

        today = timezone.localdate().isoformat()
        self.assertContains(response, f'name="date" value="{today}"')
        self.assertContains(response, "Mes siguiente")


class ConfirmationStampTests(TestCase):
    def test_stamp_only_right_after_booking(self):
        business = create_business()
        ana = create_professional(business, name="Ana")
        appointment = create_appointment(ana, create_service(business), local_dt(future_date(), 9))
        url = reverse("appointment_detail", args=[appointment.manage_token])

        fresh = self.client.get(url, {"nuevo": "1"})
        later = self.client.get(url)

        self.assertContains(fresh, "CONFIRMADO")
        self.assertContains(fresh, "¡Listo, Cliente!")
        self.assertNotContains(later, "CONFIRMADO")
