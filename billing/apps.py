from django.apps import AppConfig
from django.db.models.signals import post_save


class BillingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "billing"

    def ready(self):
        from businesses.models import Business

        from .services import start_trial

        def start_trial_for_new_business(sender, instance, created, raw=False, **kwargs):
            # Every business starts its single trial the moment it exists, however it was created.
            if created and not raw:
                start_trial(instance)

        post_save.connect(
            start_trial_for_new_business, sender=Business, dispatch_uid="billing_start_trial"
        )
