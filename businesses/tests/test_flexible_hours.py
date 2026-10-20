"""Flexible working hours: several ranges per day, added and removed freely, up to a limit."""

from datetime import time, timedelta

from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from billing.tests.helpers import end_trial, set_active
from businesses.forms import MAX_WORKING_HOURS
from businesses.models import Professional, WorkingHours

from .test_professionals import create_business, professional_data

WEEKDAYS = range(5)  # Monday to Friday


def row(weekday, start, end, **extra):
    return {"weekday": str(weekday), "start_time": start, "end_time": end, **extra}


def split_shift(days=WEEKDAYS):
    """Ana's example: 09:00 to 13:00 and 17:00 to 21:00 on each day."""
    rows = []
    for day in days:
        rows += [row(day, "09:00", "13:00"), row(day, "17:00", "21:00")]
    return rows


def saved_hours(professional):
    return list(professional.working_hours.values_list("weekday", "start_time", "end_time"))


class FlexibleHoursFormTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.business = create_business("a@example.com", "Estética Luna")

    def setUp(self):
        self.client.force_login(self.business.owner)

    def create(self, rows, name="Ana"):
        return self.client.post(reverse("professional_create"), professional_data(name, rows))

    def edit(self, professional, rows, initial):
        return self.client.post(
            reverse("professional_edit", args=[professional.pk]),
            professional_data(professional.name, rows, initial=initial),
        )

    def with_hours(self, ranges):
        professional = Professional.objects.create(business=self.business, name="Ana")
        hours = [
            WorkingHours.objects.create(
                professional=professional, weekday=day, start_time=start, end_time=end
            )
            for day, start, end in ranges
        ]
        return professional, hours

    def test_two_ranges_on_the_same_day(self):
        response = self.create([row(0, "09:00", "13:00"), row(0, "17:00", "21:00")])

        self.assertRedirects(response, reverse("professional_list"))
        self.assertEqual(
            saved_hours(Professional.objects.get(name="Ana")),
            [(0, time(9), time(13)), (0, time(17), time(21))],
        )

    def test_split_shift_monday_to_friday_saves_ten_rows(self):
        response = self.create(split_shift())

        self.assertRedirects(response, reverse("professional_list"))
        hours = saved_hours(Professional.objects.get(name="Ana"))
        self.assertEqual(len(hours), 10)
        for day in WEEKDAYS:
            self.assertIn((day, time(9), time(13)), hours)
            self.assertIn((day, time(17), time(21)), hours)

    def test_order_of_the_rows_does_not_matter(self):
        response = self.create(
            [row(0, "17:00", "21:00"), row(1, "09:00", "13:00"), row(0, "09:00", "13:00")]
        )

        self.assertRedirects(response, reverse("professional_list"))
        self.assertEqual(len(saved_hours(Professional.objects.get(name="Ana"))), 3)

    def test_partial_overlap_is_rejected_in_any_order(self):
        for rows in (
            [row(0, "09:00", "14:00"), row(0, "13:00", "17:00")],
            [row(0, "13:00", "17:00"), row(0, "09:00", "14:00")],
            [row(0, "09:00", "18:00"), row(0, "10:00", "11:00")],
        ):
            response = self.create(rows)

            self.assertContains(response, "Hay horarios superpuestos el lunes.")
        self.assertFalse(Professional.objects.exists())

    def test_exact_copy_is_rejected(self):
        response = self.create([row(0, "09:00", "13:00"), row(0, "09:00", "13:00")])

        self.assertContains(response, "Hay horarios superpuestos el lunes.")
        self.assertFalse(Professional.objects.exists())

    def test_back_to_back_ranges_are_allowed(self):
        response = self.create([row(0, "09:00", "13:00"), row(0, "13:00", "17:00")])

        self.assertRedirects(response, reverse("professional_list"))

    def test_end_not_after_start_is_rejected(self):
        for end in ("09:00", "08:00"):
            response = self.create([row(0, "17:00", "21:00"), row(0, "09:00", end)])

            self.assertContains(response, "La hora de fin tiene que ser posterior a la de inicio.")
        self.assertFalse(Professional.objects.exists())

    def test_removing_one_range_keeps_the_others(self):
        professional, (morning, afternoon) = self.with_hours(
            [(0, time(9), time(13)), (0, time(17), time(21))]
        )

        response = self.edit(
            professional,
            [
                row(0, "09:00", "13:00", id=str(morning.pk)),
                row(0, "17:00", "21:00", id=str(afternoon.pk), DELETE="on"),
            ],
            initial=2,
        )

        self.assertRedirects(response, reverse("professional_list"))
        self.assertEqual(saved_hours(professional), [(0, time(9), time(13))])

    def test_adding_a_range_keeps_the_existing_ones(self):
        professional, (morning,) = self.with_hours([(0, time(9), time(13))])

        response = self.edit(
            professional,
            [row(0, "09:00", "13:00", id=str(morning.pk)), row(0, "17:00", "21:00")],
            initial=1,
        )

        self.assertRedirects(response, reverse("professional_list"))
        self.assertEqual(
            saved_hours(professional), [(0, time(9), time(13)), (0, time(17), time(21))]
        )
        self.assertTrue(WorkingHours.objects.filter(pk=morning.pk).exists())

    def test_edit_page_loads_every_range_plus_empty_rows(self):
        professional, _ = self.with_hours([(day, time(9), time(13)) for day in WEEKDAYS])

        response = self.client.get(reverse("professional_edit", args=[professional.pk]))

        formset = response.context["formset"]
        self.assertEqual(len(formset.forms), 5 + 3)
        self.assertContains(response, "Agregar otro horario")
        self.assertContains(response, 'name="hours-0-DELETE"')

    def test_up_to_the_limit_is_saved(self):
        rows = [
            row(day, f"{hour:02d}:00", f"{hour:02d}:30") for day in range(7) for hour in range(8)
        ]
        rows = rows[:MAX_WORKING_HOURS]

        response = self.create(rows)

        self.assertRedirects(response, reverse("professional_list"))
        self.assertEqual(WorkingHours.objects.count(), MAX_WORKING_HOURS)

    def test_more_ranges_than_the_limit_are_rejected(self):
        rows = [
            row(day, f"{hour:02d}:00", f"{hour:02d}:30") for day in range(7) for hour in range(8)
        ]
        rows = rows[: MAX_WORKING_HOURS + 1]

        response = self.create(rows)

        self.assertContains(response, f"Podés cargar hasta {MAX_WORKING_HOURS} horarios")
        self.assertFalse(Professional.objects.exists())

    def test_a_forged_form_with_thousands_of_rows_is_rejected(self):
        data = professional_data("Ana", [row(0, "09:00", "13:00")])
        data["hours-TOTAL_FORMS"] = "5000"

        response = self.client.post(reverse("professional_create"), data)

        self.assertContains(response, f"Podés cargar hasta {MAX_WORKING_HOURS} horarios")
        self.assertLessEqual(len(response.context["formset"].forms), MAX_WORKING_HOURS * 2)
        self.assertFalse(Professional.objects.exists())

    def test_the_form_needs_the_csrf_token(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.business.owner)

        response = client.post(
            reverse("professional_create"), professional_data("Ana", split_shift())
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(Professional.objects.exists())


class FlexibleHoursPlansTests(TestCase):
    """Every plan and the free trial get split shifts; a read-only panel saves nothing."""

    def post_split_shift(self, business):
        self.client.force_login(business.owner)
        return self.client.post(
            reverse("professional_create"), professional_data("Ana", split_shift())
        )

    def test_trial_and_every_plan_can_save_split_shifts(self):
        cases = [
            ("trial", None),
            ("esencial", "esencial"),
            ("profesional", "profesional"),
            ("negocio", "negocio"),
            ("piloto", "piloto"),
        ]
        for index, (label, plan) in enumerate(cases):
            with self.subTest(label):
                business = create_business(f"{label}@example.com", f"Negocio {index}")
                if plan == "piloto":
                    set_active(business, plan)  # granted with grant_plan: no end date
                elif plan:
                    set_active(business, plan, timezone.now() + timedelta(days=20))

                response = self.post_split_shift(business)

                self.assertRedirects(response, reverse("professional_list"))
                self.assertEqual(business.professionals.get().working_hours.count(), 10)

    def test_a_read_only_panel_cannot_save(self):
        business = create_business("vencida@example.com", "Prueba vencida")
        end_trial(business)

        response = self.post_split_shift(business)

        self.assertRedirects(response, reverse("plans"), fetch_redirect_response=False)
        self.assertFalse(Professional.objects.filter(business=business).exists())
