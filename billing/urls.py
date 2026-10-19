from django.urls import path

from . import views

urlpatterns = [
    path("panel/planes/", views.plans, name="plans"),
    path("panel/planes/<slug:code>/elegir/", views.choose, name="choose_plan"),
    path("panel/planes/<slug:code>/pagar/", views.checkout, name="checkout"),
    path("panel/planes/pago/", views.payment_return, name="payment_return"),
    path("panel/planes/baja/", views.cancel, name="cancel_subscription"),
    path("webhooks/mercadopago/", views.mercadopago_webhook, name="mercadopago_webhook"),
]
