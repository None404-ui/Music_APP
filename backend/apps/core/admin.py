"""
Django admin: регистрация моделей CRATES на кастомном AdminSite (русский UI, порядок разделов).
"""

import uuid

from django import forms
from django.contrib import admin
from django.contrib.auth.admin import GroupAdmin, UserAdmin
from django.contrib.auth.models import Group, User

from crates.admin_site import crates_admin_site

from .models import (
    AdUnit,
    Collection,
    CollectionItem,
    Comment,
    Conversation,
    ConversationMember,
    Favorite,
    Follow,
    ListeningEvent,
    Message,
    MusicItem,
    MusicItemQualifiedListen,
    Notification,
    Profile,
    Reaction,
    Report,
    Review,
    ReviewFavorite,
)


class MusicItemAdminForm(forms.ModelForm):
    """Упрощение: provider / external_id можно не заполнять (будут upload + uuid)."""

    provider = forms.CharField(
        max_length=32,
        required=False,
        help_text="Оставьте пустым для значения «upload».",
    )
    external_id = forms.CharField(
        max_length=128,
        required=False,
        help_text="Оставьте пустым — сгенерируется уникальный id.",
    )

    class Meta:
        model = MusicItem
        fields = "__all__"

    def clean(self):
        cleaned = super().clean()
        if not (cleaned.get("provider") or "").strip():
            cleaned["provider"] = "upload"
        if not (cleaned.get("external_id") or "").strip():
            cleaned["external_id"] = str(uuid.uuid4())
        return cleaned


class AdUnitAdminForm(forms.ModelForm):
    placement = forms.ChoiceField(
        choices=(
            ("app_top_banner", "Верхний баннер приложения"),
            ("feed_banner", "Баннер ленты"),
        ),
        help_text=(
            "Для баннера сверху во всём приложении выберите "
            "«Верхний баннер приложения». Техническое значение: app_top_banner."
        ),
    )

    class Meta:
        model = AdUnit
        fields = "__all__"


@admin.register(Profile, site=crates_admin_site)
class ProfileAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "nickname",
        "user_role",
        "is_premium",
        "premium_until",
        "updated_at",
    )
    search_fields = ("nickname", "user__username", "user__email")
    list_filter = ("is_premium", "user__is_staff", "user__is_superuser")
    fieldsets = (
        ("Пользователь", {"fields": ("user",)}),
        ("Профиль", {"fields": ("nickname", "avatar_url", "avatar_file", "bio")}),
        (
            "Подписка",
            {"fields": ("is_premium", "premium_until")},
        ),
        (
            "Интерфейс и плеер",
            {
                "fields": (
                    "favorite_genres",
                    "ui_theme_color",
                    "ui_background",
                    "ui_progress_color",
                    "player_preset",
                ),
            },
        ),
        (
            "Служебное",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )
    readonly_fields = ("created_at", "updated_at")

    @admin.display(description="Роль")
    def user_role(self, obj) -> str:
        user = obj.user
        if user.is_superuser:
            return "superuser"
        if user.is_staff:
            return "admin/staff"
        if obj.is_premium:
            return "premium"
        return "user"


@admin.register(MusicItem, site=crates_admin_site)
class MusicItemAdmin(admin.ModelAdmin):
    form = MusicItemAdminForm
    list_display = ("id", "provider", "kind", "artist", "title", "updated_at")
    search_fields = ("title", "artist", "external_id")
    list_filter = ("provider", "kind")
    autocomplete_fields = ("artist_user",)

    class Media:
        js = ("admin/js/musicitem_kind_fieldsets.js",)

    readonly_fields = ("artist", "duration_sec")

    fieldsets = (
        (
            "Основное",
            {
                "fields": (
                    "provider",
                    "external_id",
                    "kind",
                    "title",
                    "artist_user",
                    "artist",
                )
            },
        ),
        (
            "Аудиофайл на сервере",
            {
                "fields": ("audio_file", "duration_sec"),
                "classes": ("wide", "musicitem-fs-track"),
                "description": (
                    "Трек загружается на сервер и воспроизводится приложением напрямую из backend. "
                    "Длительность заполняется автоматически при сохранении файла."
                ),
            },
        ),
        (
            "Обложка (любой вид)",
            {
                "fields": ("artwork_file", "artwork_url"),
                "description": "Файл обложки предпочтительнее ссылки; для карусели «Популярное».",
            },
        ),
        (
            "Дополнительно",
            {"fields": ("meta_json",), "classes": ("collapse",)},
        ),
    )


@admin.register(Collection, site=crates_admin_site)
class CollectionAdmin(admin.ModelAdmin):
    list_display = ("id", "owner", "title", "is_public", "created_at", "deleted_at")
    search_fields = ("title", "owner__username")
    list_filter = ("is_public",)
    fieldsets = (
        ("Основное", {"fields": ("owner", "title", "description", "is_public", "cover_url")}),
        ("Служебное", {"fields": ("deleted_at", "created_at", "updated_at")}),
    )
    readonly_fields = ("created_at", "updated_at")


@admin.register(CollectionItem, site=crates_admin_site)
class CollectionItemAdmin(admin.ModelAdmin):
    list_display = ("id", "collection", "music_item", "position", "added_at")
    search_fields = ("collection__title", "music_item__title", "music_item__artist")


@admin.register(Review, site=crates_admin_site)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("id", "author", "music_item", "collection", "created_at", "deleted_at")
    search_fields = ("author__username", "text")
    list_filter = ("spoiler",)
    fieldsets = (
        ("Содержание", {"fields": ("author", "music_item", "collection", "text", "spoiler")}),
        ("Служебное", {"fields": ("deleted_at", "created_at", "updated_at")}),
    )
    readonly_fields = ("created_at", "updated_at")


@admin.register(Comment, site=crates_admin_site)
class CommentAdmin(admin.ModelAdmin):
    list_display = ("id", "review", "author", "parent", "created_at", "deleted_at")
    search_fields = ("author__username", "text")


@admin.register(Reaction, site=crates_admin_site)
class ReactionAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "target_type", "target_id", "value", "created_at")
    search_fields = ("user__username", "target_id")
    list_filter = ("target_type", "value")


