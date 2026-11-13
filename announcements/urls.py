from django.urls import path

from . import views

urlpatterns = [
    path("panel/novedades/", views.news, name="news"),
]
