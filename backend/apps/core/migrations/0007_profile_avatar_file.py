from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0006_musicitem_audio_artwork_files"),
    ]

    operations = [
        migrations.AddField(
            model_name="profile",
            name="avatar_file",
            field=models.FileField(blank=True, upload_to="avatars/"),
        ),
    ]
