from datetime import timedelta

from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts import throttle
from accounts.forms import LOGIN_LOCKED_MESSAGE
from accounts.models import Attempt
from bookings.models import Appointment
from bookings.tests.helpers import (
    create_business,
    create_professional,
    create_service,
    future_date,
    local_dt,
)
from bookings.views import TOO_MANY_BOOKINGS_MESSAGE

PASSWORD = "correct-horse-battery"  # the password create_business gives the owner


class ThrottleTests(TestCase):
    def test_counts_inside_the_window_only(self):
        now = timezone.now()
        for _ in range(3):
            throttle.record("reset", "ana@example.com", now=now - timedelta(minutes=30))

        self.assertTrue(throttle.is_limited("reset", "ana@example.com", now=now))
        self.assertFalse(
            throttle.is_limited("reset", "ana@example.com", now=now + timedelta(hours=1))
        )
        self.assertFalse(throttle.is_limited("reset", "otra@example.com", now=now))

    def test_old_rows_are_cleaned_up(self):
        now = timezone.now()
        throttle.record("reset", "ana@example.com", now=now - timedelta(days=2))

        throttle.record("reset", "ana@example.com", now=now)

        self.assertEqual(Attempt.objects.count(), 1)

    def test_empty_keys_are_never_limited(self):
        throttle.record("signup_ip", "")
        self.assertFalse(throttle.is_limited("signup_ip", ""))
        self.assertFalse(Attempt.objects.exists())

    def test_client_ip_prefers_the_proxy_header(self):
        class Request:
            META = {"HTTP_X_FORWARDED_FOR": "200.1.2.3, 10.0.0.1", "REMOTE_ADDR": "10.0.0.1"}

        self.assertEqual(throttle.client_ip(Request()), "200.1.2.3")
        Request.META = {"REMOTE_ADDR": "10.0.0.9"}
        self.assertEqual(throttle.client_ip(Request()), "10.0.0.9")


def request_with(forwarded, remote="10.0.0.1"):
    class Request:
        META = {"HTTP_X_FORWARDED_FOR": forwarded, "REMOTE_ADDR": remote}

    return Request()


class TrustedProxyTests(TestCase):
    """A client may send its own X-Forwarded-For; only what the trusted proxy appended counts."""

    @override_settings(CLIENT_IP_PROXY_COUNT=1)
    def test_forged_entries_before_the_proxy_are_ignored(self):
        for forged in ("1.1.1.1", "2.2.2.2", "3.3.3.3, 4.4.4.4"):
            ip = throttle.client_ip(request_with(f"{forged}, 200.1.2.3"))
            self.assertEqual(ip, "200.1.2.3")

    @override_settings(CLIENT_IP_PROXY_COUNT=2)
    def test_two_proxies(self):
        ip = throttle.client_ip(request_with("6.6.6.6, 200.1.2.3, 10.0.0.5"))

        self.assertEqual(ip, "200.1.2.3")

    @override_settings(CLIENT_IP_PROXY_COUNT=2)
    def test_fewer_entries_than_proxies_falls_back_to_the_connection(self):
        self.assertEqual(throttle.client_ip(request_with("200.1.2.3")), "10.0.0.1")

    @override_settings(CLIENT_IP_PROXY_COUNT=0)
    def test_without_a_proxy_the_header_is_not_trusted(self):
        self.assertEqual(throttle.client_ip(request_with("1.1.1.1")), "10.0.0.1")

    @override_settings(CLIENT_IP_PROXY_COUNT=1)
    def test_rotating_forged_headers_do_not_escape_the_login_limit(self):
        for attempt in range(30):
            self.client.post(
                reverse("login"),
                {"username": f"cuenta{attempt}@example.com", "password": "wrong"},
                HTTP_X_FORWARDED_FOR=f"9.9.9.{attempt}, 200.1.2.3",
            )

        self.assertTrue(throttle.is_limited("login_ip", "200.1.2.3"))