@admin.register(Favorite, site=crates_admin_site)
class FavoriteAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "music_item", "created_at")
    search_fields = ("user__username", "music_item__title", "music_item__artist")


@admin.register(ReviewFavorite, site=crates_admin_site)
class ReviewFavoriteAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "review", "created_at")
    search_fields = ("user__username", "review__text")


@admin.register(ListeningEvent, site=crates_admin_site)
class ListeningEventAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "music_item",
        "started_at",
        "ended_at",
        "listen_seconds",
        "source",
    )
    search_fields = ("user__username", "music_item__title", "music_item__artist")
    list_filter = ("source",)
    date_hierarchy = "started_at"


@admin.register(MusicItemQualifiedListen, site=crates_admin_site)
class MusicItemQualifiedListenAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "music_item", "created_at")
    search_fields = ("user__username", "music_item__title", "music_item__artist")


@admin.register(Report, site=crates_admin_site)
class ReportAdmin(admin.ModelAdmin):
    list_display = ("id", "reporter", "target_type", "target_id", "status", "created_at")
    search_fields = ("reporter__username", "reason", "target_id")
    list_filter = ("status", "target_type")
    readonly_fields = ("created_at",)
    fieldsets = (
        ("Жалоба", {"fields": ("reporter", "target_type", "target_id", "reason", "status")}),
        ("Служебное", {"fields": ("created_at", "resolved_at")}),
    )


@admin.register(AdUnit, site=crates_admin_site)
class AdUnitAdmin(admin.ModelAdmin):
    form = AdUnitAdminForm
    list_display = ("id", "placement", "is_active", "has_banner_image", "updated_at")
    search_fields = ("placement",)
    list_filter = ("is_active",)
    fieldsets = (
        ("Реклама", {"fields": ("placement", "is_active", "banner_image", "config_json")}),
        ("Служебное", {"fields": ("created_at", "updated_at")}),
    )
    readonly_fields = ("created_at", "updated_at")

    def get_changeform_initial_data(self, request):
        data = super().get_changeform_initial_data(request)
        data.setdefault("placement", "app_top_banner")
        data.setdefault("config_json", "{}")
        return data

    @admin.display(boolean=True, description="Картинка")
    def has_banner_image(self, obj) -> bool:
        return bool(getattr(obj.banner_image, "name", ""))


@admin.register(Conversation, site=crates_admin_site)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ("id", "created_at")
    readonly_fields = ("created_at",)


@admin.register(ConversationMember, site=crates_admin_site)
class ConversationMemberAdmin(admin.ModelAdmin):
    list_display = ("id", "conversation", "user")
    search_fields = ("user__username", "conversation__id")


@admin.register(Message, site=crates_admin_site)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("id", "conversation", "author", "created_at")
    search_fields = ("author__username", "text")
    date_hierarchy = "created_at"


@admin.register(Follow, site=crates_admin_site)
class FollowAdmin(admin.ModelAdmin):
    list_display = ("id", "follower", "followee", "created_at")
    search_fields = ("follower__username", "followee__username")


@admin.register(Notification, site=crates_admin_site)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "type", "actor", "is_read", "created_at")
    search_fields = ("user__username", "actor__username", "entity_type", "entity_id")
    list_filter = ("type", "is_read")
    readonly_fields = ("created_at",)


crates_admin_site.register(User, UserAdmin)
crates_admin_site.register(Group, GroupAdmin)
