"""Mercado Pago subscriptions (ADR-0005), over its REST API with the standard library.

Rules that keep this safe:
- The owner pays on Mercado Pago's own checkout; card data never reaches TurnoFacil.
- A notification is only a hint: its signature is checked, and then the real state is always read
  back from the API with our own credentials before anything changes.
- Applying the same state twice changes nothing, so retried or repeated notifications are harmless.
"""

import hashlib
import hmac
import json
import logging
import uuid
from datetime import timedelta
from datetime import timezone as dt_timezone
from urllib import error as urlerror
from urllib import request as urlrequest
from urllib.parse import quote

from django.conf import settings
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from . import services
from .models import Subscription
from .payments import CheckoutResult, PaymentError, PaymentNotFound, PaymentProvider

logger = logging.getLogger(__name__)

NAME = "mercadopago"
PREAPPROVAL_TOPICS = {"subscription_preapproval", "preapproval"}
PAYMENT_TOPICS = {"subscription_authorized_payment", "authorized_payment"}
# How long the reconciliation keeps asking about a checkout the owner may have abandoned.
PENDING_SYNC_DAYS = 7


def external_reference(subscription):
    return f"turnofacil-sub-{subscription.pk}"


def parse_date(value):
    return parse_datetime(value) if value else None


def api_date(moment):
    return moment.astimezone(dt_timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def valid_signature(secret, signature_header, request_id, data_id):
    """Check Mercado Pago's `x-signature` header (HMAC-SHA256 of the documented manifest)."""
    parts = {}
    for item in (signature_header or "").split(","):
        key, _, value = item.strip().partition("=")
        parts[key] = value
    ts, received = parts.get("ts"), parts.get("v1")
    if not (secret and ts and received):
        return False
    manifest = ""
    if data_id:
        manifest += f"id:{data_id.lower()};"
    if request_id:
        manifest += f"request-id:{request_id};"
    manifest += f"ts:{ts};"
    expected = hmac.new(secret.encode(), manifest.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, received)


class MercadoPagoClient:
    def __init__(self, access_token=None, base_url=None, timeout=10):
        self.access_token = access_token or settings.MERCADOPAGO_ACCESS_TOKEN
        self.base_url = (base_url or settings.MERCADOPAGO_API_URL).rstrip("/")
        self.timeout = timeout

    def request(self, method, path, body=None):
        if not self.access_token:
            raise PaymentError("Falta configurar MERCADOPAGO_ACCESS_TOKEN")
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
        if method == "POST":
            headers["X-Idempotency-Key"] = str(uuid.uuid4())
        data = json.dumps(body).encode() if body is not None else None
        req = urlrequest.Request(self.base_url + path, data=data, headers=headers, method=method)
        try:
            with urlrequest.urlopen(req, timeout=self.timeout) as response:
                return json.loads(response.read() or b"{}")
        except urlerror.HTTPError as exc:
            detail = exc.read()[:300].decode(errors="replace")
            error_class = PaymentNotFound if exc.code == 404 else PaymentError
            raise error_class(f"Mercado Pago respondió {exc.code}: {detail}") from exc
        except (urlerror.URLError, TimeoutError, ValueError) as exc:
            raise PaymentError(f"No pudimos comunicarnos con Mercado Pago: {exc}") from exc

    def get_preapproval(self, preapproval_id):
        return self.request("GET", f"/preapproval/{quote(str(preapproval_id), safe='')}")

    def create_preapproval(self, body):
        return self.request("POST", "/preapproval", body)

    def update_preapproval(self, preapproval_id, body):
        return self.request("PUT", f"/preapproval/{quote(str(preapproval_id), safe='')}", body)

    def get_authorized_payment(self, payment_id):
        return self.request("GET", f"/authorized_payments/{quote(str(payment_id), safe='')}")


def find_subscription(preapproval_id):
    if not preapproval_id:
        return None
    return Subscription.objects.filter(
        provider=NAME, provider_subscription_id=str(preapproval_id)
    ).first()


def apply_preapproval(subscription, data, now=None):
    """Follow the subscription's state at Mercado Pago: authorization and cancellation."""
    now = now or timezone.now()
    if str(data.get("id")) != subscription.provider_subscription_id or data.get(
        "external_reference"
    ) != external_reference(subscription):
        logger.warning(
            "Mercado Pago preapproval %s does not match subscription %s",
            data.get("id"),
            subscription.pk,
        )
        return subscription
    status = data.get("status")
    if status == "authorized" and subscription.status == Subscription.PENDING_PAYMENT:
        # Paid access starts at the first charge; until then the owner keeps what they had.
        first_charge = (
            parse_date(data.get("next_payment_date"))
            or parse_date((data.get("auto_recurring") or {}).get("start_date"))
            or now
        )
        plan = subscription.selected_plan or subscription.plan
        return services.activate(
            subscription, plan, max(first_charge, now), "Suscripción autorizada en Mercado Pago"
        )
    if status == "cancelled" and subscription.renews_automatically:
        return services.schedule_cancel(subscription, "Suscripción cancelada en Mercado Pago", now)
    return subscription


def apply_payment(subscription, data, now=None):
    """A monthly charge: approved extends one month from its date, rejected flags the problem."""
    now = now or timezone.now()
    payment_status = (data.get("payment") or {}).get("status")
    if payment_status == "approved":
        if subscription.status not in (
            Subscription.ACTIVE,
            Subscription.PAST_DUE,
            Subscription.PENDING_PAYMENT,
        ):
            logger.warning(
                "Approved charge for subscription %s in state %s",
                subscription.pk,
                subscription.status,
            )
            return subscription
        charged_at = parse_date(data.get("debit_date")) or parse_date(data.get("date_created"))
        period_end = services.add_months(charged_at or now, 1)
        current = subscription.current_period_end
        if subscription.status == Subscription.ACTIVE and current and current >= period_end:
            return subscription  # already applied
        return services.transition(
            subscription,
            Subscription.ACTIVE,
            "Cobro mensual aprobado por Mercado Pago",
            plan=subscription.selected_plan or subscription.plan,
            selected_plan=None,
            current_period_end=period_end,
        )
    if payment_status in ("rejected", "cancelled") and (
        subscription.status == Subscription.ACTIVE and subscription.renews_automatically
    ):
        return services.mark_past_due(subscription, "Mercado Pago no pudo cobrar la cuota")
    return subscription


class MercadoPagoProvider(PaymentProvider):
    name = NAME
    collects_payer_email = True

    def __init__(self, client=None):
        self.client = client or MercadoPagoClient()

    def start_checkout(self, subscription, plan, payer_email=None):
        # Check everything on our side before creating anything at Mercado Pago.
        services.ensure_plan_fits(subscription, plan)
        if Subscription.PENDING_PAYMENT not in services.ALLOWED_TRANSITIONS[subscription.status]:
            raise services.InvalidTransition(f"No se puede pagar desde {subscription.status}")
        now = timezone.now()
        auto_recurring = {
            "frequency": 1,
            "frequency_type": "months",
            "transaction_amount": float(plan.monthly_price),
            "currency_id": plan.currency,
        }
        first_charge = services.first_charge_at(subscription, now)
        if first_charge > now + timedelta(minutes=5):
            auto_recurring["start_date"] = api_date(first_charge)
        previous = subscription.provider_subscription_id if subscription.provider == NAME else ""
        data = self.client.create_preapproval(
            {
                "reason": f"TurnoFacil {plan.name} - {subscription.business.name}"[:200],
                "external_reference": external_reference(subscription),
                "payer_email": payer_email,
                "auto_recurring": auto_recurring,
                "back_url": f"{settings.SITE_URL}{reverse('payment_return')}",
                "status": "pending",
            }
        )
        if not data.get("id") or not data.get("init_point"):
            raise PaymentError("Mercado Pago no devolvió el link de pago")
        subscription = services.choose_plan(subscription, plan)
        services.set_provider_reference(subscription, NAME, str(data["id"]))
        if previous and previous != str(data["id"]):
            self.discard(previous)
        return CheckoutResult(redirect_url=data["init_point"], message="")

    def discard(self, preapproval_id):
        """Best effort: an abandoned checkout should not stay usable at Mercado Pago."""
        try:
            data = self.client.get_preapproval(preapproval_id)
            if data.get("status") == "pending":
                self.client.update_preapproval(preapproval_id, {"status": "cancelled"})
        except PaymentError:
            logger.warning("Could not discard Mercado Pago preapproval %s", preapproval_id)

    def change_plan(self, subscription, plan):
        services.ensure_plan_fits(subscription, plan)
        self.client.update_preapproval(
            subscription.provider_subscription_id,
            {
                "reason": f"TurnoFacil {plan.name} - {subscription.business.name}"[:200],
                "auto_recurring": {
                    "transaction_amount": float(plan.monthly_price),
                    "currency_id": plan.currency,
                },
            },
        )
        return services.change_active_plan(subscription, plan)

    def cancel(self, subscription):
        self.client.update_preapproval(
            subscription.provider_subscription_id, {"status": "cancelled"}
        )
        return services.schedule_cancel(subscription, "Baja pedida por el dueño")

    def sync(self, subscription):
        if subscription.provider != NAME or not subscription.provider_subscription_id:
            return subscription
        data = self.client.get_preapproval(subscription.provider_subscription_id)
        return apply_preapproval(subscription, data)

    def process_notification(self, topic, resource_id):
        """Read the notified resource from the API and apply it. Unknown resources are ignored."""
        if not resource_id:
            return None
        try:
            if topic in PREAPPROVAL_TOPICS:
                data = self.client.get_preapproval(resource_id)
                subscription = find_subscription(data.get("id"))
                return apply_preapproval(subscription, data) if subscription else None
            if topic in PAYMENT_TOPICS:
                data = self.client.get_authorized_payment(resource_id)
                subscription = find_subscription(data.get("preapproval_id"))
                return apply_payment(subscription, data) if subscription else None
        except PaymentNotFound:
            # Not ours (or a simulated notification): acknowledge it so it is not retried.
            logger.info("Ignored Mercado Pago %s %s: not found", topic, resource_id)
        return None

    def reconcile(self, now=None):
        """Catch notifications that never arrived: pending checkouts and charges in trouble."""
        now = now or timezone.now()
        synced = 0
        candidates = Subscription.objects.filter(provider=NAME).exclude(provider_subscription_id="")
        recent_pending = candidates.filter(
            status=Subscription.PENDING_PAYMENT,
            updated_at__gte=now - timedelta(days=PENDING_SYNC_DAYS),
        )
        for subscription in list(recent_pending) + list(
            candidates.filter(status=Subscription.PAST_DUE)
        ):
            try:
                self.sync(subscription)
                synced += 1
            except PaymentError:
                logger.warning("Could not sync subscription %s with Mercado Pago", subscription.pk)
        return synced
