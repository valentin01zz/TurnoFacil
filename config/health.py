"""Health check for the external uptime monitor (docs/agentic/DEPLOYMENT.md)."""

import logging

from django.db import connection
from django.http import JsonResponse

logger = logging.getLogger(__name__)

PATH = "/healthz/"


def database_is_up():
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        return True
    except Exception as error:
        # Only the type: the message can include connection details.
        logger.error("Health check could not reach the database: %s", type(error).__name__)
        return False


class HealthCheckMiddleware:
    """Answers before everything else, so the check needs no session and creates no cookie.

    The home and login pages render without the database, so a database outage does not show on
    them. This does. It says only whether the app reaches the database, with no details.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path != PATH:
            return self.get_response(request)
        healthy = database_is_up()
        return JsonResponse({"status": "ok" if healthy else "fail"}, status=200 if healthy else 503)
