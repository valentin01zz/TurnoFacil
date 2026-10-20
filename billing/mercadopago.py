"""Mercado Pago subscriptions (ADR-0005), over its REST API with the standard library.

Rules that keep this safe:
- The owner pays on Mercado Pago's own checkout; card data never reaches TurnoFacil.
- A notification is only a hint: its signature is checked, and then the real state is always read
  back from the API with our own credentials before anything changes.
- Applying the same state twice changes nothing, so retried or repeated notifications are harmless:
  each charge is recorded once applied (ProviderPayment) and the paid period never moves back.
- A checkout is saved before Mercado Pago is called (CheckoutAttempt) and retried with the same
  idempotency key, so double clicks, concurrent requests and timeouts never create two checkouts.
"""

import hashlib
import hmac
import json
import logging
import time
import uuid
from datetime import timedelta
from datetime import timezone as dt_timezone
from urllib import error as urlerror
from urllib import request as urlrequest
from urllib.parse import quote

from django.conf import settings
from django.db import transaction
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from . import services
from .models import CheckoutAttempt, ProviderPayment, Subscription
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


def valid_signature(secret, signature_header, request_id, data_id, max_age=0, now=None):
    """Check Mercado Pago's `x-signature` header (HMAC-SHA256 of the documented manifest).

    With `max_age` (seconds), a signature whose timestamp is further than that from `now` is
    rejected too, so a captured notification cannot be replayed later.
    """
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
    if not hmac.compare_digest(expected, received):
        return False
    return not max_age or is_recent(ts, max_age, now)


def is_recent(ts, max_age, now=None):
    try:
        sent = int(ts)
    except ValueError:
        return False
    if sent > 10**11:  # milliseconds
        sent //= 1000
    now = time.time() if now is None else now
    return abs(now - sent) <= max_age


class MercadoPagoClient:
    def __init__(self, access_token=None, base_url=None, timeout=10):
        self.access_token = access_token or settings.MERCADOPAGO_ACCESS_TOKEN
        self.base_url = (base_url or settings.MERCADOPAGO_API_URL).rstrip("/")
        self.timeout = timeout

    def request(self, method, path, body=None, idempotency_key=None):
        if not self.access_token:
            raise PaymentError("Falta configurar MERCADOPAGO_ACCESS_TOKEN")
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
        if method == "POST":
            headers["X-Idempotency-Key"] = idempotency_key or str(uuid.uuid4())
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

    def create_preapproval(self, body, idempotency_key=None):
        return self.request("POST", "/preapproval", body, idempotency_key=idempotency_key)

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
    payment_id = str(data.get("id") or "")
    if payment_id and already_applied(payment_id):
        # Repeated or late notification (even with another status): its effect is already in.
        logger.info("Mercado Pago charge %s was already applied", payment_id)
        return subscription
    if payment_status == "approved":
        return apply_approved_payment(subscription, data, payment_id, now)
    if payment_status in ("rejected", "cancelled") and (
        subscription.status == Subscription.ACTIVE and subscription.renews_automatically
    ):
        return services.mark_past_due(subscription, "Mercado Pago no pudo cobrar la cuota")
    return subscription


def already_applied(payment_id):
    return ProviderPayment.objects.filter(provider=NAME, external_payment_id=payment_id).exists()


def apply_approved_payment(subscription, data, payment_id, now):
    """Extend one month from the charge date, once per charge, without moving the period back."""
    charged_at = parse_date(data.get("debit_date")) or parse_date(data.get("date_created")) or now
    period_end = services.add_months(charged_at, 1)
    with transaction.atomic():
        # Notifications for the same subscription are applied one at a time.
        locked = Subscription.objects.select_for_update().get(pk=subscription.pk)
        if payment_id and already_applied(payment_id):
            logger.info("Mercado Pago charge %s was already applied", payment_id)
            return refreshed(subscription)
        if locked.status not in (
            Subscription.ACTIVE,
            Subscription.PAST_DUE,
            Subscription.PENDING_PAYMENT,
        ):
            logger.warning(
                "Approved charge for subscription %s in state %s", locked.pk, locked.status
            )
            return refreshed(subscription)
        if payment_id:
            ProviderPayment.objects.create(
                subscription=locked,
                provider=NAME,
                external_payment_id=payment_id,
                charged_at=charged_at,
                period_end=period_end,
            )
        current = locked.current_period_end
        if current and current >= period_end:
            if locked.status == Subscription.ACTIVE:
                return refreshed(subscription)  # an older charge: the paid period stays
            period_end = current
        services.transition(
            locked,
            Subscription.ACTIVE,
            "Cobro mensual aprobado por Mercado Pago",
            plan=locked.selected_plan or locked.plan,
            selected_plan=None,
            current_period_end=period_end,
        )
    return refreshed(subscription)


