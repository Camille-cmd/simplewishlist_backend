from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0009_add_suggested_by_field'),
    ]

    operations = [
        migrations.CreateModel(
            name='WishAssignment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('assigned_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='wish_assignments', to='core.wishlistuser')),
                ('wish', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='assignments', to='core.wish')),
            ],
            options={
                'constraints': [
                    models.UniqueConstraint(fields=['wish', 'user'], name='uniq_wish_assignment'),
                ],
            },
        ),
        migrations.AddField(
            model_name='wish',
            name='assigned_users',
            field=models.ManyToManyField(blank=True, related_name='assigned_wishes', through='core.WishAssignment', to='core.wishlistuser'),
        ),
    ]
