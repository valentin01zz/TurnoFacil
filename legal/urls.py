from django.urls import path

from . import views
from .models import LegalDocument, ServiceRequest

urlpatterns = [
    path("terminos/", views.legal_document, {"kind": LegalDocument.TERMS}, name="terms"),
    path(
        "terminos/v/<str:version>/",
        views.legal_document_version,
        {"kind": LegalDocument.TERMS},
        name="terms_version",
    ),
    path("privacidad/", views.legal_document, {"kind": LegalDocument.PRIVACY}, name="privacy"),
    path(
        "privacidad/v/<str:version>/",
        views.legal_document_version,
        {"kind": LegalDocument.PRIVACY},
        name="privacy_version",
    ),
    path("contacto/", views.contact, name="contact"),
    path("baja/", views.service_request, {"kind": ServiceRequest.CANCEL}, name="cancel_request"),
    path(
        "arrepentimiento/",
        views.service_request,
        {"kind": ServiceRequest.WITHDRAWAL},
        name="withdrawal_request",
    ),
    path(
        "mis-datos/",
        views.service_request,
        {"kind": ServiceRequest.DELETION},
        name="deletion_request",
    ),
    path(
        "solicitud/<str:token>/",
        views.service_request_confirm,
        name="service_request_confirm",
    ),
    path("aceptar-terminos/", views.accept_new_terms, name="accept_terms"),
]
