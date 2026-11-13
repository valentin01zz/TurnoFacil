"""Publishing news and knowing what each panel profile has not seen yet (HU-38)."""

import logging

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import timezone

from .models import Announcement, AnnouncementCursor

logger = logging.getLogger(__name__)


def profile_key(profile):
    return "owner" if profile.is_owner else f"pro:{profile.professional.pk}"


def visible(profile):
    """News this profile may see, newest first. Only published ones (none dated in the future)."""
    news = Announcement.objects.filter(published_at__lte=timezone.now())
    if not profile.is_owner:
        news = news.exclude(audience=Announcement.OWNER)
    return news


def unseen(business, profile):
    """Published after the business signed up and after this profile last opened the news."""
    cursor = AnnouncementCursor.objects.filter(
        business=business, profile_key=profile_key(profile)
    ).first()
    since = max(business.created_at, cursor.seen_until) if cursor else business.created_at
    return visible(profile).filter(published_at__gt=since)


def mark_seen(business, profile, now=None):
    AnnouncementCursor.objects.update_or_create(
        business=business,
        profile_key=profile_key(profile),
        defaults={"seen_until": now or timezone.now()},
    )


def link_problem(url):
    """Why `url` cannot be an announcement link, or None. Only this site's paths or https."""
    if not url:
        return None
    if url.startswith("/") and not url.startswith("//"):
        return None
    if url.startswith("https://"):
        return None
    return "El link tiene que empezar con / (una página de TurnoFacil) o con https://."


def publish(title, body, link_url="", link_label="", audience=Announcement.EVERYONE, email=False):
    """Create the announcement and, with `email`, send it to every owner with a verified email.

    One email per owner (never a shared recipient list). Returns (announcement, emails sent).
    """
    announcement = Announcement.objects.create(
        title=title.strip(),
        body=body.strip(),
        link_url=link_url.strip(),
        link_label=link_label.strip(),
        audience=audience,
    )
    sent = email_owners(announcement) if email else 0
    return announcement, sent


def email_owners(announcement):
    from businesses.models import Business

    link = announcement.link_url
    if link.startswith("/"):
        link = f"{settings.SITE_URL}{link}"
    context = {"announcement": announcement, "link": link, "site_url": settings.SITE_URL}
    message = render_to_string("announcements/emails/announcement.txt", context)
    sent = 0
    owners = Business.objects.filter(owner__email_verified_at__isnull=False).values_list(
        "owner__email", flat=True
    )
    for email in owners:
        try:
            send_mail(
                subject=announcement.title,
                message=message,
                from_email=None,
                recipient_list=[email],
            )
            sent += 1
        except Exception:
            logger.exception("Could not email announcement %s", announcement.pk)
    return sent
