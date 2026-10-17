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
