"""Availability with split shifts: 09:00-13:00 and 17:00-21:00 on the same day."""

from datetime import time, timedelta

from django.test import TestCase

from bookings.availability import available_slots
from businesses.models import WorkingHours

from .helpers import (
    create_appointment,
    create_business,
    create_professional,
    create_service,
    future_date,
    local_dt,
)


def every_30_minutes(date, hour, count):
    return [local_dt(date, hour) + timedelta(minutes=30 * i) for i in range(count)]


class SplitShiftAvailabilityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.business = create_business()
        cls.ana = create_professional(
            cls.business, name="Ana", ranges=((time(9), time(13)), (time(17), time(21)))
        )
        cls.service = create_service(cls.business, duration=60)
        cls.date = future_date()

    def slots(self, professional=None, service=None):
        return available_slots(professional or self.ana, service or self.service, self.date)

    def test_morning_and_afternoon_slots_and_none_in_the_break(self):
        # A 60-minute service: last start 12:00 in the morning and 20:00 in the afternoon.
        expected = every_30_minutes(self.date, 9, 7) + every_30_minutes(self.date, 17, 7)

        self.assertEqual(self.slots(), expected)
        for hour in (13, 14, 15, 16):
            self.assertNotIn(local_dt(self.date, hour), self.slots())

    def test_a_service_that_does_not_fit_before_the_end_of_a_range_is_not_offered(self):
        long_service = create_service(self.business, name="Tratamiento", duration=150)

        slots = self.slots(service=long_service)

        self.assertIn(local_dt(self.date, 10, 30), slots)  # ends 13:00
        self.assertNotIn(local_dt(self.date, 11), slots)  # would end 13:30, in the break
        self.assertIn(local_dt(self.date, 18, 30), slots)  # ends 21:00
        self.assertNotIn(local_dt(self.date, 19), slots)

    def test_an_appointment_blocks_only_its_own_range(self):
        create_appointment(self.ana, self.service, local_dt(self.date, 10))

        slots = self.slots()

        self.assertNotIn(local_dt(self.date, 10), slots)
        self.assertNotIn(local_dt(self.date, 9, 30), slots)
        self.assertIn(local_dt(self.date, 11), slots)
        self.assertEqual(every_30_minutes(self.date, 17, 7), [s for s in slots if s.hour >= 17])

    def test_back_to_back_ranges_never_repeat_a_slot(self):
        bruno = create_professional(
            self.business, name="Bruno", ranges=((time(9), time(13)), (time(13), time(17)))
        )

        slots = self.slots(professional=bruno)

        self.assertEqual(len(slots), len(set(slots)))
        self.assertEqual(slots, sorted(slots))
        self.assertIn(local_dt(self.date, 13), slots)

    def test_only_the_ranges_of_that_weekday_count(self):
        sofia = create_professional(self.business, name="Sofía", ranges=())
        WorkingHours.objects.create(
            professional=sofia,
            weekday=self.date.weekday(),
            start_time=time(17),
            end_time=time(19),
        )
        WorkingHours.objects.create(
            professional=sofia,
            weekday=(self.date.weekday() + 1) % 7,
            start_time=time(9),
            end_time=time(13),
        )

        self.assertEqual(self.slots(professional=sofia), every_30_minutes(self.date, 17, 3))
