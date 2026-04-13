"""
Заполнить duration_sec у уже загруженных треков по audio_file (mutagen).

  python manage.py backfill_music_duration
"""

from django.core.management.base import BaseCommand

from apps.core.audio_duration import duration_from_filefield
from apps.core.models import MusicItem


class Command(BaseCommand):
    help = "Пересчитать duration_sec для треков с локальным audio_file"

    def handle(self, *args, **options):
        qs = MusicItem.objects.filter(kind=MusicItem.Kind.TRACK.value).exclude(
            audio_file=""
        )
        updated = 0
        for mi in qs.iterator():
            sec = duration_from_filefield(mi.audio_file)
            if sec is None or sec <= 0:
                continue
            if mi.duration_sec != sec:
                MusicItem.objects.filter(pk=mi.pk).update(duration_sec=sec)
                updated += 1
        self.stdout.write(self.style.SUCCESS(f"Обновлено записей: {updated}"))
