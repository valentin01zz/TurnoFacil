from django.apps import AppConfig
from django.db.models.signals import post_save


class BillingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "billing"

    def ready(self):
        from businesses.models import Business

        from .services import start_trial

        def start_trial_for_new_business(sender, instance, created, raw=False, **kwargs):
            # A business owned by a verified account starts its single trial when it is created.
            # Owners who still have to confirm their email start it on verification instead.
            if created and not raw and instance.owner.is_email_verified:
                start_trial(instance)

        # weak=False: the receiver is a local function, so a weak reference would let it be
        # garbage collected as soon as ready() returns (it only survived when DEBUG kept it alive).
        post_save.connect(
            start_trial_for_new_business,
            sender=Business,
            weak=False,
            dispatch_uid="billing_start_trial",
        )
