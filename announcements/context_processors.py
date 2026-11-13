from .services import unseen


def unread(request):
    """How many news items the current panel profile has not seen, for the bell in the header."""
    profile = getattr(request, "panel_profile", None)
    user = getattr(request, "user", None)
    if profile is None or user is None or not user.is_authenticated:
        return {}
    return {"unread_news": unseen(user.business, profile).count()}
