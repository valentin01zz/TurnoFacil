from django.conf import settings
from django.utils import timezone
from django.utils.functional import SimpleLazyObject

from .models import LegalDocument


def published_kinds():
    return set(
        LegalDocument.objects.filter(effective_at__lte=timezone.now()).values_list(
            "kind", flat=True
        )
    )


def legal_links(request):
    """Which legal pages exist, for the footer. Queried only when a template uses it."""
    kinds = SimpleLazyObject(published_kinds)
    return {
        "legal_links": {
            "terms": SimpleLazyObject(lambda: LegalDocument.TERMS in kinds),
            "privacy": SimpleLazyObject(lambda: LegalDocument.PRIVACY in kinds),
            "contact": bool(settings.LEGAL_CONTACT_EMAIL),
        }
    }
