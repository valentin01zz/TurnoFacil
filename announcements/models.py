from django.db import models
from django.utils import timezone


class Announcement(models.Model):
    """News for the businesses (HU-38): new features, plan changes, a new legal version.

    Published by an operator with `publish_announcement`, or on its own when a legal document is
    published. Shown under the bell in the panel.
    """

    EVERYONE = "everyone"
    OWNER = "owner"
    AUDIENCES = [(EVERYONE, "Dueño y profesionales"), (OWNER, "Solo el dueño")]

    title = models.CharField("título", max_length=120)
    body = models.TextField("texto", max_length=2000)
    link_url = models.CharField("link", max_length=300, blank=True)
    link_label = models.CharField("texto del link", max_length=60, blank=True)
    audience = models.CharField(max_length=10, choices=AUDIENCES, default=EVERYONE)
    published_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-published_at", "-pk"]

    def __str__(self):
        return self.title


class AnnouncementCursor(models.Model):
    """Until when a panel profile has seen the news. One row per business and profile (the owner,
    or each professional with separate agendas), so what María read stays unread for Mariano."""

    business = models.ForeignKey(
        "businesses.Business", on_delete=models.CASCADE, related_name="announcement_cursors"
    )
    profile_key = models.CharField(max_length=30)
    seen_until = models.DateTimeField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["business", "profile_key"], name="announcement_cursor_unique"
            ),
        ]