def refreshed(subscription):
    subscription.refresh_from_db()
    return subscription


def open_checkout_attempt(subscription, plan, payer_email, now=None):
    """The attempt to use for this checkout, committed before Mercado Pago is called.

    A recent open attempt for the same plan and email is reused (with its idempotency key);
    otherwise it is closed and a new one starts.
    """
    now = now or timezone.now()
    with transaction.atomic():
        locked = Subscription.objects.select_for_update().get(pk=subscription.pk)
        current = CheckoutAttempt.objects.filter(
            subscription=locked, status=CheckoutAttempt.OPEN
        ).first()
        if current and reusable_attempt(current, locked, plan, payer_email, now):
            return current
        if current:
            current.status = CheckoutAttempt.CLOSED
            current.save(update_fields=["status"])
        return CheckoutAttempt.objects.create(
            subscription=locked,
            plan=plan,
            payer_email=payer_email,
            idempotency_key=uuid.uuid4().hex,
        )


def reusable_attempt(attempt, subscription, plan, payer_email, now):
    if attempt.plan_id != plan.pk or attempt.payer_email.lower() != payer_email.lower():
        return False
    if attempt.created_at < now - timedelta(minutes=settings.CHECKOUT_REUSE_MINUTES):
        return False
    if not attempt.provider_reference:
        return True  # Mercado Pago never answered: retry with the same key
    # Answered: its link is still the subscription's pending checkout.
    return (
        subscription.status == Subscription.PENDING_PAYMENT
        and subscription.provider == NAME
        and subscription.provider_subscription_id == attempt.provider_reference
    )


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
        attempt = open_checkout_attempt(subscription, plan, payer_email or "")
        with transaction.atomic():
            # One checkout at a time per subscription: a concurrent request waits here and then
            # finds this attempt already answered. The lock is held while Mercado Pago answers.
            locked = Subscription.objects.select_for_update().get(pk=subscription.pk)
            attempt = CheckoutAttempt.objects.get(pk=attempt.pk)
            if attempt.status != CheckoutAttempt.OPEN:
                raise PaymentError("Otro pago reemplazó a este intento")
            if attempt.provider_reference:
                return CheckoutResult(redirect_url=attempt.redirect_url, message="")
            previous = locked.provider_subscription_id if locked.provider == NAME else ""
            data = self.client.create_preapproval(
                self.preapproval_body(locked, plan, payer_email),
                idempotency_key=attempt.idempotency_key,
            )
            if not data.get("id") or not data.get("init_point"):
                raise PaymentError("Mercado Pago no devolvió el link de pago")
            reference = str(data["id"])
            attempt.provider_reference = reference
            attempt.redirect_url = data["init_point"]
            attempt.save(update_fields=["provider_reference", "redirect_url"])
            locked = services.choose_plan(locked, plan)
            services.set_provider_reference(locked, NAME, reference)
        if previous and previous != reference:
            self.discard(previous)
        return CheckoutResult(redirect_url=attempt.redirect_url, message="")

    def preapproval_body(self, subscription, plan, payer_email):
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
        return {
            "reason": f"TurnoFacil {plan.name} - {subscription.business.name}"[:200],
            "external_reference": external_reference(subscription),
            "payer_email": payer_email,
            "auto_recurring": auto_recurring,
            "back_url": f"{settings.SITE_URL}{reverse('payment_return')}",
            "status": "pending",
        }

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
