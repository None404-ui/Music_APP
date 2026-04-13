"""
Core domain models for the CRATES backend.

This app stores:
- user profile & player customization (`Profile`)
- external music catalog cache (`MusicItem`)
- user collections/playlists (`Collection`, `CollectionItem`)
- reviews + comments (`Review`, `Comment`)
- social reactions like/dislike (`Reaction`)
- favorites + social graph (`Favorite`, `Follow`)
- notifications + complaint/report flow (`Notification`, `Report`)
- listening diary + ad unit config (`ListeningEvent`, `AdUnit`)
"""

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import models
from django.db.models import Q


class Profile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile"
    )

    nickname = models.CharField(max_length=64, unique=True)
    avatar_url = models.URLField(blank=True)
    avatar_file = models.FileField(upload_to="avatars/", blank=True)
    bio = models.TextField(blank=True)

    is_premium = models.BooleanField(default=False)
    premium_until = models.DateTimeField(null=True, blank=True)

    favorite_genres = models.TextField(blank=True)  # simple CSV/JSON string
    ui_theme_color = models.CharField(max_length=32, blank=True)
    ui_background = models.CharField(max_length=128, blank=True)
    ui_progress_color = models.CharField(max_length=32, blank=True)
    player_preset = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Профиль"
        verbose_name_plural = "Профили"

    def __str__(self) -> str:
        return self.nickname


class MusicItem(models.Model):
    class Kind(models.TextChoices):
        TRACK = "track", "Трек"
        ALBUM = "album", "Альбом"
        PLAYLIST = "playlist", "Плейлист"

    provider = models.CharField(max_length=32)
    external_id = models.CharField(max_length=128)
    kind = models.CharField(max_length=16, choices=Kind.choices)

    title = models.CharField(max_length=256)
    artist = models.CharField(max_length=256, blank=True)
    artwork_url = models.URLField(blank=True)
    # Локальная обложка (админка): в API подставляется в artwork_url как URL к /media/...
    artwork_file = models.FileField(upload_to="music/covers/", blank=True)
    duration_sec = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Заполняется автоматически при сохранении трека с файлом audio_file (mutagen).",
    )

    playback_ref = models.CharField(
        max_length=512,
        blank=True,
        help_text=(
            "Ссылка на воспроизведение (рекомендуется): полный URL https://… "
            "(YouTube, стриминг, прямой MP3/AAC). Имеет приоритет над файлом на сервере."
        ),
    )
    audio_file = models.FileField(
        upload_to="music/tracks/",
        blank=True,
        help_text=(
            "Локальная загрузка на сервер — используется в API только если в «Ссылке на воспроизведение» "
            "нет HTTP(S)-URL."
        ),
    )
    meta_json = models.TextField(blank=True)

    artist_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="music_as_artist",
    )

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Запись каталога"
        verbose_name_plural = "Каталог музыки"
        constraints = [
            models.UniqueConstraint(
                fields=["provider", "external_id", "kind"],
                name="uniq_music_item_provider_external_kind",
            )
        ]
        indexes = [
            models.Index(fields=["title"], name="idx_musicitem_title"),
            models.Index(fields=["artist"], name="idx_musicitem_artist"),
            models.Index(fields=["artist_user"], name="idx_musicitem_artist_user"),
        ]

    def save(self, *args, **kwargs):
        uid = getattr(self, "artist_user_id", None)
        if uid:
            prof = Profile.objects.filter(user_id=uid).first()
            if prof:
                self.artist = prof.nickname
            else:
                u = get_user_model().objects.filter(pk=uid).first()
                self.artist = (u.get_username() if u else "") or ""
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        if self.artist:
            return f"{self.artist} — {self.title}"
        return self.title

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.kind != self.Kind.TRACK.value:
            return
        from .audio_duration import duration_from_filefield

        sec = duration_from_filefield(self.audio_file)
        if sec is None or sec <= 0:
            return
        if self.duration_sec != sec:
            type(self).objects.filter(pk=self.pk).update(duration_sec=sec)
            self.duration_sec = sec


