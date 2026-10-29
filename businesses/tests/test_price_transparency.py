"""Price transparency (HU-36): final prices, "desde" prices with their condition, and the deposit
split into total, deposit and balance for the customer."""

from decimal import Decimal

from django.core import mail
from django.test import TestCase
from django.urls import reverse

from bookings.models import Appointment
from bookings.tests.helpers import (
    create_appointment,
    create_business,
    create_professional,
    create_service,
    future_date,
    local_dt,
    sent_to,
)
from businesses.models import Business, Service
from businesses.pricing import DepositBreakdown, PublicPrice, deposit_breakdown, public_price

from .test_deposit import enable_deposit


def set_price(service, price, varies=False, note=""):
    Service.objects.filter(pk=service.pk).update(price=price, price_varies=varies, price_note=note)
    service.refresh_from_db()
    return service


class ServiceFormTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.business = create_business()

    def setUp(self):
        self.client.force_login(self.business.owner)

    def save(self, **data):
        fields = {"name": "Corte", "duration_minutes": "30", "price": "", "is_active": "on"}
        fields.update(data)
        return self.client.post(reverse("service_create"), fields)

    def test_varying_price_needs_a_minimum_and_a_condition(self):
        for data in (
            {"price_varies": "on", "price_note": "según el largo"},
            {"price_varies": "on", "price": "15000"},
            {"price_varies": "on", "price": "15000", "price_note": "   "},
        ):
            with self.subTest(data=data):
                self.assertEqual(self.save(**data).status_code, 200)
        self.assertFalse(Service.objects.exists())

    def test_varying_price_is_saved_on_one_line(self):
        self.save(price="15000", price_varies="on", price_note="según el\n largo del pelo")
        service = Service.objects.get()
        self.assertTrue(service.price_varies)
        self.assertEqual(service.price_note, "según el largo del pelo")
        self.assertContains(self.client.get(reverse("service_list")), "Desde $&nbsp;15.000")

    def test_fixed_price_drops_a_leftover_condition(self):
        self.save(price="10000", price_note="algo")
        self.assertEqual(Service.objects.get().price_note, "")


class BreakdownTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.business = create_business()
        Business.objects.filter(pk=cls.business.pk).update(show_prices=True)
        cls.business.refresh_from_db()
        cls.service = set_price(create_service(cls.business), Decimal("10000"))

    def test_balance_is_the_price_minus_the_deposit(self):
        deposit = enable_deposit(self.business, amount=Decimal("2000"))
        breakdown = deposit_breakdown(deposit, self.service)
        self.assertEqual(breakdown.price, PublicPrice(Decimal("10000"), False, ""))
        self.assertEqual(breakdown.balance, Decimal("8000"))

    def test_balance_never_goes_below_zero(self):
        price = PublicPrice(Decimal("1000"), False, "")
        self.assertEqual(DepositBreakdown(Decimal("2000"), price).balance, Decimal("0"))

    def test_hidden_prices_give_no_total(self):
        Business.objects.filter(pk=self.business.pk).update(show_prices=False)
        self.service.business.refresh_from_db()
        self.assertIsNone(public_price(self.service))
        deposit = enable_deposit(self.business, amount=Decimal("2000"))
        breakdown = deposit_breakdown(deposit, self.service)
        self.assertIsNone(breakdown.price)
        self.assertIsNone(breakdown.balance)

    def test_saved_appointment_price_wins(self):
        self.assertEqual(public_price(self.service, Decimal("9000")).amount, Decimal("9000"))


class CustomerPagesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.business = create_business("a@example.com", name="Estética Luna")
        Business.objects.filter(pk=cls.business.pk).update(show_prices=True)
        cls.ana = create_professional(cls.business, name="Ana")
        cls.fixed = set_price(create_service(cls.business, name="Corte"), Decimal("10000"))
        cls.varies = set_price(
            create_service(cls.business, name="Color"),
            Decimal("15000"),
            varies=True,
            note="el largo del pelo",
        )
        cls.date = future_date()

    def page(self, service=None):
        params = {"service": service.pk, "professional": self.ana.pk} if service else {}
        return self.client.get(reverse("booking_page", args=[self.business.slug]), params)

    def test_booking_page_shows_final_and_desde_prices(self):
        response = self.page()
        self.assertContains(response, "$&nbsp;10.000")
        self.assertContains(response, "Desde $&nbsp;15.000")
        self.assertContains(response, "El largo del pelo")

    def test_ticket_shows_the_price_and_the_balance_after_the_deposit(self):
        enable_deposit(self.business, amount=Decimal("2000"))
        response = self.page(self.fixed)
        self.assertContains(response, "<dt>Precio</dt><dd>$&nbsp;10.000</dd>", html=False)
        self.assertContains(response, "te quedan $&nbsp;8.000 para pagar en el local")
        response = self.page(self.varies)
        self.assertContains(response, "te quedan $&nbsp;13.000 o más para pagar en el local")

    def test_appointment_detail_splits_total_deposit_and_balance(self):
        enable_deposit(self.business, amount=Decimal("2000"))
        appointment = create_appointment(self.ana, self.fixed, local_dt(self.date, 10))
        Appointment.objects.filter(pk=appointment.pk).update(price=Decimal("10000"))
        response = self.client.get(reverse("appointment_detail", args=[appointment.manage_token]))
        for text in [
            "Precio final",
            "$&nbsp;10.000",
            "Seña",
            "$&nbsp;2.000",
            "Saldo a pagar en el local",
            "$&nbsp;8.000",
        ]:
            self.assertContains(response, text)

    def test_hidden_prices_explain_the_deposit_without_amounts(self):
        Business.objects.filter(pk=self.business.pk).update(show_prices=False)
        enable_deposit(self.business, amount=Decimal("2000"))
        appointment = create_appointment(self.ana, self.fixed, local_dt(self.date, 10))
        response = self.client.get(reverse("appointment_detail", args=[appointment.manage_token]))
        self.assertContains(response, "La seña se descuenta del precio final del servicio")
        self.assertNotContains(response, "10.000")

    def test_confirmation_email_has_the_breakdown(self):
        enable_deposit(self.business, amount=Decimal("2000"))
        self.client.post(
            reverse("book", args=[self.business.slug]),
            {
                "service": self.varies.pk,
                "professional": self.ana.pk,
                "date": self.date.isoformat(),
                "start_at": local_dt(self.date, 10).isoformat(),
                "customer_name": "Laura Gómez",
                "customer_phone": "11 5555 1234",
                "customer_email": "laura@example.com",
            },
        )
        [message] = sent_to("laura@example.com")
        self.assertIn("que se descuenta del total", message.body)
        self.assertIn("Precio desde: $ 15.000 (el largo del pelo)", message.body)
        self.assertIn("Saldo desde: $ 13.000", message.body)
        self.assertEqual(len(mail.outbox), 2)  # customer and owner

    def test_agenda_marks_desde_prices(self):
        self.client.force_login(self.business.owner)
        appointment = create_appointment(self.ana, self.varies, local_dt(self.date, 10))
        Appointment.objects.filter(pk=appointment.pk).update(price=Decimal("15000"))
        response = self.client.get(reverse("panel"), {"date": self.date.isoformat()})
        self.assertContains(response, "desde $&nbsp;15.000")

    def test_reports_warn_about_personal_data_in_the_export(self):
        self.client.force_login(self.business.owner)
        response = self.client.get(reverse("reports"))
        self.assertContains(response, "tiene datos personales de tus clientes")
        self.assertContains(response, 'aria-describedby="export-note"')
