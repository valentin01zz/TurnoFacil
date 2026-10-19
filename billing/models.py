from django.db import models

from businesses.models import Business


class Plan(models.Model):
    code = models.SlugField(max_length=30, unique=True)
    name = models.CharField(max_length=60)
    monthly_price = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default="ARS")
    max_professionals = models.PositiveIntegerField()
    features = models.JSONField(default=list)
    is_public = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "monthly_price"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(max_professionals__gt=0), name="plan_max_professionals_positive"
            ),
            models.CheckConstraint(
                condition=models.Q(monthly_price__gte=0), name="plan_price_not_negative"
            ),
        ]

    def __str__(self):
        return self.name

    def has_feature(self, code):
        return code in self.features


class Subscription(models.Model):
    TRIALING = "trialing"
    TRIAL_EXPIRED = "trial_expired"
    PENDING_PAYMENT = "pending_payment"
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELED = "canceled"
    STATUSES = [
        (TRIALING, "Prueba activa"),
        (TRIAL_EXPIRED, "Prueba vencida"),
        (PENDING_PAYMENT, "Pago pendiente"),
        (ACTIVE, "Activa"),
        (PAST_DUE, "Pago con problemas"),
        (CANCELED, "Cancelada"),
    ]

    business = models.OneToOneField(Business, on_delete=models.CASCADE, related_name="subscription")
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name="subscriptions")
    selected_plan = models.ForeignKey(
        Plan, on_delete=models.PROTECT, related_name="+", null=True, blank=True
    )
    status = models.CharField(max_length=20, choices=STATUSES, default=TRIALING)
    trial_started_at = models.DateTimeField()
    trial_ends_at = models.DateTimeField()
    current_period_end = models.DateTimeField(null=True, blank=True)
    canceled_at = models.DateTimeField(null=True, blank=True)
    # Reference to the subscription at the payment provider. No card or payment data is stored here.
    provider = models.CharField(max_length=30, blank=True)
    provider_subscription_id = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(trial_ends_at__gt=models.F("trial_started_at")),
                name="subscription_trial_ends_after_start",
            ),
            models.UniqueConstraint(
                fields=["provider", "provider_subscription_id"],
                condition=~models.Q(provider_subscription_id=""),
                name="subscription_unique_provider_reference",
            ),
        ]

    def __str__(self):
        return f"{self.business} · {self.get_status_display()}"


class SubscriptionEvent(models.Model):
    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE, related_name="events")
    from_status = models.CharField(max_length=20, blank=True)
    to_status = models.CharField(max_length=20)
    reason = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "pk"]


class TrialNotice(models.Model):
    DAYS_7 = "days_7"
    DAYS_3 = "days_3"
    DAYS_1 = "days_1"
    ENDED = "ended"
    KINDS = [
        (DAYS_7, "7 días antes"),
        (DAYS_3, "3 días antes"),
        (DAYS_1, "1 día antes"),
        (ENDED, "Prueba finalizada"),
    ]

    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE, related_name="notices")
    kind = models.CharField(max_length=10, choices=KINDS)
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["subscription", "kind"], name="trial_notice_once_per_kind"
            )
        ]