class Collection(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="collections"
    )
    title = models.CharField(max_length=128)
    description = models.TextField(blank=True)
    is_public = models.BooleanField(default=True)
    cover_url = models.URLField(blank=True)

    deleted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Подборка"
        verbose_name_plural = "Подборки"

    def __str__(self) -> str:
        return self.title


class CollectionItem(models.Model):
    collection = models.ForeignKey(
        Collection, on_delete=models.CASCADE, related_name="items"
    )
    music_item = models.ForeignKey(
        MusicItem, on_delete=models.CASCADE, related_name="in_collections"
    )
    position = models.PositiveIntegerField(null=True, blank=True)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Элемент подборки"
        verbose_name_plural = "Элементы подборок"
        constraints = [
            models.UniqueConstraint(
                fields=["collection", "music_item"],
                name="uniq_collection_music_item",
            )
        ]
        indexes = [
            models.Index(
                fields=["collection", "position"], name="idx_collectionitem_position"
            )
        ]


class Review(models.Model):
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reviews"
    )
    music_item = models.ForeignKey(
        MusicItem, null=True, blank=True, on_delete=models.SET_NULL, related_name="reviews"
    )
    collection = models.ForeignKey(
        Collection, null=True, blank=True, on_delete=models.SET_NULL, related_name="reviews"
    )

    text = models.TextField()
    spoiler = models.BooleanField(default=False)

    deleted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Рецензия"
        verbose_name_plural = "Рецензии"
        constraints = [
            models.CheckConstraint(
                check=(
                    (Q(music_item__isnull=False) & Q(collection__isnull=True))
                    | (Q(music_item__isnull=True) & Q(collection__isnull=False))
                ),
                name="chk_review_exactly_one_target",
            )
        ]
        indexes = [
            models.Index(fields=["created_at"], name="idx_review_created"),
            models.Index(fields=["author", "created_at"], name="idx_review_author_created"),
        ]


class Comment(models.Model):
    review = models.ForeignKey(Review, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="comments"
    )
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.CASCADE, related_name="replies"
    )
    text = models.TextField()

    deleted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Комментарий"
        verbose_name_plural = "Комментарии"
        indexes = [
            models.Index(fields=["review", "created_at"], name="idx_comment_review_created"),
        ]


class Reaction(models.Model):
    class TargetType(models.TextChoices):
        REVIEW = "review", "Рецензия"
        COMMENT = "comment", "Комментарий"
        MUSIC_ITEM = "music_item", "Трек каталога"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reactions"
    )
    target_type = models.CharField(max_length=16, choices=TargetType.choices)
    target_id = models.PositiveBigIntegerField()
    value = models.SmallIntegerField()

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Реакция"
        verbose_name_plural = "Реакции"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "target_type", "target_id"],
                name="uniq_user_reaction_target",
            ),
            models.CheckConstraint(
                check=Q(value__in=[-1, 1]),
                name="chk_reaction_value_pm1",
            ),
        ]
        indexes = [
            models.Index(fields=["target_type", "target_id"], name="idx_reaction_target"),
            models.Index(fields=["user"], name="idx_reaction_user"),
        ]


class Favorite(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="favorites"
    )
    music_item = models.ForeignKey(
        MusicItem, on_delete=models.CASCADE, related_name="favorites"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Избранный трек"
        verbose_name_plural = "Избранное (треки)"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "music_item"],
                name="uniq_user_favorite_music_item",
            )
        ]


