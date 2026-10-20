import re

from django.conf import settings
from django.test import SimpleTestCase

PAYMENT_VARIABLES = {"PAYMENT_PROVIDER", "MERCADOPAGO_ACCESS_TOKEN", "MERCADOPAGO_WEBHOOK_SECRET"}
# Only the web service answers HTTP requests.
WEB_ONLY = {"ALLOWED_HOSTS"}


def blueprint_keys():
    """Environment variable names per service in render.yaml, without a YAML parser."""
    text = (settings.BASE_DIR / "render.yaml").read_text(encoding="utf-8")
    services = text.split("databases:")[0].split("  - type: ")[1:]
    keys = {}
    for service in services:
        name = re.search(r"^\s+name: (\S+)", service, re.MULTILINE).group(1)
        keys[name] = set(re.findall(r"- key: (\w+)", service))
    return keys


class BlueprintTests(SimpleTestCase):
    def test_web_and_cron_get_the_payment_provider_and_its_credentials(self):
        keys = blueprint_keys()

        self.assertLessEqual(PAYMENT_VARIABLES, keys["turnofacil-web"])
        self.assertLessEqual(PAYMENT_VARIABLES, keys["turnofacil-reminders"])

    def test_the_cron_has_every_web_variable_it_needs(self):
        keys = blueprint_keys()

        self.assertEqual(keys["turnofacil-web"] - WEB_ONLY - keys["turnofacil-reminders"], set())

    def test_secrets_are_never_written_in_the_blueprint(self):
        text = (settings.BASE_DIR / "render.yaml").read_text(encoding="utf-8")

        for key in (
            "MERCADOPAGO_ACCESS_TOKEN",
            "MERCADOPAGO_WEBHOOK_SECRET",
            "EMAIL_HOST_PASSWORD",
        ):
            for block in re.findall(rf"- key: {key}\n(\s+\S.*)", text):
                self.assertIn("sync: false", block)
