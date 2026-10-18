from datetime import date, timedelta

from django.test import TestCase
from django.urls import reverse

from bookings.models import Appointment
from bookings.tests.helpers import (
    create_appointment,
    create_business,
    create_professional,
    create_service,
    local_dt,
)
from businesses.views import week_chart


class WeekChartTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.business = create_business()
        cls.ana = create_professional(cls.business, name="Ana")
        cls.sofia = create_professional(cls.business, name="Sofía")
        cls.service = create_service(cls.business, duration=30)
        # A fixed week in the future: Monday 2027-03-01 to Sunday 2027-03-07.
        cls.monday = date(2027, 3, 1)
        cls.wednesday = cls.monday + timedelta(days=2)
        for hour in (9, 10, 11):
            create_appointment(cls.ana, cls.service, local_dt(cls.monday, hour))
        create_appointment(cls.sofia, cls.service, local_dt(cls.wednesday, 9))
        create_appointment(
            cls.ana, cls.service, local_dt(cls.wednesday, 15), status=Appointment.CANCELLED
        )
        create_appointment(cls.ana, cls.service, local_dt(cls.monday - timedelta(days=1), 9))
        create_appointment(cls.ana, cls.service, local_dt(cls.monday + timedelta(days=7), 9))
        other = create_business("b@example.com", "Taller Sur")
        create_appointment(
            create_professional(other, name="Carlos"),
            create_service(other, name="Aceite"),
            local_dt(cls.wednesday, 10),
        )

    def test_counts_confirmed_appointments_per_day_of_the_week(self):
        week = week_chart(self.business, self.wednesday, None)

        self.assertEqual([day["date"] for day in week][0], self.monday)
        self.assertEqual([day["count"] for day in week], [3, 0, 1, 0, 0, 0, 0])

    def test_filter_by_professional(self):
        week = week_chart(self.business, self.wednesday, self.sofia)

        self.assertEqual([day["count"] for day in week], [0, 0, 1, 0, 0, 0, 0])

    def test_selected_day_and_bar_heights(self):
        week = week_chart(self.business, self.wednesday, None)

        self.assertEqual([day["selected"] for day in week].index(True), 2)
        self.assertEqual(week[0]["height"], 100)
        self.assertEqual(week[2]["height"], 33)
        self.assertEqual(week[1]["height"], 6)

    def test_agenda_shows_the_chart_with_links_to_each_day(self):
        self.client.force_login(self.business.owner)

        response = self.client.get(reverse("panel"), {"date": self.wednesday.isoformat()})

        self.assertContains(response, "Esta semana")
        self.assertContains(response, f"?date={self.monday.isoformat()}")
        self.assertContains(response, 'aria-current="date"')
        self.assertContains(response, "3 turnos")
