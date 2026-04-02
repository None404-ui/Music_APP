"""
DRF views for the CRATES API.

Exposes JSON endpoints used by the PyQt client:
- ViewSets for music items, collections, reviews, comments, reactions
- Social features: follows + feed
- Notifications and reports
- Profile endpoint and session-based auth endpoints (see auth_views.py)
"""

from django.db.models import Q
from django.utils import timezone
from django.db.models.functions import TruncDate
from django.db.models import Count
from datetime import timedelta
from rest_framework import mixins, permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    Collection,
    CollectionItem,
    Comment,
    Conversation,
    Favorite,
    Follow,
    Message,
    ReviewFavorite,
    MusicItem,
    Profile,
    Report,
    Review,
)
from .models import AdUnit, ListeningEvent, Notification, Reaction
from .permissions import (
    IsAdminOrReadOnly,
    IsAuthorOrReadOnly,
    IsConversationMember,
    IsCollectionItemOwner,
    IsStaff,
    IsOwnerOrReadOnly,
)
from .serializers import (
    CollectionSerializer,
    CollectionItemSerializer,
    CommentSerializer,
    ConversationSerializer,
    FavoriteSerializer,
    FollowSerializer,
    MusicItemSerializer,
    MessageSerializer,
    ReviewFavoriteSerializer,
    NotificationSerializer,
    ProfileSerializer,
    ReactionSerializer,
    ReportSerializer,
    ReviewSerializer,
    ListeningEventSerializer,
    AdUnitSerializer,
)


class MusicItemViewSet(viewsets.ModelViewSet):
    queryset = MusicItem.objects.all().order_by("-updated_at")
    serializer_class = MusicItemSerializer
    permission_classes = [IsAdminOrReadOnly]

    def get_queryset(self):
        qs = super().get_queryset()
        q = self.request.query_params.get("q")
        if q:
            qs = qs.filter(Q(title__icontains=q) | Q(artist__icontains=q))
        provider = self.request.query_params.get("provider")
        if provider:
            qs = qs.filter(provider=provider)
        kind = self.request.query_params.get("kind")
        if kind:
            qs = qs.filter(kind=kind)
        return qs


class CollectionViewSet(viewsets.ModelViewSet):
    serializer_class = CollectionSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsOwnerOrReadOnly]

    def get_queryset(self):
        return Collection.objects.all().order_by("-created_at")

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


class ReviewViewSet(viewsets.ModelViewSet):
    serializer_class = ReviewSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsAuthorOrReadOnly]

    def get_queryset(self):
        qs = Review.objects.all().order_by("-created_at")
        q = self.request.query_params.get("q")
        if q:
            qs = qs.filter(text__icontains=q)
        author_id = self.request.query_params.get("author_id")
        if author_id:
            qs = qs.filter(author_id=author_id)
        music_item_id = self.request.query_params.get("music_item_id")
        if music_item_id:
            qs = qs.filter(music_item_id=music_item_id)
        collection_id = self.request.query_params.get("collection_id")
        if collection_id:
            qs = qs.filter(collection_id=collection_id)
        return qs

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)


class CommentViewSet(viewsets.ModelViewSet):
    serializer_class = CommentSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsAuthorOrReadOnly]

    def get_queryset(self):
        qs = Comment.objects.all().order_by("created_at")
        review_id = self.request.query_params.get("review_id")
        if review_id:
            qs = qs.filter(review_id=review_id)
        return qs

    def perform_create(self, serializer):
        comment = serializer.save(author=self.request.user)
        # Notify review author
        if comment.review.author_id != self.request.user.id:
            Notification.objects.create(
                user_id=comment.review.author_id,
                type=Notification.Type.COMMENT,
                actor=self.request.user,
                entity_type="review",
                entity_id=comment.review_id,
            )


