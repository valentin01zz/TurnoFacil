from django.urls import path

from . import profile_views, views

urlpatterns = [
    path("panel/", views.panel, name="panel"),
    path("panel/business/", views.business_edit, name="business_edit"),
    path("panel/business/deposit/", views.deposit_settings, name="deposit_settings"),
    path("panel/business/agendas/", profile_views.agenda_settings, name="agenda_settings"),
    path("panel/perfil/", profile_views.choose_profile, name="choose_profile"),
    path("panel/perfil/cambiar/", profile_views.switch_profile, name="switch_profile"),
    path("panel/perfil/olvide-pin/", profile_views.owner_pin_forgot, name="owner_pin_forgot"),
    path(
        "panel/perfil/nuevo-pin/<str:token>/",
        profile_views.owner_pin_reset,
        name="owner_pin_reset",
    ),
    path("panel/mi-pin/", profile_views.my_pin, name="my_pin"),
    path(
        "confirmar-email/profesional/<str:token>/",
        profile_views.confirm_professional_email,
        name="confirm_professional_email",
    ),
    path("panel/services/", views.service_list, name="service_list"),
    path("panel/services/new/", views.service_create, name="service_create"),
    path("panel/services/<int:pk>/edit/", views.service_edit, name="service_edit"),
    path("panel/professionals/", views.professional_list, name="professional_list"),
    path("panel/professionals/new/", views.professional_create, name="professional_create"),
    path("panel/professionals/<int:pk>/edit/", views.professional_edit, name="professional_edit"),
    path("panel/reports/", views.reports, name="reports"),
    path("panel/reports/export/", views.reports_export, name="reports_export"),
    path("panel/time-off/", views.time_off_list, name="time_off_list"),
    path(
        "panel/time-off/<int:pk>/appointments/",
        views.time_off_appointments,
        name="time_off_appointments",
    ),
    path("panel/time-off/<int:pk>/delete/", views.time_off_delete, name="time_off_delete"),
]
