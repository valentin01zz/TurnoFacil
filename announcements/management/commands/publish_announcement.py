from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from announcements.models import Announcement
from announcements.services import link_problem, publish

MAX_BODY = 2000


class Command(BaseCommand):
    help = (
        "Publish a news item under the bell of every business panel (HU-38). Operators only. "
        "A published item is not edited: publish a new one."
    )

    def add_arguments(self, parser):
        parser.add_argument("--title", required=True, help="Up to 120 characters")
        body = parser.add_mutually_exclusive_group(required=True)
        body.add_argument("--body", help="The text")
        body.add_argument("--body-file", help="UTF-8 file with the text (for long texts)")
        parser.add_argument("--link", default="", help="A site path like /panel/ or an https URL")
        parser.add_argument("--link-label", default="", help='For example "Ver la política"')
        parser.add_argument(
            "--only-owner", action="store_true", help="Hide it from professionals' profiles"
        )
        parser.add_argument(
            "--email",
            action="store_true",
            help="Also email it to every owner with a verified email",
        )

    def handle(self, title, body, body_file, link, link_label, only_owner, email, **options):
        text = Path(body_file).read_text(encoding="utf-8") if body_file else body
        title, text = title.strip(), (text or "").strip()
        if not title or len(title) > 120:
            raise CommandError("The title must have between 1 and 120 characters.")
        if not text or len(text) > MAX_BODY:
            raise CommandError(f"The text must have between 1 and {MAX_BODY} characters.")
        problem = link_problem(link.strip())
        if problem:
            raise CommandError(problem)
        if link and not link_label:
            link_label = "Ver más"
        announcement, sent = publish(
            title,
            text,
            link_url=link,
            link_label=link_label,
            audience=Announcement.OWNER if only_owner else Announcement.EVERYONE,
            email=email,
        )
        self.stdout.write(
            f"Published announcement {announcement.pk}: {announcement.title}"
            + (f" (emailed to {sent} owners)" if email else "")
        )
