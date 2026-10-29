"""Income and reports (HU-35): figures per period and professional, and the Excel export."""

from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from billing.models import Plan, Subscription
from billing.tests.helpers import end_trial, set_active
from bookings.models import Appointment
from bookings.tests.helpers import (
    create_appointment,
    create_business,
    create_professional,
    create_service,
)
from businesses.models import Service
from businesses.reports import build_report, period_for, safe_cell


def at(day, hour, minute=0):
    return timezone.make_aware(datetime.combine(day, time(hour, minute)))


class PeriodTests(TestCase):
    def test_periods_and_their_previous_ones(self):
        today = date(2026, 10, 29)  # Thursday
        week, before = period_for("week", today)
        self.assertEqual((week.first_day, week.end_day), (date(2026, 10, 26), date(2026, 11, 2)))
        self.assertEqual(before.first_day, date(2026, 10, 19))

        month, before = period_for("month", today)
        self.assertEqual((month.first_day, month.end_day), (date(2026, 10, 1), date(2026, 11, 1)))
        self.assertEqual((before.first_day, before.end_day), (date(2026, 9, 1), date(2026, 10, 1)))
        self.assertEqual(month.label, "Octubre 2026")

        last, before = period_for("last_month", today)
        self.assertEqual((last.first_day, last.end_day), (date(2026, 9, 1), date(2026, 10, 1)))
        self.assertEqual(before.first_day, date(2026, 8, 1))

        quarter, before = period_for("quarter", today)
        self.assertEqual(
            (quarter.first_day, quarter.end_day), (date(2026, 8, 1), date(2026, 11, 1))
        )
        self.assertEqual((before.first_day, before.end_day), (date(2026, 5, 1), date(2026, 8, 1)))
        self.assertEqual(quarter.label, "Agosto a octubre 2026")

        january, before = period_for("month", date(2027, 1, 15))
        self.assertEqual(before.first_day, date(2026, 12, 1))


class ReportFigureTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.business = create_business(name="Estética Luna")
        cls.ana = create_professional(cls.business, name="Ana")
        cls.bruno = create_professional(cls.business, name="Bruno")
        cls.facial = create_service(cls.business, name="Limpieza facial", duration=50)
        cls.masaje = create_service(cls.business, name="Masaje", duration=50)
        Service.objects.filter(pk=cls.facial.pk).update(price=Decimal("10000"))
        cls.facial.refresh_from_db()
        # "Now" is the middle of a month, so the month has a past and a future.
        cls.now = at(date(2026, 10, 15), 12)
        cls.past_day = date(2026, 10, 5)
        cls.future_day = date(2026, 10, 25)

    def book(self, professional, service, start, phone="11 5555 1111", attendance="", status=None):
        appointment = create_appointment(professional, service, start)
        Appointment.objects.filter(pk=appointment.pk).update(
            price=service.price,
            customer_phone=phone,
            attendance=attendance,
            status=status or Appointment.CONFIRMED,
        )
        return appointment

    def report(self, professional=None, period="month"):
        return build_report(self.business, period, professional, now=self.now)

    def test_income_is_split_by_attendance_and_time(self):
        self.book(self.ana, self.facial, at(self.past_day, 9), attendance=Appointment.ATTENDED)
        self.book(self.ana, self.facial, at(self.past_day, 10), attendance=Appointment.NO_SHOW)
        self.book(self.ana, self.facial, at(self.past_day, 11))  # not marked
        self.book(self.ana, self.masaje, at(self.past_day, 14), attendance=Appointment.ATTENDED)
        self.book(self.bruno, self.facial, at(self.future_day, 9))
        self.book(self.bruno, self.facial, at(self.future_day, 10), status=Appointment.CANCELLED)

        t = self.report()["totals"]
        self.assertEqual(t["income_attended"], Decimal("10000"))  # the massage has no price
        self.assertEqual(t["income_pending"], Decimal("10000"))
        self.assertEqual(t["income_upcoming"], Decimal("10000"))
        self.assertEqual((t["attended"], t["no_show"], t["pending"]), (2, 1, 1))
        self.assertEqual((t["upcoming"], t["cancelled"], t["total"]), (1, 1, 6))
        self.assertEqual(t["no_show_rate"], 33)
        self.assertEqual(t["cancel_rate"], 17)

    def test_saved_price_wins_over_the_current_one(self):
        self.book(self.ana, self.facial, at(self.past_day, 9), attendance=Appointment.ATTENDED)
        Service.objects.filter(pk=self.facial.pk).update(price=Decimal("99999"))
        self.assertEqual(self.report()["totals"]["income_attended"], Decimal("10000"))

    def test_professional_filter_and_rankings(self):
        self.book(self.ana, self.facial, at(self.past_day, 9), attendance=Appointment.ATTENDED)
        self.book(self.ana, self.facial, at(self.past_day, 10), attendance=Appointment.ATTENDED)
        self.book(self.bruno, self.masaje, at(self.past_day, 9), attendance=Appointment.ATTENDED)

        report = self.report()
        self.assertEqual([row["name"] for row in report["professionals"]], ["Ana", "Bruno"])
        self.assertEqual(report["professionals"][0]["income"], Decimal("20000"))
        self.assertEqual([row["name"] for row in report["services"]], ["Limpieza facial", "Masaje"])

        only_bruno = self.report(professional=self.bruno)
        self.assertEqual(only_bruno["totals"]["attended"], 1)
        self.assertEqual(only_bruno["totals"]["income_attended"], Decimal("0"))

    def test_comparison_with_the_previous_period(self):
        september = date(2026, 9, 10)
        self.book(self.ana, self.facial, at(september, 9), attendance=Appointment.ATTENDED)
        for hour in (9, 10):
            self.book(
                self.ana, self.facial, at(self.past_day, hour), attendance=Appointment.ATTENDED
            )
        changes = self.report()["changes"]
        self.assertEqual(changes["income_attended"], 100)
        self.assertEqual(changes["attended"], 100)

    def test_no_previous_data_means_no_comparison(self):
        self.book(self.ana, self.facial, at(self.past_day, 9), attendance=Appointment.ATTENDED)
        self.assertIsNone(self.report()["changes"]["income_attended"])

    def test_demand_and_customers(self):
        # 5/10/2026 is a Monday.
        self.book(self.ana, self.facial, at(self.past_day, 9), phone="011 15 5555 1111")
        self.book(self.bruno, self.facial, at(self.past_day, 9), phone="11 5555 1111")
        self.book(self.ana, self.facial, at(self.past_day, 11), phone="11 5555 2222")
        self.book(self.ana, self.facial, at(date(2026, 9, 1), 9), phone="+54 9 11 5555 2222")
        self.book(
            self.ana, self.facial, at(self.past_day, 15), phone="11 5555 3333", status="cancelled"
        )

        report = self.report()
        days = {day["label"]: day["count"] for day in report["demand"]["days"]}
        self.assertEqual(days["Lun"], 3)
        self.assertEqual(sum(days.values()), 3)  # the cancelled one does not count
        hours = {hour["label"]: hour["count"] for hour in report["demand"]["hours"]}
        self.assertEqual(hours, {"09": 2, "10": 0, "11": 1})
        # 1111 twice this month (new), 2222 came in September (returning), 3333 cancelled.
        self.assertEqual(report["customers"], {"total": 2, "new": 1, "returning": 1})

    def test_unpriced_active_services_are_counted(self):
        create_service(self.business, name="Viejo").__class__.objects.filter(name="Viejo").update(
            is_active=False
        )
        self.assertEqual(self.report()["unpriced_services"], 1)  # Masaje; Viejo is inactive

    def test_other_business_appointments_never_count(self):
        other = create_business("b@example.com", "Otro")
        theirs = create_service(other)
        Service.objects.filter(pk=theirs.pk).update(price=Decimal("5000"))
        theirs.refresh_from_db()
        self.book(
            create_professional(other, name="Zoe"),
            theirs,
            at(self.past_day, 9),
            attendance=Appointment.ATTENDED,
        )
        self.assertEqual(self.report()["totals"]["total"], 0)


class ReportPageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.business = create_business(name="Estética Luna")
        cls.ana = create_professional(cls.business, name="Ana")
        cls.service = create_service(cls.business, name="Limpieza facial", duration=50)
        Service.objects.filter(pk=cls.service.pk).update(price=Decimal("12500"))
        cls.service.refresh_from_db()

    def setUp(self):
        self.client.force_login(self.business.owner)
        today = timezone.localdate()
        self.day = today - timedelta(days=1) if today.day > 1 else today
        self.appointment = create_appointment(self.ana, self.service, at(self.day, 0, 5))
        Appointment.objects.filter(pk=self.appointment.pk).update(
            price=Decimal("12500"),
            attendance=Appointment.ATTENDED,
            customer_name="=HYPERLINK(1)",
            customer_phone="+54 11 5555 1234",
        )

    def test_trial_business_sees_the_report(self):
        response = self.client.get(reverse("reports"))
        self.assertContains(response, "ingresos estimados")
        self.assertContains(response, "$&nbsp;12.500")
        self.assertContains(response, "No son comprobantes fiscales")
        self.assertContains(response, reverse("reports_export"))

    def test_unknown_filters_fall_back(self):
        response = self.client.get(reverse("reports"), {"period": "x", "professional": "abc"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["period"], "month")
        self.assertIsNone(response.context["professional"])

    def test_another_business_professional_is_ignored(self):
        other = create_professional(create_business("b@example.com", "Otro"), name="Zoe")
        response = self.client.get(reverse("reports"), {"professional": other.pk})
        self.assertIsNone(response.context["professional"])

    def test_export_is_a_spanish_excel_csv_with_formulas_escaped(self):
        response = self.client.get(reverse("reports_export"), {"period": "month"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv; charset=utf-8")
        self.assertIn("attachment;", response["Content-Disposition"])
        self.assertEqual(response["Cache-Control"], "no-store")
        body = response.content.decode("utf-8")
        self.assertTrue(body.startswith("﻿Fecha;Hora;Cliente;"))
        row = body.splitlines()[1]
        self.assertIn(f"{self.day:%d/%m/%Y};00:05;'=HYPERLINK(1);'+54 11 5555 1234;", row)
        self.assertIn(";12500,00;Confirmado;Asistió;Online", row)

    def test_safe_cell(self):
        for value in ["=1+1", "+54", "-3", "@SUM", "\tx"]:
            self.assertTrue(safe_cell(value).startswith("'"), value)
        self.assertEqual(safe_cell("Laura"), "Laura")

    def test_plan_without_reports_sees_the_offer_and_cannot_export(self):
        set_active(self.business, "esencial")
        response = self.client.get(reverse("reports"))
        self.assertContains(response, "Ver planes")
        self.assertNotContains(response, "12.500")
        export = self.client.get(reverse("reports_export"))
        self.assertRedirects(export, reverse("plans"), fetch_redirect_response=False)

    def test_read_only_account_cannot_export(self):
        end_trial(self.business)
        export = self.client.get(reverse("reports_export"))
        self.assertRedirects(export, reverse("plans"), fetch_redirect_response=False)

    def test_paid_plans_and_pilot_have_reports(self):
        for code in ("profesional", "negocio", "piloto"):
            with self.subTest(plan=code):
                Subscription.objects.filter(business=self.business).update(
                    status=Subscription.ACTIVE, plan=Plan.objects.get(code=code)
                )
                self.assertEqual(self.client.get(reverse("reports_export")).status_code, 200)

    def test_login_required(self):
        self.client.logout()
        for name in ("reports", "reports_export"):
            response = self.client.get(reverse(name))
            self.assertIn(reverse("login"), response["Location"])
