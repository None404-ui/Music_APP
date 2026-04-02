"""
Django admin registrations for CRATES backend models.

Enables CRUD inspection for development:
- profiles + external music catalog cache
- collections/playlists, reviews/comments, reactions
- social graph, notifications, reports
"""

from django.contrib import admin

from .models import (
    AdUnit,
    Conversation,
    ConversationMember,
    Follow,
    Collection,
    CollectionItem,
    Comment,
    Favorite,
    ReviewFavorite,
    ListeningEvent,
    MusicItem,
    MusicItemQualifiedListen,
    Notification,
    Profile,
    Reaction,
    Report,
    Review,
    Message,
)


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "nickname", "is_premium", "premium_until", "updated_at")
    search_fields = ("nickname", "user__username", "user__email")


@admin.register(MusicItem)
class MusicItemAdmin(admin.ModelAdmin):
    list_display = ("id", "provider", "kind", "artist", "title", "updated_at")
    search_fields = ("title", "artist", "external_id")
    list_filter = ("provider", "kind")
    # Во вкладке «Популярное» в карусели «Альбомы» попадают только записи с kind = album (не track / playlist).


@admin.register(Collection)
class CollectionAdmin(admin.ModelAdmin):
    list_display = ("id", "owner", "title", "is_public", "created_at", "deleted_at")
    search_fields = ("title", "owner__username")
    list_filter = ("is_public",)


@admin.register(CollectionItem)
class CollectionItemAdmin(admin.ModelAdmin):
    list_display = ("id", "collection", "music_item", "position", "added_at")
    search_fields = ("collection__title", "music_item__title", "music_item__artist")


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("id", "author", "music_item", "collection", "created_at", "deleted_at")
    search_fields = ("author__username", "text")


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ("id", "review", "author", "parent", "created_at", "deleted_at")
    search_fields = ("author__username", "text")


@admin.register(Reaction)
class ReactionAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "target_type", "target_id", "value", "created_at")
    search_fields = ("user__username", "target_id")
    list_filter = ("target_type", "value")


@admin.register(Favorite)
class FavoriteAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "music_item", "created_at")
    search_fields = ("user__username", "music_item__title", "music_item__artist")


@admin.register(ReviewFavorite)
class ReviewFavoriteAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "review", "created_at")
    search_fields = ("user__username", "review__text")


@admin.register(ListeningEvent)
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


@admin.register(MusicItemQualifiedListen)
class MusicItemQualifiedListenAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "music_item", "created_at")
    search_fields = ("user__username", "music_item__title", "music_item__artist")


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ("id", "reporter", "target_type", "target_id", "status", "created_at")
    search_fields = ("reporter__username", "reason", "target_id")
    list_filter = ("status", "target_type")


@admin.register(AdUnit)
class AdUnitAdmin(admin.ModelAdmin):
    list_display = ("id", "placement", "is_active", "updated_at")
    search_fields = ("placement",)
    list_filter = ("is_active",)


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ("id", "created_at")


@admin.register(ConversationMember)
class ConversationMemberAdmin(admin.ModelAdmin):
    list_display = ("id", "conversation", "user")
    search_fields = ("user__username", "conversation__id")


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("id", "conversation", "author", "created_at")
    search_fields = ("author__username", "text")


@admin.register(Follow)
class FollowAdmin(admin.ModelAdmin):
    list_display = ("id", "follower", "followee", "created_at")
    search_fields = ("follower__username", "followee__username")


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "type", "actor", "is_read", "created_at")
    search_fields = ("user__username", "actor__username", "entity_type", "entity_id")
    list_filter = ("type", "is_read")