class LoginLimitTests(TestCase):
    def setUp(self):
        self.business = create_business("ana@example.com")

    def login(self, password, email="ana@example.com", ip="200.1.1.1"):
        return self.client.post(
            reverse("login"),
            {"username": email, "password": password},
            REMOTE_ADDR=ip,
        )

    def test_locks_the_account_after_ten_failures_even_with_the_right_password(self):
        for _ in range(10):
            self.assertNotContains(self.login("mala"), LOGIN_LOCKED_MESSAGE)

        response = self.login(PASSWORD)

        self.assertContains(response, "demasiados intentos fallidos")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_the_lock_follows_the_account_across_networks_and_aliases(self):
        business = create_business("ana.perez@gmail.com", "Barbería Sol")
        for number in range(10):
            self.login("mala", email="ana.perez@gmail.com", ip=f"200.1.1.{number}")

        response = self.login(PASSWORD, email="AnaPerez+x@gmail.com", ip="190.9.9.9")

        self.assertContains(response, "demasiados intentos fallidos")
        self.assertTrue(business.owner.check_password(PASSWORD))

    def test_the_lock_ends_after_fifteen_minutes(self):
        for _ in range(10):
            self.login("mala")
        Attempt.objects.update(created_at=timezone.now() - timedelta(minutes=16))

        response = self.login(PASSWORD)

        self.assertRedirects(response, reverse("panel"), fetch_redirect_response=False)

    def test_a_successful_login_forgets_earlier_failures(self):
        for _ in range(9):
            self.login("mala")
        self.login(PASSWORD)
        self.client.logout()

        for _ in range(9):
            self.assertNotContains(self.login("mala"), LOGIN_LOCKED_MESSAGE)

    def test_one_ip_cannot_try_many_accounts(self):
        for number in range(30):
            self.login("mala", email=f"user{number}@example.com")

        response = self.login(PASSWORD)

        self.assertContains(response, "demasiados intentos fallidos")


class PasswordResetLimitTests(TestCase):
    def setUp(self):
        create_business("ana@example.com")

    def reset(self, email="ana@example.com", ip="200.1.1.1"):
        return self.client.post(reverse("password_reset"), {"email": email}, REMOTE_ADDR=ip)

    def test_at_most_three_emails_per_hour_with_the_same_answer(self):
        for _ in range(5):
            response = self.reset()
            self.assertRedirects(response, reverse("password_reset_done"))

        self.assertEqual(len(mail.outbox), 3)

    def test_unknown_emails_count_too_and_reveal_nothing(self):
        for _ in range(4):
            self.assertRedirects(self.reset("nadie@example.com"), reverse("password_reset_done"))

        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(Attempt.objects.filter(scope="reset").count(), 3)

    def test_one_ip_is_limited_across_accounts(self):
        for number in range(10):
            self.reset(f"user{number}@example.com")

        self.reset("ana@example.com")

        self.assertEqual(len(mail.outbox), 0)


class SignupLimitTests(TestCase):
    def signup(self, number, ip="200.1.1.1"):
        return self.client.post(
            reverse("signup"),
            {
                "business_name": f"Negocio {number}",
                "email": f"dueno{number}@example.com",
                "password": "una-clave-segura-123",
            },
            REMOTE_ADDR=ip,
        )

    def test_five_accounts_per_hour_per_connection(self):
        for number in range(5):
            self.assertEqual(self.signup(number).status_code, 302)
            self.client.logout()

        response = self.signup(99)

        self.assertContains(response, "Se crearon muchas cuentas", status_code=429)
        self.assertEqual(self.signup(100, ip="190.9.9.9").status_code, 302)


class BookingLimitTests(TestCase):
    def setUp(self):
        self.business = create_business()
        self.professional = create_professional(self.business)
        self.service = create_service(self.business, duration=30)
        self.date = future_date()

    def book(self, hour, minute=0, ip="200.1.1.1"):
        return self.client.post(
            reverse("book", args=[self.business.slug]),
            {
                "service": self.service.pk,
                "professional": self.professional.pk,
                "date": self.date.isoformat(),
                "start_at": local_dt(self.date, hour, minute).isoformat(),
                "customer_name": "Laura Gómez",
                "customer_phone": "+54 11 5555-1234",
                "customer_email": "laura@example.com",
                "website": "",
            },
            REMOTE_ADDR=ip,
        )

    def test_twenty_bookings_per_hour_per_connection(self):
        slots = [(hour, minute) for hour in (9, 10, 11, 12, 14, 15, 16, 17) for minute in (0, 30)]
        for hour, minute in slots[:5]:
            self.assertEqual(self.book(hour, minute).status_code, 302)
        Attempt.objects.bulk_create(Attempt(scope="booking_ip", key="200.1.1.1") for _ in range(15))

        response = self.book(*slots[5])

        self.assertContains(response, TOO_MANY_BOOKINGS_MESSAGE, status_code=429)
        self.assertEqual(Appointment.objects.count(), 5)
        self.assertEqual(self.book(*slots[5], ip="190.9.9.9").status_code, 302)

    def test_rejected_bookings_do_not_count(self):
        self.book(9)
        for _ in range(3):
            self.book(9)  # already taken

        self.assertEqual(Attempt.objects.filter(scope="booking_ip").count(), 1)