class ReviewFavorite(models.Model):
    """
    Избранное для рецензий (Review).
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="review_favorites",
    )
    review = models.ForeignKey(
        Review,
        on_delete=models.CASCADE,
        related_name="favorites",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Избранная рецензия"
        verbose_name_plural = "Избранное (рецензии)"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "review"],
                name="uniq_user_favorite_review",
            )
        ]


class ListeningEvent(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="listening_events"
    )
    music_item = models.ForeignKey(
        MusicItem, on_delete=models.CASCADE, related_name="listening_events"
    )
    started_at = models.DateTimeField()
    ended_at = models.DateTimeField(null=True, blank=True)
    source = models.CharField(max_length=64, blank=True)
    # Секунды за эту сессию (для суммарного «наслушано» по треку/альбому).
    listen_seconds = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "Событие прослушивания"
        verbose_name_plural = "Дневник прослушиваний"
        indexes = [
            models.Index(fields=["user", "started_at"], name="idx_listening_user_started"),
        ]


class MusicItemQualifiedListen(models.Model):
    """
    Пользователь засчитан как «слушатель» трека/альбома после порога (30 с или половина длины).
    Одна строка на пару (user, music_item) — для счётчика «сколько людей слушали».
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="qualified_music_listens",
    )
    music_item = models.ForeignKey(
        MusicItem, on_delete=models.CASCADE, related_name="qualified_listens"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Квалифицированное прослушивание"
        verbose_name_plural = "Квалифицированные прослушивания"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "music_item"],
                name="uniq_qualified_listen_user_music_item",
            )
        ]
        indexes = [
            models.Index(fields=["music_item"], name="idx_qualifiedlisten_music_item"),
        ]


class Report(models.Model):
    class TargetType(models.TextChoices):
        REVIEW = "review", "Рецензия"
        COMMENT = "comment", "Комментарий"
        USER = "user", "Пользователь"
        COLLECTION = "collection", "Подборка"

    class Status(models.TextChoices):
        OPEN = "open", "Открыта"
        REVIEWING = "reviewing", "На рассмотрении"
        RESOLVED = "resolved", "Решена"
        REJECTED = "rejected", "Отклонена"

    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reports"
    )
    target_type = models.CharField(max_length=16, choices=TargetType.choices)
    target_id = models.PositiveBigIntegerField()
    reason = models.TextField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.OPEN)

    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Жалоба"
        verbose_name_plural = "Жалобы"
        indexes = [
            models.Index(fields=["status", "created_at"], name="idx_report_status_created"),
        ]


class AdUnit(models.Model):
    placement = models.CharField(max_length=64)
    is_active = models.BooleanField(default=True)
    config_json = models.TextField()

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Рекламный блок"
        verbose_name_plural = "Реклама"
        indexes = [
            models.Index(fields=["placement", "is_active"], name="idx_adunit_place_active"),
        ]


class Conversation(models.Model):
    """
    Диалог (может быть групповой, состав участников хранится в ConversationMember).
    """

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Диалог"
        verbose_name_plural = "Диалоги"


class ConversationMember(models.Model):
    """
    Участники диалога.
    """

    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name="members"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="conversation_memberships",
    )

    class Meta:
        verbose_name = "Участник диалога"
        verbose_name_plural = "Участники диалогов"
        constraints = [
            models.UniqueConstraint(
                fields=["conversation", "user"],
                name="uniq_conversation_member",
            )
        ]


class Message(models.Model):
    """
    Сообщение внутри диалога.
    """

    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name="messages"
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="messages"
    )
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Сообщение"
        verbose_name_plural = "Сообщения"
        indexes = [
            models.Index(fields=["conversation", "created_at"], name="idx_msg_conv_created"),
        ]


class Follow(models.Model):
    follower = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="following"
    )
    followee = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="followers"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Подписка"
        verbose_name_plural = "Подписки"
        constraints = [
            models.UniqueConstraint(
                fields=["follower", "followee"], name="uniq_follow_follower_followee"
            ),
            models.CheckConstraint(
                check=~Q(follower=models.F("followee")),
                name="chk_follow_not_self",
            ),
        ]
        indexes = [
            models.Index(fields=["followee", "created_at"], name="idx_follow_followee_created"),
        ]


class Notification(models.Model):
    class Type(models.TextChoices):
        REACTION = "reaction", "Реакция"
        COMMENT = "comment", "Комментарий"
        FOLLOW = "follow", "Подписка"
        SYSTEM = "system", "Системное"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications"
    )
    type = models.CharField(max_length=16, choices=Type.choices)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="notifications_sent",
    )
    entity_type = models.CharField(max_length=32, blank=True)
    entity_id = models.PositiveBigIntegerField(null=True, blank=True)

    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Уведомление"
        verbose_name_plural = "Уведомления"
        indexes = [
            models.Index(fields=["user", "is_read", "created_at"], name="idx_notif_user_read"),
        ]

