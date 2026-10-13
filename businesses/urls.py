from django.urls import path

from . import views

urlpatterns = [
    path("panel/", views.panel, name="panel"),
    path("b/<slug:slug>/", views.booking_page, name="booking_page"),
]
