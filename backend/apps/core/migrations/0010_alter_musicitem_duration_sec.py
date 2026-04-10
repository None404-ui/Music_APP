# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0009_alter_adunit_options_alter_collection_options_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="musicitem",
            name="duration_sec",
            field=models.PositiveIntegerField(
                blank=True,
                help_text="Заполняется автоматически при сохранении трека с файлом audio_file (mutagen).",
                null=True,
            ),
        ),
    ]
