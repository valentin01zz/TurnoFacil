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


CONTACT_MESSAGE = "Hola, tengo una consulta sobre TurnoFacil."
OWNER_MESSAGE = "Hola, soy de {name} y necesito ayuda con TurnoFacil."


def support(request):
    """Links to TurnoFacil's support WhatsApp, or empty strings when it is not configured."""
    from bookings.whatsapp import chat_url

    phone = settings.SUPPORT_WHATSAPP
    if not phone:
        return {"support": {"contact_url": "", "owner_url": ""}}

    def owner_url():
        user = request.user
        business = getattr(user, "business", None) if user.is_authenticated else None
        name = business.name if business else ""
        text = OWNER_MESSAGE.format(name=name) if name else CONTACT_MESSAGE
        return chat_url(phone, text) or ""

    return {
        "support": {
            "contact_url": chat_url(phone, CONTACT_MESSAGE) or "",
            "owner_url": SimpleLazyObject(owner_url),
        }
    }
