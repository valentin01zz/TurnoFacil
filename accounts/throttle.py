"""Rate limits for public actions (QA risk R1), stored in the database so every worker shares them.

Limits by account (email) cannot be dodged by changing networks; limits by IP are a second layer.
The IP comes from X-Forwarded-For as set by the hosting proxy, so it is best effort.
"""

import logging
from datetime import timedelta

from django.utils import timezone

from .models import Attempt

logger = logging.getLogger(__name__)

# scope: (maximum attempts, window)
LIMITS = {
    "login": (10, timedelta(minutes=15)),  # failed logins per account
    "login_ip": (30, timedelta(minutes=15)),  # failed logins per IP
    "reset": (3, timedelta(hours=1)),  # password reset emails per account
    "reset_ip": (10, timedelta(hours=1)),
    "signup_ip": (5, timedelta(hours=1)),  # new accounts per IP
    "booking_ip": (20, timedelta(hours=1)),  # online bookings per IP
}
KEEP = timedelta(days=1)  # longer than any window


def client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.split(",")[0].strip()[:254]
    return request.META.get("REMOTE_ADDR", "")[:254]


def is_limited(scope, key, now=None):
    if not key:
        return False
    now = now or timezone.now()
    limit, window = LIMITS[scope]
    count = Attempt.objects.filter(scope=scope, key=key, created_at__gt=now - window).count()
    if count >= limit:
        logger.warning("Rate limit reached: %s", scope)
        return True
    return False


def record(scope, key, now=None):
    if not key:
        return
    now = now or timezone.now()
    Attempt.objects.create(scope=scope, key=key[:254], created_at=now)
    Attempt.objects.filter(created_at__lt=now - KEEP).delete()


def clear(scope, key):
    Attempt.objects.filter(scope=scope, key=key).delete()