class ReactionViewSet(
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = ReactionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = Reaction.objects.all().order_by("-created_at")
        # Do not leak other users' reactions
        qs = qs.filter(user=self.request.user)
        target_type = self.request.query_params.get("target_type")
        target_id = self.request.query_params.get("target_id")
        if target_type:
            qs = qs.filter(target_type=target_type)
        if target_id:
            qs = qs.filter(target_id=target_id)
        return qs

    def perform_create(self, serializer):
        # Idempotent create: if user already reacted to the same target,
        # update value instead of violating UNIQUE constraint.
        data = serializer.validated_data
        user = self.request.user
        target_type = data["target_type"]
        target_id = data["target_id"]
        value = data["value"]

        reaction, created = Reaction.objects.get_or_create(
            user=user,
            target_type=target_type,
            target_id=target_id,
            defaults={"value": value},
        )
        updated = False
        if not created:
            if reaction.value != value:
                reaction.value = value
                reaction.save(update_fields=["value"])
                updated = True

        serializer.instance = reaction
        if created or updated:
            self._notify_reaction(reaction)

    def perform_update(self, serializer):
        reaction = serializer.save()
        self._notify_reaction(reaction)

    def _notify_reaction(self, reaction: Reaction) -> None:
        if reaction.target_type == Reaction.TargetType.REVIEW:
            try:
                review = Review.objects.get(id=reaction.target_id)
            except Review.DoesNotExist:
                return
            if review.author_id != reaction.user_id:
                Notification.objects.create(
                    user_id=review.author_id,
                    type=Notification.Type.REACTION,
                    actor=reaction.user,
                    entity_type="review",
                    entity_id=review.id,
                )
        elif reaction.target_type == Reaction.TargetType.COMMENT:
            try:
                comment = Comment.objects.get(id=reaction.target_id)
            except Comment.DoesNotExist:
                return
            if comment.author_id != reaction.user_id:
                Notification.objects.create(
                    user_id=comment.author_id,
                    type=Notification.Type.REACTION,
                    actor=reaction.user,
                    entity_type="comment",
                    entity_id=comment.id,
                )


class FavoriteViewSet(
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = FavoriteSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = Favorite.objects.all().order_by("-created_at")
        if self.request.user.is_authenticated:
            return qs.filter(user=self.request.user)
        return qs.none()

    def perform_create(self, serializer):
        # Idempotent create.
        music_item = serializer.validated_data["music_item"]
        favorite, _created = Favorite.objects.get_or_create(
            user=self.request.user, music_item=music_item
        )
        serializer.instance = favorite


class ReviewFavoriteViewSet(
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    """
    Избранное для рецензий (Review).
    """

    serializer_class = ReviewFavoriteSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = ReviewFavorite.objects.all().order_by("-created_at")
        return qs.filter(user=self.request.user)

    def perform_create(self, serializer):
        # Idempotent create.
        review = serializer.validated_data["review"]
        favorite, _created = ReviewFavorite.objects.get_or_create(
            user=self.request.user, review=review
        )
        serializer.instance = favorite


class FollowViewSet(
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = FollowSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = Follow.objects.all().order_by("-created_at")
        kind = self.request.query_params.get("kind")  # following|followers
        user_id = self.request.query_params.get("user_id")
        if user_id:
            if kind == "followers":
                return qs.filter(followee_id=user_id)
            return qs.filter(follower_id=user_id)

        # Default: current user's following list
        return qs.filter(follower=self.request.user)

    def perform_create(self, serializer):
        # Idempotent create: if follow already exists, do not duplicate notification.
        followee = serializer.validated_data["followee"]
        follow, created = Follow.objects.get_or_create(
            follower=self.request.user, followee=followee
        )
        serializer.instance = follow

        # Notify followee only on first follow.
        if created and follow.followee_id != self.request.user.id:
            Notification.objects.create(
                user_id=follow.followee_id,
                type=Notification.Type.FOLLOW,
                actor=self.request.user,
                entity_type="follow",
                entity_id=follow.id,
            )


class FeedView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        followee_ids = Follow.objects.filter(follower=request.user).values_list(
            "followee_id", flat=True
        )
        qs = Review.objects.filter(author_id__in=list(followee_ids)).order_by("-created_at")
        return Response(ReviewSerializer(qs, many=True).data)


class GenreRecommendationsView(APIView):
    """
    Рекомендации по любимым жанрам пользователя.

    Логика максимально простая (MVP):
    - берём `Profile.favorite_genres` (строка CSV или JSON-массив)
    - ищем ключевые слова в:
      - `Review.text`
      - и в связанной музыке: `MusicItem.meta_json/title/artist`
    """

    permission_classes = [permissions.IsAuthenticated]

    def _parse_genres(self, raw):
        if not raw:
            return []

        raw = raw.strip()
        if not raw:
            return []

        import json

        # JSON-сценарии (на будущее): ["rock","metal"] или {"genres":[...]}
        if raw.startswith("[") or raw.startswith("{"):
            try:
                obj = json.loads(raw)
                if isinstance(obj, list):
                    items = obj
                elif isinstance(obj, dict):
                    items = obj.get("genres") or obj.get("favorite_genres") or []
                else:
                    items = []
                if isinstance(items, list):
                    return [str(x).strip().lower() for x in items if str(x).strip()]
            except Exception:
                pass

        # CSV/строки: "rock, metal; indie"
        parts = raw.replace(";", ",").split(",")
        return [p.strip().lower() for p in parts if p.strip()]

    def get(self, request):
        limit = int(request.query_params.get("limit") or 50)
        limit = max(1, min(limit, 200))

        profile = Profile.objects.filter(user=request.user).first()
        genres = self._parse_genres(getattr(profile, "favorite_genres", None) if profile else "")
        qs = Review.objects.all()

        if genres:
            cond = Q()
            for g in genres:
                # В MVP допускаем грубое соответствие по тексту/метаданным.
                cond |= (
                    Q(text__icontains=g)
                    | Q(music_item__meta_json__icontains=g)
                    | Q(music_item__title__icontains=g)
                    | Q(music_item__artist__icontains=g)
                )
            qs = qs.filter(cond)

        qs = qs.order_by("-created_at")[:limit]
        return Response(ReviewSerializer(qs, many=True).data)


class NotificationViewSet(
    mixins.ListModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = Notification.objects.filter(user=self.request.user).order_by("-created_at")
        is_read = self.request.query_params.get("is_read")
        if is_read in ("0", "1"):
            qs = qs.filter(is_read=(is_read == "1"))
        return qs

    @action(detail=False, methods=["post"])
    def mark_read(self, request):
        ids = request.data.get("ids") or []
        Notification.objects.filter(user=request.user, id__in=ids).update(is_read=True)
        return Response({"detail": "ok"})


class ReportViewSet(viewsets.ModelViewSet):
    serializer_class = ReportSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = Report.objects.all().order_by("-created_at")
        if self.request.user.is_staff:
            return qs
        return qs.filter(reporter=self.request.user)

    def perform_create(self, serializer):
        # Неформально: обычный пользователь создаёт жалобу, статус всегда "open".
        # Staff/admin может менять статус через update/partial_update.
        if self.request.user.is_staff:
            serializer.save(reporter=self.request.user)
        else:
            serializer.save(reporter=self.request.user, status=Report.Status.OPEN)

    def update(self, request, *args, **kwargs):
        if not request.user.is_staff:
            return Response({"detail": "Forbidden"}, status=403)
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        if not request.user.is_staff:
            return Response({"detail": "Forbidden"}, status=403)
        return super().partial_update(request, *args, **kwargs)


class MeProfileView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        profile, _ = Profile.objects.get_or_create(
            user=request.user, defaults={"nickname": request.user.username}
        )
        return Response(ProfileSerializer(profile).data)

    def patch(self, request):
        profile, _ = Profile.objects.get_or_create(
            user=request.user, defaults={"nickname": request.user.username}
        )
        serializer = ProfileSerializer(profile, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class ListeningEventsView(APIView):
    """
    Дневник прослушиваний.

    Эндпоинты:
    - GET  /api/listening-events/
    - POST /api/listening-events/
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        limit = int(request.query_params.get("limit") or 50)
        music_item_id = request.query_params.get("music_item_id")

        qs = ListeningEvent.objects.filter(user=request.user).order_by("-started_at")
        if music_item_id:
            qs = qs.filter(music_item_id=music_item_id)

        qs = qs[: max(1, min(limit, 200))]
        return Response(ListeningEventSerializer(qs, many=True).data)

    def post(self, request):
        serializer = ListeningEventSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        obj = serializer.save(user=request.user)
        return Response(ListeningEventSerializer(obj).data, status=201)


class ListeningStatsView(APIView):
    """
    Статистика по прослушиваниям.

    GET /api/stats/listening/?days=7
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        days = int(request.query_params.get("days") or 7)
        days = max(1, min(days, 30))
        since = timezone.now() - timedelta(days=days)

        qs = ListeningEvent.objects.filter(user=request.user, started_at__gte=since)
        events = list(qs.only("started_at", "ended_at"))

        by_day = {}
        total_seconds = 0.0
        now = timezone.now()

        for e in events:
            day_key = e.started_at.date().isoformat()
            ended = e.ended_at or now
            seconds = max(0.0, (ended - e.started_at).total_seconds())
            total_seconds += seconds

            by_day.setdefault(day_key, {"day": day_key, "count": 0, "seconds": 0.0})
            by_day[day_key]["count"] += 1
            by_day[day_key]["seconds"] += seconds

        # Сортируем по дню
        by_day_list = [by_day[k] for k in sorted(by_day.keys())]
        return Response(
            {
                "days": days,
                "total_events": len(events),
                "total_seconds": total_seconds,
                "by_day": by_day_list,
            }
        )


class AdsView(APIView):
    """
    Выдача рекламы.

    Логика:
    - если пользователь premium -> ads=[].
    - иначе -> вернуть активные `AdUnit` по placement.
    """

    permission_classes = [permissions.AllowAny]

    def get(self, request):
        placement = request.query_params.get("placement") or "feed_banner"
        limit = int(request.query_params.get("limit") or 3)

        is_premium = False
        if request.user.is_authenticated:
            profile = Profile.objects.filter(user=request.user).first()
            is_premium = bool(profile and profile.is_premium)

        if is_premium:
            return Response({"ads": []})

        ads = (
            AdUnit.objects.filter(is_active=True, placement=placement)
            .order_by("-id")
            .select_related(None)[: max(1, min(limit, 10))]
        )

        # config_json обычно строка JSON; возвращаем как строку, если парсинг не удался.
        import json

        items = []
        for ad in ads:
            try:
                cfg = json.loads(ad.config_json)
            except Exception:
                cfg = ad.config_json
            items.append(
                {
                    "id": ad.id,
                    "placement": ad.placement,
                    "config": cfg,
                }
            )

        return Response({"ads": items})


class AdUnitViewSet(viewsets.ModelViewSet):
    """
    Админ API управления рекламными слотами (ad_units).

    Доступ: только staff/admin.
    """

    serializer_class = AdUnitSerializer
    permission_classes = [permissions.IsAuthenticated, IsStaff]

    def get_queryset(self):
        return AdUnit.objects.all().order_by("-id")

    def perform_create(self, serializer):
        serializer.save()

    def perform_update(self, serializer):
        serializer.save()

    def perform_destroy(self, instance):
        instance.delete()


class ConversationViewSet(
    mixins.CreateModelMixin, mixins.ListModelMixin, viewsets.GenericViewSet
):
    """
    Чат: диалоги + отправка/получение сообщений.
    """

    serializer_class = ConversationSerializer
    permission_classes = [permissions.IsAuthenticated, IsConversationMember]

    def get_queryset(self):
        return Conversation.objects.filter(members__user=self.request.user).distinct()

    def perform_create(self, serializer):
        participant_ids = self.request.data.get("participant_ids") or []
        participant_ids = set(int(x) for x in participant_ids if x)

        # В диалог всегда добавляем текущего пользователя.
        member_ids = participant_ids | {self.request.user.id}

        # Ищем уже существующий диалог с *точно таким же* набором участников.
        # Это делает POST idempotent: при повторном запросе новых диалогов не создаём.
        exact = (
            Conversation.objects.filter(members__user_id__in=member_ids)
            .annotate(
                total_members=Count("members", distinct=True),
                matched_members=Count(
                    "members",
                    filter=Q(members__user_id__in=member_ids),
                    distinct=True,
                ),
            )
            .filter(
                total_members=len(member_ids),
                matched_members=len(member_ids),
            )
            .distinct()
        ).first()

        if exact is not None:
            serializer.instance = exact
            return

        conversation = serializer.save()

        # Создаём участников диалога (включая request.user).
        ConversationMember = conversation.members.model  # model class for manager
        ConversationMember.objects.create(conversation=conversation, user=self.request.user)
        for uid in participant_ids:
            ConversationMember.objects.create(conversation=conversation, user_id=uid)

    @action(detail=True, methods=["get", "post"], url_path="messages")
    def messages(self, request, pk=None):
        conversation = self.get_object()
        if request.method == "GET":
            limit = request.query_params.get("limit")
            limit = int(limit) if limit is not None else None
            qs = Message.objects.filter(conversation=conversation).order_by("created_at")
            if limit is not None:
                qs = qs[: max(1, min(limit, 200))]
            return Response(MessageSerializer(qs, many=True).data)
        text = request.data.get("text")
        if not text:
            return Response({"detail": "Text is required"}, status=400)

        msg = Message.objects.create(conversation=conversation, author=request.user, text=text)
        return Response(MessageSerializer(msg).data, status=201)


class CollectionItemViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """
    Управление треками внутри коллекций (плейлистов).
    """

    serializer_class = CollectionItemSerializer
    permission_classes = [IsCollectionItemOwner]

    def get_queryset(self):
        qs = CollectionItem.objects.select_related("collection", "music_item").all()
        collection_id = self.request.query_params.get("collection_id")
        if collection_id:
            qs = qs.filter(collection_id=collection_id)

        # Для чтения разрешаем открытые коллекции; для записи — только owner через permission.
        if self.request.method in permissions.SAFE_METHODS:
            if self.request.user.is_authenticated:
                return qs.filter(Q(collection__is_public=True) | Q(collection__owner=self.request.user))
            return qs.filter(collection__is_public=True)

        # Небезопасные методы: queryset ограничиваем owner'ом, чтобы не отдавать лишнее.
        return qs.filter(collection__owner=self.request.user)

    def perform_create(self, serializer):
        collection = serializer.validated_data["collection"]
        if collection.owner_id != self.request.user.id:
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied("Only collection owner can edit items.")

        music_item = serializer.validated_data["music_item"]
        position = serializer.validated_data.get("position")

        item, created = CollectionItem.objects.get_or_create(
            collection=collection, music_item=music_item, defaults={}
        )
        if position is not None and (not created) and item.position != position:
            item.position = position
            item.save(update_fields=["position"])

        serializer.instance = item
