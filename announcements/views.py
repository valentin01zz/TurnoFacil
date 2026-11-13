from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone

from .services import mark_seen, unseen, visible


@login_required
def news(request):
    """Every news item for this profile; the new ones are marked, then counted as seen."""
    business, profile = request.user.business, request.panel_profile
    now = timezone.now()
    new_ids = set(unseen(business, profile).values_list("pk", flat=True))
    items = list(visible(profile)[:50])
    for item in items:
        item.is_new = item.pk in new_ids
    mark_seen(business, profile, now)
    # The header counted before this visit; it reads zero from now on.
    return render(request, "announcements/news.html", {"items": items, "unread_news": 0})
