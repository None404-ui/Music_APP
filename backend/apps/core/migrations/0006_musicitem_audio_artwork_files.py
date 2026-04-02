# Uploaded audio + cover for MusicItem (API exposes URLs under /media/).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0005_musicitemqualifiedlisten_listeningevent_listen_seconds"),
    ]

    operations = [
        migrations.AddField(
            model_name="musicitem",
            name="artwork_file",
            field=models.FileField(blank=True, upload_to="music/covers/"),
        ),
        migrations.AddField(
            model_name="musicitem",
            name="audio_file",
            field=models.FileField(blank=True, upload_to="music/tracks/"),
        ),
        migrations.AlterField(
            model_name="musicitem",
            name="playback_ref",
            field=models.CharField(
                blank=True,
                help_text="URL или путь на машине сервера (клиенту не подойдёт). Лучше загрузить «Аудиофайл».",
                max_length=512,
            ),
        ),
    ]
