from django.db import migrations
from django.utils import timezone


def backfill_wish_assignments(apps, schema_editor):
    Wish = apps.get_model("core", "Wish")
    WishAssignment = apps.get_model("core", "WishAssignment")
    now = timezone.now()
    for wish in Wish.objects.filter(assigned_user__isnull=False):
        WishAssignment.objects.create(wish=wish, user=wish.assigned_user, assigned_at=now)


def reverse_backfill_wish_assignments(apps, schema_editor):
    WishAssignment = apps.get_model("core", "WishAssignment")
    WishAssignment.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0010_wishassignment'),
    ]

    operations = [
        migrations.RunPython(backfill_wish_assignments, reverse_backfill_wish_assignments),
    ]
