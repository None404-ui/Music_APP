from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0010_alter_musicitem_duration_sec"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="musicitem",
            name="playback_ref",
        ),
    ]
