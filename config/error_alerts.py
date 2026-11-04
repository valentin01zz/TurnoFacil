"""Email the operator when the site answers with a server error (500).

Only the error and where it happened: never the request's data (customer names, phones, emails) nor
the settings. The same error is reported at most once every ALERT_EVERY seconds per process, so a
broken page cannot spend the email quota.
"""

import logging
import time
import traceback

from django.conf import settings
from django.core.mail import mail_admins

ALERT_EVERY = 15 * 60


class ErrorEmailHandler(logging.Handler):
    def __init__(self):
        super().__init__(level=logging.ERROR)
        self.last_sent = {}

    def emit(self, record):
        if not settings.ADMINS:
            return
        error = record.exc_info[1] if record.exc_info else None
        key = (record.name, type(error).__name__, record.pathname, record.lineno)
        now = time.monotonic()
        if now - self.last_sent.get(key, -ALERT_EVERY) < ALERT_EVERY:
            return
        self.last_sent[key] = now
        request = getattr(record, "request", None)
        where = f"{request.method} {request.path}" if request is not None else record.name
        lines = [f"Error en {where}", ""]
        if record.exc_info:
            lines += traceback.format_exception(*record.exc_info)
        else:
            lines.append(record.getMessage())
        try:
            mail_admins(f"Error {type(error).__name__ if error else ''} en {where}", "".join(lines))
        except Exception:
            # Never let the alert itself break the request that failed.
            pass
