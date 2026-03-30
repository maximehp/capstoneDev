from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0004_templatebuildjob_last_heartbeat_at"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="DirectoryProfile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("ad_object_sid", models.CharField(max_length=128, unique=True)),
                ("ad_rid", models.PositiveIntegerField(unique=True)),
                ("display_name", models.CharField(blank=True, max_length=255)),
                ("distinguished_name", models.CharField(blank=True, max_length=512)),
                ("user_principal_name", models.CharField(blank=True, max_length=255)),
                ("department", models.CharField(blank=True, max_length=255)),
                ("company", models.CharField(blank=True, max_length=255)),
                (
                    "directory_role",
                    models.CharField(
                        choices=[("unknown", "Unknown"), ("student", "Student"), ("faculty", "Faculty")],
                        default="unknown",
                        max_length=16,
                    ),
                ),
                ("raw_attributes", models.JSONField(default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="directory_profile",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "indexes": [models.Index(fields=["directory_role", "updated_at"], name="core_directo_directo_17eb7f_idx")],
            },
        ),
    ]
