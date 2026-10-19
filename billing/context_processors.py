from .access import get_access


def subscription(request):
    """Expose the owner's access to every panel template (banner, read-only hints)."""
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated or not hasattr(user, "business"):
        return {}
    if not user.is_email_verified:
        return {}  # no trial yet: the verification page explains what to do
    access = getattr(request, "access", None) or get_access(user.business)
    return {"access": access}
