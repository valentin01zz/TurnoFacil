from datetime import time, timedelta

from django.test import TestCase

from bookings.availability import available_slots
from bookings.models import Appointment

from .helpers import (
    create_appointment,
    create_business,
    create_professional,
    create_service,
    future_date,
    local_dt,
)


class AvailableSlotsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.business = create_business()
        cls.professional = create_professional(cls.business)
        cls.service = create_service(cls.business, duration=50)
        cls.date = future_date()

    def slots(self, **kwargs):
        return available_slots(self.professional, self.service, self.date, **kwargs)

    def test_slots_every_30_minutes_where_the_service_fits(self):
        expected = [local_dt(self.date, 9, 0) + timedelta(minutes=30 * i) for i in range(7)]
        expected += [local_dt(self.date, 14, 0) + timedelta(minutes=30 * i) for i in range(7)]

        self.assertEqual(self.slots(), expected)
        self.assertNotIn(local_dt(self.date, 12, 30), self.slots())

    def test_confirmed_appointment_blocks_overlapping_slots(self):
        create_appointment(self.professional, self.service, local_dt(self.date, 10, 0))

        slots = self.slots()

        # 10:00-10:50 is taken: 9:30 (ends 10:20), 10:00 and 10:30 overlap it.
        for blocked in [(9, 30), (10, 0), (10, 30)]:
            self.assertNotIn(local_dt(self.date, *blocked), slots)
        self.assertIn(local_dt(self.date, 9, 0), slots)
        self.assertIn(local_dt(self.date, 11, 0), slots)

    def test_cancelled_appointment_does_not_block(self):
        create_appointment(
            self.professional,
            self.service,
            local_dt(self.date, 10, 0),
            status=Appointment.CANCELLED,
        )

        self.assertIn(local_dt(self.date, 10, 0), self.slots())

    def test_other_professional_appointment_does_not_block(self):
        other = create_professional(self.business, name="Bruno")
        create_appointment(other, self.service, local_dt(self.date, 10, 0))

        self.assertIn(local_dt(self.date, 10, 0), self.slots())

    def test_past_times_today_are_not_offered(self):
        today = self.date - timedelta(days=7)
        now = local_dt(today, 10, 10)

        slots = available_slots(self.professional, self.service, today, now=now)

        self.assertEqual(slots[0], local_dt(today, 10, 30))

    def test_dates_outside_the_booking_window_have_no_slots(self):
        today = self.date - timedelta(days=7)
        now = local_dt(today, 8, 0)

        for date in [today - timedelta(days=1), today + timedelta(days=61)]:
            self.assertEqual(
                available_slots(self.professional, self.service, date, now=now), [], date
            )
        self.assertTrue(
            available_slots(self.professional, self.service, today + timedelta(days=60), now=now)
        )

    def test_day_without_working_hours_has_no_slots(self):
        self.professional.working_hours.filter(weekday=self.date.weekday()).delete()

        self.assertEqual(self.slots(), [])

    def test_service_longer_than_any_range_has_no_slots(self):
        long_service = create_service(self.business, name="Tratamiento completo", duration=300)

        self.assertEqual(available_slots(self.professional, long_service, self.date), [])

    def test_slots_follow_the_range_start(self):
        professional = create_professional(
            self.business, name="Ciro", ranges=((time(9, 15), time(10, 45)),)
        )
        service = create_service(self.business, name="Corte", duration=30)

        slots = available_slots(professional, service, self.date)

        self.assertEqual(
            slots,
            [local_dt(self.date, 9, 15), local_dt(self.date, 9, 45), local_dt(self.date, 10, 15)],
        )
