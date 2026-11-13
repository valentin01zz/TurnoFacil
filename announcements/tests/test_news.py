"""News under the bell (HU-38): from an operator or a new legal version, read per profile."""

from datetime import timedelta
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core import mail
from django.core.management import CommandError, call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from announcements.models import Announcement
from announcements.services import link_problem, publish
from bookings.tests.helpers import create_business, create_professional
from businesses.models import Business
from businesses.profiles import hash_pin


def announce(title="Agendas separadas", days_ago=0, **kwargs):
    item, _ = publish(title, "Ahora cada profesional puede tener su agenda.", **kwargs)
    if days_ago:
        Announcement.objects.filter(pk=item.pk).update(
            published_at=timezone.now() - timedelta(days=days_ago)
        )
    return item


class BellTests(TestCase):
    def setUp(self):
        self.business = create_business("a@example.com", name="Consultorio Pies")
        self.client.force_login(self.business.owner)

    def panel(self):
        return self.client.get(reverse("panel"))

    def test_bell_counts_unseen_news_and_the_page_clears_it(self):
        announce("Uno")
        announce("Dos")
        response = self.panel()
        self.assertEqual(response.context["unread_news"], 2)
        self.assertContains(response, '<span class="bell-count" aria-hidden="true">2</span>')

        page = self.client.get(reverse("news"))
        self.assertContains(page, "Uno")
        self.assertContains(page, "Nuevo", count=2)
        self.assertEqual(self.panel().context["unread_news"], 0)
        self.assertNotContains(self.client.get(reverse("news")), ">Nuevo<")

    def test_news_from_before_signing_up_are_not_unread(self):
        announce("Vieja", days_ago=30)
        Business.objects.filter(pk=self.business.pk).update(
            created_at=timezone.now() - timedelta(days=1)
        )
        self.assertEqual(self.panel().context["unread_news"], 0)
        self.assertContains(self.client.get(reverse("news")), "Vieja")  # still in the history

    def test_future_news_wait_until_their_date(self):
        item = announce("Mañana")
        Announcement.objects.filter(pk=item.pk).update(
            published_at=timezone.now() + timedelta(days=1)
        )
        self.assertEqual(self.panel().context["unread_news"], 0)
        self.assertNotContains(self.client.get(reverse("news")), "Mañana")

    def test_link_and_text_are_escaped(self):
        publish("<b>Título</b>", "Texto <script>x</script>", link_url="/privacidad/")
        page = self.client.get(reverse("news"))
        self.assertNotContains(page, "<script>x</script>")
        self.assertContains(page, "&lt;b&gt;Título&lt;/b&gt;")
        self.assertContains(page, 'href="/privacidad/"')

    def test_login_required(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse("news")).status_code, 302)


class ProfileTests(TestCase):
    def setUp(self):
        self.business = create_business("a@example.com", name="Consultorio Pies")
        self.maria = create_professional(self.business, name="María")
        self.mariano = create_professional(self.business, name="Mariano")
        for professional, pin in ((self.maria, "7391"), (self.mariano, "4826")):
            professional.pin = hash_pin(pin)
            professional.save()
        Business.objects.filter(pk=self.business.pk).update(
            separate_agendas=True, owner_pin=hash_pin("2580")
        )
        self.client.force_login(self.business.owner)

    def as_profile(self, profile, pin):
        self.client.post(reverse("choose_profile"), {"profile": profile, "pin": pin})

    def unread(self):
        return self.client.get(reverse("panel")).context["unread_news"]

    def test_each_profile_reads_on_its_own(self):
        announce("Para todos")
        self.as_profile(self.maria.pk, "7391")
        self.client.get(reverse("news"))
        self.assertEqual(self.unread(), 0)
        self.as_profile(self.mariano.pk, "4826")
        self.assertEqual(self.unread(), 1)

    def test_owner_only_news_are_hidden_from_professionals(self):
        announce("Solo dueño", audience=Announcement.OWNER)
        self.as_profile(self.maria.pk, "7391")
        self.assertEqual(self.unread(), 0)
        self.assertNotContains(self.client.get(reverse("news")), "Solo dueño")
        self.as_profile("owner", "2580")
        self.assertEqual(self.unread(), 1)

    def test_without_a_profile_there_is_no_bell(self):
        response = self.client.get(reverse("choose_profile"))
        self.assertNotContains(response, reverse("news"))


class PublishCommandTests(TestCase):
    def test_publish_and_email_every_verified_owner_one_by_one(self):
        create_business("a@example.com", name="Uno")
        create_business("b@example.com", name="Dos")
        unverified = create_business("c@example.com", name="Tres")
        unverified.owner.email_verified_at = None
        unverified.owner.save()
        out = StringIO()
        call_command(
            "publish_announcement",
            "--title=Novedad",
            "--body=Texto de la novedad",
            "--link=/panel/",
            "--email",
            stdout=out,
        )
        self.assertIn("emailed to 2 owners", out.getvalue())
        self.assertEqual(sorted(m.to[0] for m in mail.outbox), ["a@example.com", "b@example.com"])
        self.assertTrue(all(len(m.to) == 1 and not m.cc and not m.bcc for m in mail.outbox))
        self.assertIn("Texto de la novedad", mail.outbox[0].body)
        item = Announcement.objects.get()
        self.assertEqual((item.link_url, item.link_label), ("/panel/", "Ver más"))

    def test_without_email_flag_nobody_is_emailed(self):
        create_business()
        call_command("publish_announcement", "--title=T", "--body=B", stdout=StringIO())
        self.assertEqual(mail.outbox, [])

    def test_bad_input_is_refused(self):
        cases = [
            ["--title=", "--body=B"],
            ["--title=" + "x" * 121, "--body=B"],
            ["--title=T", "--body=" + "x" * 2001],
            ["--title=T", "--body=B", "--link=javascript:alert(1)"],
            ["--title=T", "--body=B", "--link=http://insecure.example"],
            ["--title=T", "--body=B", "--link=//evil.example"],
        ]
        for args in cases:
            with self.subTest(args=args[:1]), self.assertRaises(CommandError):
                call_command("publish_announcement", *args, stdout=StringIO())
        self.assertFalse(Announcement.objects.exists())

    def test_link_rules(self):
        self.assertIsNone(link_problem(""))
        self.assertIsNone(link_problem("/privacidad/"))
        self.assertIsNone(link_problem("https://turnofacil.online/"))
        self.assertIsNotNone(link_problem("//evil.example"))


class LegalNoticeTests(TestCase):
    def publish(self, *extra):
        with TemporaryDirectory() as folder:
            path = Path(folder) / "privacidad.md"
            path.write_text("## 1. Texto final de la política", encoding="utf-8")
            call_command(
                "publish_legal_document",
                "privacy",
                str(path),
                "--doc-version",
                "9.1",
                *extra,
                stdout=StringIO(),
            )

    def test_new_legal_version_posts_news_and_emails_owners(self):
        create_business("a@example.com", name="Uno")
        self.publish()
        item = Announcement.objects.get()
        self.assertEqual(item.title, "Actualizamos la Política de Privacidad")
        self.assertIn("versión 9.1", item.body)
        self.assertEqual(item.link_url, "/privacidad/")
        [message] = mail.outbox
        self.assertEqual(message.to, ["a@example.com"])
        self.assertIn("/privacidad/", message.body)

    def test_no_notice_flag_stays_quiet(self):
        create_business("a@example.com", name="Uno")
        self.publish("--no-notice")
        self.assertFalse(Announcement.objects.exists())
        self.assertEqual(mail.outbox, [])
