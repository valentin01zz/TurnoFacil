"""Versioned legal documents, the public pages, the footer and the publish command."""

from datetime import timedelta
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from legal.models import ImmutableError, LegalDocument
from legal.text import render_document

from .helpers import publish


class DocumentModelTests(TestCase):
    def test_a_published_version_is_never_edited_or_deleted(self):
        document = publish()
        document.body = "otro texto"
        with self.assertRaises(ImmutableError):
            document.save()
        with self.assertRaises(ImmutableError):
            document.delete()

    def test_it_keeps_the_hash_of_the_exact_text(self):
        document = publish(body="hola")
        self.assertEqual(
            document.body_sha256,
            "b221d9dbb083a7f33428d7c2a3c3198ae925614d70210e28716ccaa7cd4ddb79",
        )

    def test_current_is_the_latest_in_force(self):
        self.assertIsNone(LegalDocument.current(LegalDocument.TERMS))
        first = publish(version="1.0", effective_at=timezone.now() - timedelta(days=10))
        publish(version="2.0", effective_at=timezone.now() + timedelta(days=5))
        self.assertEqual(LegalDocument.current(LegalDocument.TERMS), first)


class RenderTests(TestCase):
    def test_headings_lists_and_bold_and_everything_escaped(self):
        html = render_document(
            "# Título\n\nUn **dato** <script>x</script>\n\n- uno\n  sigue\n- dos"
        )
        self.assertIn("<h2>Título</h2>", html)
        self.assertIn("<strong>dato</strong>", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertIn("<ul><li>uno sigue</li><li>dos</li></ul>", html)


class PageTests(TestCase):
    def test_nothing_published_means_no_page_and_no_link(self):
        self.assertEqual(self.client.get(reverse("terms")).status_code, 404)
        self.assertEqual(self.client.get(reverse("privacy")).status_code, 404)
        home = self.client.get(reverse("home"))
        self.assertNotContains(home, reverse("terms"))
        self.assertNotContains(home, reverse("privacy"))

    def test_published_pages_show_version_and_date_and_the_footer_links_them(self):
        publish()
        publish(kind=LegalDocument.PRIVACY, body="Privacidad")
        response = self.client.get(reverse("terms"))
        self.assertContains(response, "Versión 1.0")
        self.assertContains(response, "<strong>negrita</strong>", html=True)
        home = self.client.get(reverse("home"))
        self.assertContains(home, reverse("terms"))
        self.assertContains(home, reverse("privacy"))

    def test_old_versions_stay_reachable(self):
        publish(version="1.0", effective_at=timezone.now() - timedelta(days=10))
        publish(version="2.0", body="Nueva", effective_at=timezone.now() - timedelta(days=1))
        old = self.client.get(reverse("terms_version", args=["1.0"]))
        self.assertContains(old, "esta versión ya no está vigente")
        self.assertContains(
            self.client.get(reverse("terms")), reverse("terms_version", args=["1.0"])
        )

    def test_the_cancellation_and_withdrawal_buttons_are_on_the_home_page(self):
        home = self.client.get(reverse("home"))
        self.assertContains(home, "Botón de baja de servicio")
        self.assertContains(home, "Botón de arrepentimiento")
        self.assertContains(home, reverse("cancel_request"))
        self.assertContains(home, reverse("withdrawal_request"))

    def test_contact_page_only_when_configured(self):
        self.assertEqual(self.client.get(reverse("contact")).status_code, 404)
        self.assertNotContains(self.client.get(reverse("home")), reverse("contact"))
        with self.settings(
            LEGAL_CONTACT_EMAIL="hola@turnofacil.example", LEGAL_OWNER_NAME="Titular Ejemplo"
        ):
            response = self.client.get(reverse("contact"))
            self.assertContains(response, "hola@turnofacil.example")
            self.assertContains(response, "Titular Ejemplo")
            self.assertContains(self.client.get(reverse("home")), reverse("contact"))


@override_settings(LEGAL_CONTACT_EMAIL="")
class PublishCommandTests(TestCase):
    def run_publish(self, text, *args):
        with TemporaryDirectory() as folder:
            path = Path(folder) / "doc.md"
            path.write_text(text, encoding="utf-8")
            out = StringIO()
            call_command("publish_legal_document", "terms", str(path), *args, stdout=out)
            return out.getvalue()

    def test_publishes_a_final_text(self):
        output = self.run_publish("# Términos\n\nTexto final.", "--doc-version", "1.0")
        self.assertIn("Published", output)
        self.assertEqual(LegalDocument.current(LegalDocument.TERMS).version, "1.0")

    def test_refuses_drafts_and_missing_data(self):
        for text in ("# BORRADOR. NO PUBLICAR.", "Titular: [COMPLETAR]", "> Nota: revisar"):
            with self.subTest(text=text), self.assertRaises(CommandError):
                self.run_publish(text, "--doc-version", "1.0")
        self.assertFalse(LegalDocument.objects.exists())

    def test_refuses_an_existing_version(self):
        self.run_publish("Texto.", "--doc-version", "1.0")
        with self.assertRaises(CommandError):
            self.run_publish("Otro texto.", "--doc-version", "1.0")

    def test_the_drafts_in_the_repo_cannot_be_published(self):
        drafts = Path(__file__).resolve().parents[2] / "docs" / "agentic" / "legal"
        for name in ("TERMINOS_BORRADOR.md", "PRIVACIDAD_BORRADOR.md"):
            with self.subTest(name=name), self.assertRaises(CommandError):
                self.run_publish(
                    (drafts / name).read_text(encoding="utf-8"), "--doc-version", "1.0"
                )
