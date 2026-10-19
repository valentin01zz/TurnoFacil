from functools import wraps

from django.contrib import messages
from django.shortcuts import redirect

from .access import get_access

READ_ONLY_MESSAGE = (
    "Tu panel está en modo lectura porque no tenés un plan activo. "
    "Elegí un plan para volver a editar."
)


def requires_feature(feature):
    """Run the view only if the owner's business has `feature` now; else go to the plans page.

    Checked on every request, GET and POST alike, so hidden buttons are never the only barrier.
    """

    def decorator(view):
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            access = get_access(request.user.business)
            if not access.can(feature):
                messages.warning(request, READ_ONLY_MESSAGE)
                return redirect("plans")
            request.access = access
            return view(request, *args, **kwargs)

        return wrapper

    return decorator
