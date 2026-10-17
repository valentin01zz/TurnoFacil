from django.conf import settings
from django.db import models
from django.utils.text import slugify


class Business(models.Model):
    owner = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="business"
    )
    name = models.CharField(max_length=80)
    slug = models.SlugField(max_length=90, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = self._unique_slug()
        super().save(*args, **kwargs)

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
        ]

    def __str__(self):
        return f"{self.get_weekday_display()} {self.start_time:%H:%M}-{self.end_time:%H:%M}"
