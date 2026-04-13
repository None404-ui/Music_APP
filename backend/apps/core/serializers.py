"""
DRF serializers for all core models.

Responsible for the JSON shape returned/accepted by API endpoints
defined in `views.py`.
"""

from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Sum
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
    MusicItemQualifiedListen,
    Notification,
    ReviewFavorite,
    Profile,
    Reaction,
    Report,
    Review,
)


User = get_user_model()


def public_artist_user_payload(user_id: int, request) -> dict | None:
    """Публичные поля исполнителя для вложения в MusicItem и фиды."""
    if not user_id:
        return None
    prof = Profile.objects.filter(user_id=user_id).first()
    nickname = ""
    avatar_url = ""
    if prof:
        nickname = prof.nickname
        avatar_url = (prof.avatar_url or "").strip()
        af = getattr(prof, "avatar_file", None)
        if af and getattr(af, "name", ""):
            rel = af.url
            avatar_url = (
                request.build_absolute_uri(rel) if request else rel
            )
    if not nickname:
        u = User.objects.filter(pk=user_id).first()
        if not u:
            return None
        nickname = u.get_username()
    return {"id": user_id, "nickname": nickname, "avatar_url": avatar_url}


class ProfileSerializer(serializers.ModelSerializer):
    def to_representation(self, instance):
        data = super().to_representation(instance)
        data.pop("avatar_file", None)
        request = self.context.get("request")
        af = getattr(instance, "avatar_file", None)
        if af and getattr(af, "name", ""):
            rel = af.url
            data["avatar_url"] = (
                request.build_absolute_uri(rel) if request else rel
            )
        return data

    class Meta:
        model = Profile
        fields = [
            "id",
            "user",
            "nickname",
            "avatar_url",
            "avatar_file",
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
        extra_kwargs = {"avatar_file": {"required": False, "allow_null": True}}


class MusicItemSerializer(serializers.ModelSerializer):
    artist_user_id = serializers.IntegerField(read_only=True, allow_null=True)
    artist_user = serializers.SerializerMethodField()
    reviews_count = serializers.SerializerMethodField()
    favorites_count = serializers.SerializerMethodField()
    listens_count = serializers.SerializerMethodField()
    listen_time_total_sec = serializers.SerializerMethodField()
    user_favorited = serializers.SerializerMethodField()

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get("request")
        audio = getattr(instance, "audio_file", None)
        if audio and getattr(audio, "name", ""):
            rel = audio.url
            data["playback_ref"] = (
                request.build_absolute_uri(rel) if request else rel
            )
        cover = getattr(instance, "artwork_file", None)
        if cover and getattr(cover, "name", ""):
            rel = cover.url
            data["artwork_url"] = (
                request.build_absolute_uri(rel) if request else rel
            )
        return data

    def get_artist_user(self, obj):
        uid = getattr(obj, "artist_user_id", None)
        if not uid:
            return None
        return public_artist_user_payload(uid, self.context.get("request"))

    class Meta:
        model = MusicItem
        fields = [
            "id",
            "provider",
            "external_id",
            "kind",
            "title",
            "artist",
            "artist_user_id",
            "artist_user",
            "artwork_url",
            "duration_sec",
            "playback_ref",
            "meta_json",
            "updated_at",
            "reviews_count",
            "favorites_count",
            "listens_count",
            "listen_time_total_sec",
            "user_favorited",
        ]
        read_only_fields = ["id", "updated_at"]

    def _ann(self, obj, name: str):
        v = getattr(obj, name, None)
        return v if v is not None else None

    def get_reviews_count(self, obj):
        v = self._ann(obj, "reviews_count")
        if v is not None:
            return int(v)
        return Review.objects.filter(
            music_item_id=obj.pk, deleted_at__isnull=True
        ).count()

    def get_favorites_count(self, obj):
        v = self._ann(obj, "favorites_count")
        if v is not None:
            return int(v)
        return Favorite.objects.filter(music_item_id=obj.pk).count()

    def get_listens_count(self, obj):
        v = self._ann(obj, "listens_count")
        if v is not None:
            return int(v)
        return MusicItemQualifiedListen.objects.filter(music_item_id=obj.pk).count()

    def get_listen_time_total_sec(self, obj):
        v = self._ann(obj, "listen_time_total_sec")
        if v is not None:
            return int(v)
        r = ListeningEvent.objects.filter(music_item_id=obj.pk).aggregate(
            s=Sum("listen_seconds")
        )
        return int(r["s"] or 0)

    def get_user_favorited(self, obj):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False
        return Favorite.objects.filter(user=request.user, music_item_id=obj.pk).exists()


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
    favorites_count = serializers.SerializerMethodField()
    user_favorited = serializers.SerializerMethodField()
    author_label = serializers.SerializerMethodField()

    class Meta:
        model = Review
        fields = [
            "id",
            "author",
            "author_label",
            "music_item",
            "collection",
            "text",
            "spoiler",
            "deleted_at",
            "created_at",
            "updated_at",
            "favorites_count",
            "user_favorited",
        ]
        read_only_fields = [
            "id",
            "author",
            "author_label",
            "created_at",
            "updated_at",
            "favorites_count",
            "user_favorited",
        ]
        extra_kwargs = {
            "music_item": {"required": False, "allow_null": True},
            "collection": {"required": False, "allow_null": True},
        }

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if instance.music_item_id:
            data["music_item"] = MusicItemSerializer(
                instance.music_item, context=self.context
            ).data
        else:
            data["music_item"] = None
        if instance.collection_id:
            c = instance.collection
            data["collection"] = {
                "id": c.id,
                "title": c.title,
                "cover_url": c.cover_url or "",
            }
        else:
            data["collection"] = None
        return data

    def get_author_label(self, obj):
        u = obj.author
        try:
            prof = u.profile
        except ObjectDoesNotExist:
            prof = None
        if prof is not None and (prof.nickname or "").strip():
            return prof.nickname.strip()
        return (getattr(u, "email", None) or u.get_username() or "").strip() or "—"

    def get_favorites_count(self, obj):
        v = getattr(obj, "favorites_count", None)
        if v is not None:
            return int(v)
        return ReviewFavorite.objects.filter(review_id=obj.pk).count()

    def get_user_favorited(self, obj):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False
        return ReviewFavorite.objects.filter(
            user=request.user, review_id=obj.pk
        ).exists()

    def validate(self, attrs):
        if self.instance is None:
            mi = attrs.get("music_item")
            col = attrs.get("collection")
            if (mi is None and col is None) or (mi is not None and col is not None):
                raise serializers.ValidationError(
                    "Укажите ровно одно поле: music_item или collection."
                )
        return attrs


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
        fields = [
            "id",
            "user",
            "music_item",
            "started_at",
            "ended_at",
            "source",
            "listen_seconds",
        ]
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

