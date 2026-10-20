from datetime import time
from unittest import mock

from django.apps import apps as django_apps
from django.contrib.auth import get_user_model
from django.db import IntegrityError, connection, transaction
from django.test import TestCase

from bookings.tests.helpers import create_business, create_professional
from businesses.models import Business, WorkingHours

User = get_user_model()
DELETE_DUPLICATES = __import__(
    "businesses.migrations.0005_delete_duplicate_working_hours",
    fromlist=["delete_exact_duplicates"],
).delete_exact_duplicates


def new_owner(email):
    return User.objects.create_user(email, "correct-horse-battery", verified=True)


class SlugCollisionTests(TestCase):
    def test_a_slug_taken_meanwhile_is_picked_again(self):
        create_business(name="Studio Norte")
        business = Business(owner=new_owner("b@example.com"), name="Studio Norte")
        real = Business._unique_slug

        # The first pick happens "before" the other sign-up saved: it returns the taken slug.
        with mock.patch.object(
            Business, "_unique_slug", autospec=True, side_effect=["studio-norte", real(business)]
        ):
            business.save()

        self.assertEqual(Business.objects.get(pk=business.pk).slug, "studio-norte-2")

    def test_other_integrity_errors_are_not_hidden(self):
        owner = create_business(name="Studio Norte").owner

        with self.assertRaises(IntegrityError), transaction.atomic():
            Business.objects.create(owner=owner, name="Otro nombre")

    def test_it_gives_up_after_a_few_tries(self):
        create_business(name="Studio Norte")
        business = Business(owner=new_owner("b@example.com"), name="Studio Norte")

        with mock.patch.object(Business, "_unique_slug", return_value="studio-norte"):
            with self.assertRaises(IntegrityError):
                business.save()

    def test_an_existing_slug_is_kept(self):
        business = create_business(name="Studio Norte")
        business.name = "Studio Sur"

        business.save()

        self.assertEqual(Business.objects.get(pk=business.pk).slug, "studio-norte")


class WorkingHoursIntegrityTests(TestCase):
    def test_the_database_rejects_an_exact_copy(self):
        professional = create_professional(create_business(), ranges=((time(9), time(13)),))

        with self.assertRaises(IntegrityError), transaction.atomic():
            WorkingHours.objects.create(
                professional=professional, weekday=0, start_time=time(9), end_time=time(13)
            )

    def test_the_migration_removes_existing_copies_and_keeps_the_rest(self):
        professional = create_professional(create_business(), ranges=((time(9), time(13)),))
        with connection.cursor() as cursor:
            # As it was before the constraint (the test's transaction puts it back afterwards).
            cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")
            cursor.execute(
                "ALTER TABLE businesses_workinghours DROP CONSTRAINT working_hours_unique_range"
            )
        original = professional.working_hours.get(weekday=0)
        WorkingHours.objects.create(
            professional=professional, weekday=0, start_time=time(9), end_time=time(13)
        )

        DELETE_DUPLICATES(django_apps, None)

        self.assertEqual(list(professional.working_hours.filter(weekday=0)), [original])
        self.assertEqual(professional.working_hours.count(), 7)

    def test_other_professionals_and_days_may_share_hours(self):
        business = create_business()
        ana = create_professional(business, name="Ana", ranges=((time(9), time(13)),))

        create_professional(business, name="Bruno", ranges=((time(9), time(13)),))

        self.assertEqual(ana.working_hours.filter(start_time=time(9)).count(), 7)
