"""
DRF views for the CRATES API.

Exposes JSON endpoints used by the PyQt client:
- ViewSets for music items, collections, reviews, comments, reactions
- Social features: follows + feed
- Notifications and reports
- Profile endpoint and session-based auth endpoints (see auth_views.py)
"""

from django.db.models import Q
from rest_framework import mixins, permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    Collection,
    Comment,
    Conversation,
    Favorite,
    Follow,
    Message,
    MusicItem,
    Profile,
    Report,
    Review,
)
from .models import Notification, Reaction
from .permissions import IsAdminOrReadOnly, IsAuthorOrReadOnly, IsConversationMember, IsOwnerOrReadOnly
from .serializers import (
    CollectionSerializer,
    CommentSerializer,
    ConversationSerializer,
    FavoriteSerializer,
    FollowSerializer,
    MusicItemSerializer,
    MessageSerializer,
    NotificationSerializer,
    ProfileSerializer,
    ReactionSerializer,
    ReportSerializer,
    ReviewSerializer,
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
        reaction = serializer.save(user=self.request.user)
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
        serializer.save(user=self.request.user)


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
        follow = serializer.save(follower=self.request.user)
        # Notify followee
        if follow.followee_id != self.request.user.id:
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
        serializer.save(reporter=self.request.user)

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
        participant_ids.discard(self.request.user.id)
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
            qs = Message.objects.filter(conversation=conversation).order_by("created_at")
            return Response(MessageSerializer(qs, many=True).data)

        text = request.data.get("text")
        if not text:
            return Response({"detail": "Text is required"}, status=400)

        msg = Message.objects.create(conversation=conversation, author=request.user, text=text)
        return Response(MessageSerializer(msg).data, status=201)
