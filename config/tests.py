import os
from unittest import mock

from django.contrib.staticfiles import finders
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
