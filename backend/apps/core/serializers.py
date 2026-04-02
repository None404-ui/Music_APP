"""
DRF serializers for all core models.

Responsible for the JSON shape returned/accepted by API endpoints
defined in `views.py`.
"""

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import serializers

from .models import (
    AdUnit,
    Conversation,
    ConversationMember,
    Collection,
    CollectionItem,
    Comment,
    Favorite,
    Follow,
    ListeningEvent,
    Message,
    MusicItem,
    Notification,
    ReviewFavorite,
    Profile,
    Reaction,
    Report,
    Review,
)


User = get_user_model()


class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profile
        fields = [
            "id",
            "user",
            "nickname",
            "avatar_url",
            "bio",
            "is_premium",
            "premium_until",
            "favorite_genres",
            "ui_theme_color",
            "ui_background",
            "ui_progress_color",
            "player_preset",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "user", "created_at", "updated_at"]


class MusicItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = MusicItem
        fields = [
            "id",
            "provider",
            "external_id",
            "kind",
            "title",
            "artist",
            "artwork_url",
            "duration_sec",
            "playback_ref",
            "meta_json",
            "updated_at",
        ]
        read_only_fields = ["id", "updated_at"]


class CollectionItemSerializer(serializers.ModelSerializer):
    music_item = MusicItemSerializer(read_only=True)
    music_item_id = serializers.PrimaryKeyRelatedField(
        source="music_item", queryset=MusicItem.objects.all(), write_only=True
    )

    class Meta:
        model = CollectionItem
        fields = ["id", "collection", "music_item", "music_item_id", "position", "added_at"]
        read_only_fields = ["id", "added_at"]


class CollectionSerializer(serializers.ModelSerializer):
    items = CollectionItemSerializer(many=True, read_only=True)

    class Meta:
        model = Collection
        fields = [
            "id",
            "owner",
            "title",
            "description",
            "is_public",
            "cover_url",
            "deleted_at",
            "created_at",
            "updated_at",
            "items",
        ]
        read_only_fields = ["id", "owner", "created_at", "updated_at"]


class ReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = Review
        fields = [
            "id",
            "author",
            "music_item",
            "collection",
            "text",
            "spoiler",
            "deleted_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "author", "created_at", "updated_at"]


class CommentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Comment
        fields = [
            "id",
            "review",
            "author",
            "parent",
            "text",
            "deleted_at",
            "created_at",
        ]
        read_only_fields = ["id", "author", "created_at"]


class ReactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Reaction
        fields = ["id", "user", "target_type", "target_id", "value", "created_at"]
        read_only_fields = ["id", "user", "created_at"]


class FavoriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Favorite
        fields = ["id", "user", "music_item", "created_at"]
        read_only_fields = ["id", "user", "created_at"]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["music_item"] = MusicItemSerializer(instance.music_item).data
        return data


class ListeningEventSerializer(serializers.ModelSerializer):
    # Для удобства клиента `started_at` не обязателен: если не передан — ставим текущее время.
    started_at = serializers.DateTimeField(required=False)
    ended_at = serializers.DateTimeField(required=False, allow_null=True)

    class Meta:
        model = ListeningEvent
        fields = ["id", "user", "music_item", "started_at", "ended_at", "source"]
        read_only_fields = ["id", "user"]

    def create(self, validated_data):
        validated_data.setdefault("started_at", timezone.now())
        return super().create(validated_data)


class ReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = Report
        fields = [
            "id",
            "reporter",
            "target_type",
            "target_id",
            "reason",
            "status",
            "created_at",
            "resolved_at",
        ]
        read_only_fields = ["id", "reporter", "created_at", "resolved_at"]


class AdUnitSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdUnit
        fields = ["id", "placement", "is_active", "config_json", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class FollowSerializer(serializers.ModelSerializer):
    class Meta:
        model = Follow
        fields = ["id", "follower", "followee", "created_at"]
        read_only_fields = ["id", "follower", "created_at"]


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = [
            "id",
            "user",
            "type",
            "actor",
            "entity_type",
            "entity_id",
            "is_read",
            "created_at",
        ]
        read_only_fields = ["id", "user", "created_at"]


class ReviewFavoriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReviewFavorite
        fields = ["id", "user", "review", "created_at"]
        read_only_fields = ["id", "user", "created_at"]


class ConversationSerializer(serializers.ModelSerializer):
    participants = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = ["id", "created_at", "participants"]
        read_only_fields = ["id", "created_at", "participants"]

    def get_participants(self, obj: Conversation):
        return list(obj.members.values_list("user_id", flat=True))


class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = ["id", "conversation", "author", "text", "created_at"]
        read_only_fields = ["id", "conversation", "author", "created_at"]

