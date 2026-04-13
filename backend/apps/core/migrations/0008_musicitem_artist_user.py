from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("core", "0007_profile_avatar_file"),
    ]

    operations = [
        migrations.AddField(
            model_name="musicitem",
            name="artist_user",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="music_as_artist",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddIndex(
            model_name="musicitem",
            index=models.Index(
                fields=["artist_user"], name="idx_musicitem_artist_user"
            ),
        ),
    ]
