from django.urls import path

from . import views

urlpatterns = [
    path("panel/", views.panel, name="panel"),
    path("panel/services/", views.service_list, name="service_list"),
    path("panel/services/new/", views.service_create, name="service_create"),
    path("panel/services/<int:pk>/edit/", views.service_edit, name="service_edit"),
    path("b/<slug:slug>/", views.booking_page, name="booking_page"),
]
