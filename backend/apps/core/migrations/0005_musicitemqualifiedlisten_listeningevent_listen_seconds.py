# Generated manually for qualified listens + session seconds

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("core", "0004_reviewfavorite_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="listeningevent",
            name="listen_seconds",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.CreateModel(
            name="MusicItemQualifiedListen",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "music_item",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="qualified_listens",
                        to="core.musicitem",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="qualified_music_listens",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name="musicitemqualifiedlisten",
            constraint=models.UniqueConstraint(
                fields=("user", "music_item"),
                name="uniq_qualified_listen_user_music_item",
            ),
        ),
        migrations.AddIndex(
            model_name="musicitemqualifiedlisten",
            index=models.Index(
                fields=["music_item"], name="idx_qualifiedlisten_music_item"
            ),
        ),
    ]
