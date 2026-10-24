from django.shortcuts import redirect

from .services import pending_terms


class TermsAcceptanceRequiredMiddleware:
    """Owners accept the terms version in force before using the panel.

    Nothing is recorded for them: an account that existed before the terms (or before a new version)
    accepts it on its next visit. With no terms published, nobody is asked anything.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if (
            user is not None
            and user.is_authenticated
            and user.is_email_verified
            and request.path.startswith("/panel/")
            and pending_terms(user) is not None
        ):
            return redirect("accept_terms")
        return self.get_response(request)
