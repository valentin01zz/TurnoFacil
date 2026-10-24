"""Deposit (seña) by bank transfer: Profesional and Negocio plans only, shown as instructions."""

from datetime import timedelta
from decimal import Decimal

from django.apps import apps as django_apps
from django.core import mail
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from billing.catalog import BOOKING_DEPOSIT
from billing.models import Plan
from billing.tests.helpers import end_trial, set_active
from bookings.emails import send_confirmation
from bookings.models import Appointment
from bookings.tests.helpers import (
    create_appointment,
    create_business,
    create_professional,
    create_service,
    future_date,
    local_dt,
)
from businesses.deposit import public_deposit
from businesses.models import DepositSettings

GRANT = __import__("billing.migrations.0004_grant_booking_deposit", fromlist=["grant", "revoke"])

VALID = {
    "enabled": "on",
    "amount": "5000",
    "holder_name": "Ana Pérez",
    "transfer_alias": "estetica.luna",
    "cbu_cvu": "",
    "holder_tax_id": "20-12345678-9",
    "instructions": "Mandá el comprobante por WhatsApp.",
}


def enable_deposit(business, **fields):
    values = {
        "enabled": True,
        "amount": Decimal("5000"),
        "holder_name": "Ana Pérez",
        "transfer_alias": "estetica.luna",
        **fields,
    }
    return DepositSettings.objects.create(business=business, **values)


def on_plan(business, code):
    set_active(business, code, timezone.now() + timedelta(days=20))
    return business


class DepositModelTests(TestCase):
    def setUp(self):
        self.business = create_business()

    def test_one_settings_per_business(self):
        enable_deposit(self.business)

        with self.assertRaises(IntegrityError), transaction.atomic():
            DepositSettings.objects.create(business=self.business)

    def test_turned_off_it_needs_nothing(self):
        deposit = DepositSettings.objects.create(business=self.business)

        self.assertFalse(deposit.enabled)
        self.assertIsNone(deposit.amount)

    def test_the_amount_is_positive(self):
        for amount in (Decimal("0"), Decimal("-10")):
            with self.subTest(amount), self.assertRaises(IntegrityError), transaction.atomic():
                DepositSettings.objects.create(business=self.business, amount=amount)

    def test_turned_on_it_needs_amount_holder_and_destination(self):
        incomplete = [
            {"amount": None},
            {"holder_name": ""},
            {"transfer_alias": "", "cbu_cvu": ""},
        ]
        for fields in incomplete:
            with self.subTest(fields), self.assertRaises(IntegrityError), transaction.atomic():
                enable_deposit(self.business, **fields)

    def test_a_cbu_alone_is_a_destination(self):
        deposit = enable_deposit(self.business, transfer_alias="", cbu_cvu="0" * 22)

        self.assertTrue(deposit.enabled)


class DepositPlanMigrationTests(TestCase):
    def test_profesional_negocio_and_piloto_get_the_deposit(self):
        plans = {plan.code: plan.features for plan in Plan.objects.all()}

        self.assertIn(BOOKING_DEPOSIT, plans["profesional"])
        self.assertIn(BOOKING_DEPOSIT, plans["negocio"])
        self.assertNotIn(BOOKING_DEPOSIT, plans["esencial"])
        self.assertIn(BOOKING_DEPOSIT, plans["piloto"])

    def test_the_migration_can_be_reverted_and_applied_again(self):
        GRANT.revoke(django_apps, None)
        self.assertFalse(Plan.objects.filter(features__contains=[BOOKING_DEPOSIT]).exists())

        GRANT.grant(django_apps, None)
        GRANT.grant(django_apps, None)

        negocio = Plan.objects.get(code="negocio")
        self.assertEqual(negocio.features.count(BOOKING_DEPOSIT), 1)


