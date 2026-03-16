from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0003_templatedefinition_build_profile"),
    ]

    operations = [
        migrations.AddField(
            model_name="templatebuildjob",
            name="last_heartbeat_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
