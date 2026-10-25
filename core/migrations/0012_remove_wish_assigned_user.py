from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0011_backfill_wish_assignments'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='wish',
            name='assigned_user',
        ),
    ]
