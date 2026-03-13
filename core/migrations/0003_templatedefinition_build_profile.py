from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0002_templatebuildjob_templatedefinition_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="templatedefinition",
            name="build_profile",
            field=models.CharField(
                choices=[
                    ("ubuntu_autoinstall", "Ubuntu (autoinstall)"),
                    ("debian_preseed", "Debian (preseed)"),
                    ("windows_unattend", "Windows (generated unattend)"),
                ],
                default="ubuntu_autoinstall",
                max_length=32,
            ),
        ),
    ]