class DepositSettingsPageTests(TestCase):
    def setUp(self):
        self.business = create_business()
        self.url = reverse("deposit_settings")
        self.client.force_login(self.business.owner)

    def post(self, **changes):
        return self.client.post(self.url, {**VALID, **changes})

    def test_profesional_negocio_piloto_and_the_trial_can_turn_it_on(self):
        for index, plan in enumerate(("profesional", "negocio", "piloto", None)):
            with self.subTest(plan or "trial"):
                business = create_business(f"dueño{index}@example.com", f"Negocio {index}")
                if plan:
                    on_plan(business, plan)
                self.client.force_login(business.owner)

                response = self.post()

                self.assertRedirects(response, self.url)
                deposit = DepositSettings.objects.get(business=business)
                self.assertTrue(deposit.enabled)
                self.assertEqual(deposit.amount, Decimal("5000"))

    def test_saving_shows_the_preview(self):
        self.post()

        response = self.client.get(self.url)

        self.assertContains(response, "Así lo ven tus clientes")
        self.assertContains(response, "$ 5.000")
        self.assertContains(response, "estetica.luna")
        self.assertContains(response, "TurnoFacil no recibe el dinero ni verifica el pago")

    def test_esencial_sees_the_plans_and_a_forged_post_saves_nothing(self):
        on_plan(self.business, "esencial")

        page = self.client.get(self.url)
        response = self.post()

        self.assertContains(page, "planes <strong>Profesional</strong> y <strong>Negocio</strong>")
        self.assertNotContains(page, 'name="amount"')
        self.assertRedirects(response, self.url)
        self.assertFalse(DepositSettings.objects.exists())

    def test_read_only_cannot_change_it_and_keeps_what_was_saved(self):
        enable_deposit(self.business, amount=Decimal("3000"))
        end_trial(self.business)

        response = self.post(amount="9000")

        self.assertRedirects(response, reverse("plans"), fetch_redirect_response=False)
        self.assertEqual(DepositSettings.objects.get().amount, Decimal("3000"))

    def test_an_owner_only_changes_their_own_business(self):
        other = create_business("b@example.com", "Barbería Sur")
        enable_deposit(other, holder_name="Bruno Sur")

        self.post(holder_name="Ana Pérez")

        self.assertEqual(DepositSettings.objects.get(business=other).holder_name, "Bruno Sur")
        self.assertEqual(
            DepositSettings.objects.get(business=self.business).holder_name, "Ana Pérez"
        )

    def test_it_can_be_turned_off_keeping_the_details(self):
        enable_deposit(self.business)
        data = {**VALID}
        del data["enabled"]

        self.client.post(self.url, data)

        deposit = DepositSettings.objects.get()
        self.assertFalse(deposit.enabled)
        self.assertEqual(deposit.transfer_alias, "estetica.luna")

    def test_needs_login(self):
        self.client.logout()

        self.assertRedirects(self.client.get(self.url), f"{reverse('login')}?next={self.url}")

    def test_mi_negocio_links_to_it(self):
        self.assertContains(self.client.get(reverse("business_edit")), self.url)


class DepositValidationTests(TestCase):
    def setUp(self):
        self.business = create_business()
        self.client.force_login(self.business.owner)

    def post(self, **changes):
        return self.client.post(reverse("deposit_settings"), {**VALID, **changes})

    def assert_rejected(self, message, **changes):
        response = self.post(**changes)

        self.assertEqual(response.status_code, 200, changes)
        self.assertContains(response, message)
        self.assertFalse(DepositSettings.objects.exists())

    def test_amount_must_be_a_positive_number_with_cents_at_most(self):
        self.assert_rejected("El monto tiene que ser mayor a cero.", amount="0")
        self.assert_rejected("El monto tiene que ser mayor a cero.", amount="-100")
        self.assert_rejected("Introduzca un número", amount="cinco mil")
        self.assert_rejected("decimal", amount="10.555")
        self.assert_rejected("dígitos", amount="123456789")

    def test_incomplete_settings_are_rejected(self):
        self.assert_rejected("cargá el monto", amount="")
        self.assert_rejected("cargá el titular", holder_name="")
        self.assert_rejected("cargá el alias o el CBU/CVU", transfer_alias="", cbu_cvu="")

    def test_alias_cbu_and_tax_id_formats(self):
        self.assert_rejected("El alias tiene entre 6 y 20", transfer_alias="abc")
        self.assert_rejected("El alias tiene entre 6 y 20", transfer_alias="alias con espacios")
        self.assert_rejected("El CBU o CVU tiene 22 números", cbu_cvu="123")
        self.assert_rejected("El CUIT o CUIL tiene 11 números", holder_tax_id="20-1234")

    def test_values_are_normalized(self):
        self.post(cbu_cvu="0000003 100-9876543210 12", holder_tax_id="20123456789")

        deposit = DepositSettings.objects.get()
        self.assertEqual(deposit.cbu_cvu, "0000003100987654321012")
        self.assertEqual(deposit.holder_tax_id, "20-12345678-9")

    def test_texts_over_the_limit_are_rejected(self):
        self.assert_rejected("como máximo 100 caracteres", holder_name="A" * 101)
        self.assert_rejected("como máximo 300 caracteres", instructions="x" * 301)

    def test_turned_off_it_needs_no_details(self):
        response = self.client.post(reverse("deposit_settings"), {"amount": "", "holder_name": ""})

        self.assertRedirects(response, reverse("deposit_settings"))
        self.assertFalse(DepositSettings.objects.get().enabled)


