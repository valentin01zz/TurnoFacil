import os
from unittest import mock

from django.contrib.staticfiles import finders
from django.db import OperationalError, connection
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from config.env import database_from_url, env_bool, env_list


class EnvHelpersTests(SimpleTestCase):
    def test_database_from_url(self):
        config = database_from_url("postgresql://user:p%40ss@db.internal:6543/turnofacil")

        self.assertEqual(config["ENGINE"], "django.db.backends.postgresql")
        self.assertEqual(config["NAME"], "turnofacil")
        self.assertEqual(config["USER"], "user")
        self.assertEqual(config["PASSWORD"], "p@ss")
        self.assertEqual(config["HOST"], "db.internal")
        self.assertEqual(config["PORT"], "6543")

    def test_database_from_url_defaults_the_port(self):
        self.assertEqual(database_from_url("postgres://u:p@host/db")["PORT"], "5432")

    def test_database_from_url_rejects_other_engines(self):
        with self.assertRaises(ValueError):
            database_from_url("mysql://u:p@host/db")

    def test_env_bool(self):
        with mock.patch.dict(
            os.environ, {"FLAG_ON": "True", "FLAG_OFF": "false", "FLAG_EMPTY": ""}
        ):
            self.assertTrue(env_bool("FLAG_ON", False))
            self.assertFalse(env_bool("FLAG_OFF", True))
            self.assertTrue(env_bool("FLAG_EMPTY", True))
            self.assertFalse(env_bool("FLAG_MISSING", False))

    def test_env_list(self):
        with mock.patch.dict(os.environ, {"HOSTS": " a.com, b.com ,,"}):
            self.assertEqual(env_list("HOSTS"), ["a.com", "b.com"])
        self.assertEqual(env_list("HOSTS_MISSING", "x,y"), ["x", "y"])


class HealthCheckTests(TestCase):
    def test_answers_ok_without_a_login_or_details(self):
        response = self.client.get("/healthz/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_answers_a_head_request(self):
        self.assertEqual(self.client.head("/healthz/").status_code, 200)

    def test_really_queries_the_database(self):
        with self.assertNumQueries(1):
            self.client.get("/healthz/")

    def test_fails_when_the_database_is_down(self):
        with mock.patch(
            "config.health.connection.cursor",
            side_effect=OperationalError("could not connect to db.internal password=secret"),
        ):
            with self.assertLogs("config.health", level="ERROR") as logs:
                response = self.client.get("/healthz/")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"status": "fail"})
        self.assertNotIn("secret", " ".join(logs.output))
        self.assertNotIn("db.internal", " ".join(logs.output))

    def test_database_connections_have_a_short_timeout(self):
        self.assertEqual(connection.get_connection_params()["connect_timeout"], 5)

    def test_creates_no_session_or_cookie(self):
        response = self.client.get("/healthz/")

        self.assertEqual(len(response.cookies), 0)

    def test_does_not_depend_on_the_host_or_the_https_redirect(self):
        with self.settings(SECURE_SSL_REDIRECT=True, ALLOWED_HOSTS=["turnofacil.online"]):
            response = self.client.get("/healthz/", HTTP_HOST="10.0.0.1:10000")

        self.assertEqual(response.status_code, 200)

    def test_other_paths_are_not_affected(self):
        self.assertEqual(self.client.get("/healthz/otra/").status_code, 404)
        self.assertEqual(self.client.get("/").status_code, 200)


class ErrorPageTests(TestCase):
    def test_unknown_page_uses_the_spanish_404(self):
        with self.settings(DEBUG=False):
            response = self.client.get("/no-existe/")

        self.assertContains(response, "Página no encontrada", status_code=404)

    def test_500_template_renders_without_context(self):
        from django.template.loader import render_to_string

        html = render_to_string("500.html")

        self.assertIn("Algo salió mal", html)


class PanelCopyButtonTests(TestCase):
    def test_copy_button_has_a_fallback_without_https(self):
        from bookings.tests.helpers import create_business

        business = create_business()
        self.client.force_login(business.owner)

        response = self.client.get(reverse("panel"))
        script = finders.find("js/app.js")
        with open(script, encoding="utf-8") as handle:
            source = handle.read()

        self.assertContains(response, 'data-copy="booking-url"')
        self.assertContains(response, "js/app.js")
        self.assertIn("window.isSecureContext", source)
        self.assertIn('document.execCommand("copy")', source)
