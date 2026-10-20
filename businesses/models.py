from django.conf import settings
from django.db import IntegrityError, models, transaction
from django.utils.text import slugify

SLUG_ATTEMPTS = 5


class Business(models.Model):
    owner = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="business"
    )
    name = models.CharField("nombre del negocio", max_length=80)
    slug = models.SlugField(max_length=90, unique=True)
    address = models.CharField("dirección", max_length=200, blank=True)
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
    is_active = models.BooleanField("activo", default=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(duration_minutes__gt=0),
                name="service_duration_positive",
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