class PublicDepositTests(TestCase):
    def setUp(self):
        self.business = create_business()
        self.ana = create_professional(self.business)
        self.service = create_service(self.business)
        self.date = future_date()

    def appointment(self, business=None):
        business = business or self.business
        professional = self.ana if business == self.business else create_professional(business)
        service = self.service if business == self.business else create_service(business)
        return create_appointment(professional, service, local_dt(self.date, 10))

    def detail(self, appointment):
        return self.client.get(reverse("appointment_detail", args=[appointment.manage_token]))

    def test_the_booking_detail_shows_the_transfer_details(self):
        enable_deposit(self.business, cbu_cvu="0" * 22, holder_tax_id="20-12345678-9")

        response = self.detail(self.appointment())

        for text in (
            "Seña por transferencia",
            "$ 5.000",
            "Ana Pérez",
            "estetica.luna",
            "0" * 22,
            "20-12345678-9",
            "TurnoFacil no recibe el dinero ni verifica el pago",
        ):
            self.assertContains(response, text)
        self.assertNotContains(response, "pagada")

    def test_turned_off_or_missing_shows_nothing(self):
        appointment = self.appointment()
        self.assertNotContains(self.detail(appointment), "Seña por transferencia")

        DepositSettings.objects.create(business=self.business, enabled=False)

        self.assertNotContains(self.detail(appointment), "Seña por transferencia")

    def test_a_plan_without_the_feature_hides_it_and_keeps_it(self):
        enable_deposit(self.business)
        appointment = self.appointment()

        on_plan(self.business, "esencial")
        self.assertNotContains(self.detail(appointment), "Seña por transferencia")

        # Read-only: the paid period of a plan with the feature is over.
        set_active(self.business, "profesional", timezone.now() - timedelta(days=10))
        self.assertIsNone(public_deposit(self.business))
        self.assertNotContains(self.detail(appointment), "Seña por transferencia")
        self.assertTrue(DepositSettings.objects.get().enabled)

    def test_a_booking_never_shows_another_business_deposit(self):
        other = create_business("b@example.com", "Barbería Sur")
        enable_deposit(other, holder_name="Bruno Sur", transfer_alias="barberia.sur")

        response = self.detail(self.appointment())

        self.assertNotContains(response, "barberia.sur")
        self.assertNotContains(response, "Bruno Sur")
        self.assertContains(self.detail(self.appointment(business=other)), "barberia.sur")

    def test_business_texts_are_escaped(self):
        enable_deposit(
            self.business,
            holder_name="<b>Ana</b>",
            instructions='<script>alert("x")</script>',
        )

        response = self.detail(self.appointment())

        self.assertNotContains(response, '<script>alert("x")</script>')
        self.assertContains(response, "&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt;")
        self.assertContains(response, "&lt;b&gt;Ana&lt;/b&gt;")

    def test_booking_works_and_the_page_mentions_the_deposit(self):
        enable_deposit(self.business)
        page = self.client.get(
            reverse("booking_page", args=[self.business.slug]),
            {"service": self.service.pk, "professional": self.ana.pk, "date": self.date},
        )
        response = self.client.post(
            reverse("book", args=[self.business.slug]),
            {
                "service": self.service.pk,
                "professional": self.ana.pk,
                "date": self.date.isoformat(),
                "start_at": local_dt(self.date, 9).isoformat(),
                "customer_name": "Laura Gómez",
                "customer_phone": "+54 11 5555-1234",
                "customer_email": "laura@example.com",
                "website": "",
            },
            follow=True,
        )

        self.assertContains(page, "pide una seña de $ 5.000 por transferencia")
        appointment = Appointment.objects.get()
        self.assertEqual(appointment.status, Appointment.CONFIRMED)
        self.assertContains(response, "Seña por transferencia")
        self.assertIn("Seña:", mail.outbox[0].body)

    def test_booking_works_without_deposit_settings(self):
        response = self.client.post(
            reverse("book", args=[self.business.slug]),
            {
                "service": self.service.pk,
                "professional": self.ana.pk,
                "date": self.date.isoformat(),
                "start_at": local_dt(self.date, 9).isoformat(),
                "customer_name": "Laura Gómez",
                "customer_phone": "+54 11 5555-1234",
                "customer_email": "laura@example.com",
                "website": "",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(Appointment.objects.get().status, Appointment.CONFIRMED)
        self.assertNotIn("Seña", mail.outbox[0].body)

    def test_the_confirmation_email_includes_it_only_when_shown(self):
        appointment = self.appointment()

        send_confirmation(appointment, "https://turnofacil.example/turno/x/")
        enable_deposit(self.business, instructions="Mandá el comprobante.")
        send_confirmation(appointment, "https://turnofacil.example/turno/x/")

        without, with_deposit = mail.outbox
        self.assertNotIn("Seña", without.body)
        self.assertIn(
            "Seña: Estética Luna pide una seña de $ 5.000 por transferencia.", with_deposit.body
        )
        self.assertIn("Alias: estetica.luna", with_deposit.body)
        self.assertIn("Mandá el comprobante.", with_deposit.body)
        self.assertIn("TurnoFacil no recibe el dinero ni verifica el pago", with_deposit.body)
