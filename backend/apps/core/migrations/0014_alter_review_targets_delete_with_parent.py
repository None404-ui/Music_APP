from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0013_alter_musicitem_audio_file"),
    ]

    operations = [
        migrations.AlterField(
            model_name="review",
            name="collection",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.deletion.CASCADE,
                related_name="reviews",
                to="core.collection",
            ),
        ),
        migrations.AlterField(
            model_name="review",
            name="music_item",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.deletion.CASCADE,
                related_name="reviews",
                to="core.musicitem",
            ),
        ),
    ]
