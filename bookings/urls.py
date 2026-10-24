from django.urls import path

from . import panel_views, views

urlpatterns = [
    path("panel/appointments/new/", panel_views.appointment_create, name="appointment_create"),
    path(
        "panel/appointments/<int:pk>/reschedule/",
        panel_views.appointment_reschedule,
        name="appointment_reschedule",
    ),
    path(
        "panel/appointments/<int:pk>/cancel/",
        panel_views.appointment_cancel,
        name="appointment_cancel",
    ),
    path(
        "panel/appointments/<int:pk>/deposit/",
        panel_views.appointment_deposit,
        name="appointment_deposit",
    ),
    path("b/<slug:slug>/", views.booking_page, name="booking_page"),
    path("b/<slug:slug>/book/", views.book, name="book"),
    path("t/<str:token>/", views.appointment_detail, name="appointment_detail"),
    path(
        "t/<str:token>/reschedule/",
        views.reschedule_appointment,
        name="reschedule_appointment",
    ),
    path("t/<str:token>/cancel/", views.cancel_appointment, name="cancel_appointment"),
]
