from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from announcements.services import publish as publish_announcement
from legal.models import LegalDocument

# A text with any of these is a draft or still has data to fill in: it must never be published.
FORBIDDEN = [
    "[COMPLETAR",
    "[PENDIENTE",
    "[FECHA DE VIGENCIA",
    "BORRADOR",
    "NO PUBLICAR",
    "> Nota:",
    "> Requiere:",
]


class Command(BaseCommand):
    help = (
        "Publish a new version of the terms or the privacy policy from a text file. "
        "Operators only, once the Founder (and the lawyer) approved the text. A published "
        "version is never edited: publish a new one."
    )

    def add_arguments(self, parser):
        parser.add_argument("kind", choices=[LegalDocument.TERMS, LegalDocument.PRIVACY])
        parser.add_argument("path", help="UTF-8 text file with the final text")
        parser.add_argument("--doc-version", required=True, help="For example 1.0")
        parser.add_argument(
            "--no-notice",
            action="store_true",
            help="Do not post the news item nor email the owners (only for a first publication).",
        )
        parser.add_argument(
            "--effective",
            help="When it comes into force, ISO 8601 (default: now). Owners accept it from then.",
        )

    def handle(self, kind, path, doc_version, effective=None, no_notice=False, **options):
        version = doc_version
        body = Path(path).read_text(encoding="utf-8").strip()
        if not body:
            raise CommandError("The file is empty.")
        found = [marker for marker in FORBIDDEN if marker in body]
        if found:
            raise CommandError(f"Not published: the text still has {', '.join(found)}.")
        if LegalDocument.objects.filter(kind=kind, version=version).exists():
            raise CommandError(f"Version {version} already exists; publish a new version.")
        effective_at = timezone.now()
        if effective:
            effective_at = parse_datetime(effective)
            if effective_at is None:
                raise CommandError("--effective is not a valid date and time.")
            if timezone.is_naive(effective_at):
                effective_at = timezone.make_aware(effective_at)
        document = LegalDocument.objects.create(
            kind=kind, version=version, body=body, effective_at=effective_at
        )
        self.stdout.write(
            f"Published {document} (sha256 {document.body_sha256}), in force from "
            f"{timezone.localtime(document.effective_at):%Y-%m-%d %H:%M}."
        )
        if not no_notice:
            # The published policy promises to tell the businesses: the bell and an email (HU-38).
            _, sent = notify(document)
            self.stdout.write(f"Posted the news item and emailed {sent} owners.")


NOTICE_PATHS = {LegalDocument.TERMS: "/terminos/", LegalDocument.PRIVACY: "/privacidad/"}


def notify(document):
    article = "los" if document.kind == LegalDocument.TERMS else "la"
    name = f"{article} {document.get_kind_display()}"
    effective = timezone.localtime(document.effective_at)
    return publish_announcement(
        f"Actualizamos {name}",
        f"Publicamos la versión {document.version} de {name}, vigente desde el "
        f"{effective:%d/%m/%Y}. La versión anterior sigue disponible en el sitio.",
        link_url=NOTICE_PATHS[document.kind],
        link_label=f"Leer {name}",
        email=True,
    )
