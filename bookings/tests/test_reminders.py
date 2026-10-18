from datetime import timedelta
from io import StringIO
from unittest import mock

from django.core import mail
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from bookings.reminders import send_due_reminders

from .helpers import create_appointment, create_business, create_professional, create_service


@override_settings(SITE_URL="https://turnofacil.example")
class ReminderTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.business = create_business(name="Estética Luna")
        cls.ana = create_professional(cls.business, name="Ana")
        cls.service = create_service(cls.business, name="Limpieza facial", duration=50)

    def appointment_in(self, hours, **fields):
        start_at = (timezone.now() + timedelta(hours=hours)).replace(second=0, microsecond=0)
        appointment = create_appointment(self.ana, self.service, start_at)
        appointment.reminder_due_at = start_at - timedelta(hours=24)
        for name, value in fields.items():
            setattr(appointment, name, value)
        appointment.save()
        return appointment

    def test_due_reminder_is_sent_with_details_and_link(self):
        appointment = self.appointment_in(hours=23)

        sent = send_due_reminders()

        self.assertEqual(sent, 1)
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, ["cliente@example.com"])
        self.assertEqual(message.subject, "Recordatorio: tu turno en Estética Luna")
        local_start = timezone.localtime(appointment.start_at)
        for text in ["Estética Luna", "Limpieza facial", "Ana", f"{local_start:%H:%M}"]:
            self.assertIn(text, message.body)
        self.assertIn(f"https://turnofacil.example/t/{appointment.manage_token}/", message.body)
        appointment.refresh_from_db()
        self.assertIsNotNone(appointment.reminder_sent_at)

    def test_reminder_not_yet_due_is_not_sent(self):
        self.appointment_in(hours=30)

        self.assertEqual(send_due_reminders(), 0)
        self.assertEqual(len(mail.outbox), 0)

    def test_running_twice_sends_only_once(self):
        self.appointment_in(hours=23)

        send_due_reminders()
        send_due_reminders()

        self.assertEqual(len(mail.outbox), 1)

    def test_cancelled_appointment_gets_no_reminder(self):
        appointment = self.appointment_in(hours=23)
        appointment.cancel()

        self.assertEqual(send_due_reminders(), 0)

    def test_cancelled_even_with_a_stale_due_date_gets_no_reminder(self):
        self.appointment_in(hours=23, status="cancelled")

        self.assertEqual(send_due_reminders(), 0)

    def test_appointment_that_already_started_gets_no_reminder(self):
        self.appointment_in(hours=-1)

        self.assertEqual(send_due_reminders(), 0)

    def test_appointment_without_email_gets_no_reminder(self):
        self.appointment_in(hours=23, customer_email="")

        self.assertEqual(send_due_reminders(), 0)

    def test_booked_less_than_24_hours_before_has_no_reminder(self):
        self.appointment_in(hours=5, reminder_due_at=None)

        self.assertEqual(send_due_reminders(), 0)

    def test_rescheduled_appointment_is_reminded_for_the_new_date(self):
        appointment = self.appointment_in(hours=23)
        new_start = (timezone.now() + timedelta(days=3)).replace(second=0, microsecond=0)
        appointment.move_to(new_start)

        self.assertEqual(send_due_reminders(), 0)

        later = new_start - timedelta(hours=23)
        self.assertEqual(send_due_reminders(now=later), 1)
        self.assertIn(f"{timezone.localtime(new_start):%H:%M}", mail.outbox[0].body)

    def test_failed_send_is_retried_on_the_next_run(self):
        appointment = self.appointment_in(hours=23)

        with (
            mock.patch("bookings.emails.send_mail", side_effect=OSError("smtp down")),
            self.assertLogs("bookings.emails", level="ERROR"),
        ):
            self.assertEqual(send_due_reminders(), 0)

        appointment.refresh_from_db()
        self.assertIsNone(appointment.reminder_sent_at)
        self.assertEqual(send_due_reminders(), 1)

    def test_command_reports_how_many_were_sent(self):
        self.appointment_in(hours=23)
        self.appointment_in(hours=22)
        out = StringIO()

        call_command("send_reminders", stdout=out)

        self.assertIn("Reminders sent: 2", out.getvalue())
        self.assertEqual(len(mail.outbox), 2)

    @override_settings(CUSTOMER_CHANGE_LIMIT_HOURS=3)
    def test_reminder_states_the_configured_change_limit(self):
        self.appointment_in(hours=23)

        send_due_reminders()

        self.assertIn("hasta 3 horas antes", mail.outbox[0].body)
