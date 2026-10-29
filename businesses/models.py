from datetime import time, timedelta

from django.conf import settings
from django.db import IntegrityError, models, transaction
from django.utils import timezone
from django.utils.text import slugify

SLUG_ATTEMPTS = 5


class Business(models.Model):
    owner = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="business"
    )
    name = models.CharField("nombre del negocio", max_length=80)
    slug = models.SlugField(max_length=90, unique=True)
    address = models.CharField("dirección", max_length=200, blank=True)
    show_prices = models.BooleanField("mostrar precios a mis clientes", default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if self.slug:
            return super().save(*args, **kwargs)
        # Two sign-ups with the same name at once may pick the same free slug; the unique index
        # stops the second one, which then picks again.
        for attempt in range(SLUG_ATTEMPTS):
            self.slug = self._unique_slug()
            try:
                with transaction.atomic():
                    return super().save(*args, **kwargs)
            except IntegrityError:
                taken = Business.objects.filter(slug=self.slug).exists()
                self.slug = ""
                if not taken or attempt == SLUG_ATTEMPTS - 1:
                    raise

    def _unique_slug(self):
        base = slugify(self.name) or "negocio"
        slug = base
        suffix = 2
        while Business.objects.filter(slug=slug).exists():
            slug = f"{base}-{suffix}"
            suffix += 1
        return slug


class Service(models.Model):
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="services")
    name = models.CharField("nombre", max_length=80)
    duration_minutes = models.PositiveIntegerField("duración (minutos)")
    # Optional, in Argentine pesos. Each appointment keeps a copy (Appointment.price).
    price = models.DecimalField("precio", max_digits=10, decimal_places=2, null=True, blank=True)
    # "Desde": the price is the minimum and price_note says what sets the final amount.
    # db_default too: code still running during a deploy inserts rows without these columns.
    price_varies = models.BooleanField("el precio puede variar", default=False, db_default=False)
    price_note = models.CharField(
        "de qué depende el precio final", max_length=80, blank=True, default="", db_default=""
    )
    is_active = models.BooleanField("activo", default=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(duration_minutes__gt=0),
                name="service_duration_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(price__isnull=True) | models.Q(price__gt=0),
                name="service_price_positive",
            ),
        ]

    def __str__(self):
        return self.name


class Professional(models.Model):
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="professionals")
    name = models.CharField("nombre", max_length=80)
    is_active = models.BooleanField("activo", default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class WorkingHours(models.Model):
    WEEKDAYS = [
        (0, "Lunes"),
        (1, "Martes"),
        (2, "Miércoles"),
        (3, "Jueves"),
        (4, "Viernes"),
        (5, "Sábado"),
        (6, "Domingo"),
    ]

    professional = models.ForeignKey(
        Professional, on_delete=models.CASCADE, related_name="working_hours"
    )
    weekday = models.PositiveSmallIntegerField("día", choices=WEEKDAYS)
    start_time = models.TimeField("desde")
    end_time = models.TimeField("hasta")

    class Meta:
        ordering = ["weekday", "start_time"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(end_time__gt=models.F("start_time")),
                name="working_hours_end_after_start",
            ),
            # Overlaps are checked by the form (BaseWorkingHoursFormSet); exact copies never pass.
            models.UniqueConstraint(
                fields=["professional", "weekday", "start_time", "end_time"],
                name="working_hours_unique_range",
            ),
        ]

    def __str__(self):
        return f"{self.get_weekday_display()} {self.start_time:%H:%M}-{self.end_time:%H:%M}"


class DepositSettings(models.Model):
    """Bank transfer details a business shows customers to pay a deposit (seña) for a booking.

    Only instructions: TurnoFacil never checks or records the transfer, and the booking stays
    confirmed either way. No card data, tokens or bank credentials are stored here.
    """

    business = models.OneToOneField(Business, on_delete=models.CASCADE, related_name="deposit")
    enabled = models.BooleanField("pedir seña", default=False)
    # Fixed amount in Argentine pesos (services have no price to take a percentage of).
    amount = models.DecimalField("monto", max_digits=10, decimal_places=2, null=True, blank=True)
    holder_name = models.CharField("titular de la cuenta", max_length=100, blank=True)
    transfer_alias = models.CharField("alias", max_length=20, blank=True)
    cbu_cvu = models.CharField("CBU o CVU", max_length=22, blank=True)
    holder_tax_id = models.CharField("CUIT o CUIL", max_length=13, blank=True)
    instructions = models.CharField("indicaciones", max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            # Turned on, it always has an amount, a holder and somewhere to transfer to.
            models.CheckConstraint(
                condition=models.Q(enabled=False)
                | (
                    # NULL > 0 is not false in SQL, so the amount is required explicitly.
                    models.Q(amount__isnull=False)
                    & models.Q(amount__gt=0)
                    & ~models.Q(holder_name="")
                    & (~models.Q(transfer_alias="") | ~models.Q(cbu_cvu=""))
                ),
                name="deposit_complete_when_enabled",
            ),
            models.CheckConstraint(
                condition=models.Q(amount__isnull=True) | models.Q(amount__gt=0),
                name="deposit_amount_positive",
            ),
        ]

    def __str__(self):
        return f"Seña de {self.business}"


class TimeOff(models.Model):
    """A period nobody can book: the whole business (no professional) or one professional.

    Confirmed appointments inside it are left alone; the owner decides what to do with them.
    """

    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="time_off")
    professional = models.ForeignKey(
        Professional,
        on_delete=models.CASCADE,
        related_name="time_off",
        null=True,
        blank=True,
        verbose_name="profesional",
    )
    start_at = models.DateTimeField("desde")
    end_at = models.DateTimeField("hasta")
    # Only the owner sees it.
    reason = models.CharField("motivo", max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["start_at", "end_at"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(end_at__gt=models.F("start_at")),
                name="time_off_end_after_start",
            ),
        ]
        indexes = [models.Index(fields=["business", "end_at"])]

    @property
    def is_full_days(self):
        """Midnight to midnight: shown as days, without hours."""
        return (
            timezone.localtime(self.start_at).time()
            == time()
            == (timezone.localtime(self.end_at).time())
        )

    @property
    def first_day(self):
        return timezone.localdate(self.start_at)

    @property
    def last_day(self):
        """Last day touched (a full-day block ends at midnight of the next one)."""
        return timezone.localdate(self.end_at - timedelta(microseconds=1))

    def __str__(self):
        who = self.professional or "todo el negocio"
        start, end = timezone.localtime(self.start_at), timezone.localtime(self.end_at)
        return f"Bloqueo de {who}: {start:%Y-%m-%d %H:%M} a {end:%Y-%m-%d %H:%M}"
