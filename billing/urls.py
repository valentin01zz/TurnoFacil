from django.urls import path

from . import views

urlpatterns = [
    path("panel/planes/", views.plans, name="plans"),
    path("panel/planes/<slug:code>/elegir/", views.choose, name="choose_plan"),
]
