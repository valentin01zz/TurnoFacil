from django.urls import path

from . import views

urlpatterns = [
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
