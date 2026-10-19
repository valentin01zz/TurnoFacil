from django.shortcuts import redirect


class EmailVerificationRequiredMiddleware:
    """Owners must confirm their email before using the panel (and before their trial starts)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if (
            user is not None
            and user.is_authenticated
            and not user.is_email_verified
            and request.path.startswith("/panel/")
        ):
            return redirect("verify_email_pending")
        return self.get_response(request)
