"""
URL routing for the CRATES API.

All endpoints are mounted under `/api/` in `backend/crates/urls.py`.
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views
from . import auth_views


router = DefaultRouter()
router.register("music-items", views.MusicItemViewSet, basename="music-item")
router.register("collections", views.CollectionViewSet, basename="collection")
router.register("reviews", views.ReviewViewSet, basename="review")
router.register("comments", views.CommentViewSet, basename="comment")
router.register("favorites", views.FavoriteViewSet, basename="favorite")
router.register("reactions", views.ReactionViewSet, basename="reaction")
router.register("follows", views.FollowViewSet, basename="follow")
router.register("notifications", views.NotificationViewSet, basename="notification")
router.register("reports", views.ReportViewSet, basename="report")
router.register("conversations", views.ConversationViewSet, basename="conversation")
router.register("review-favorites", views.ReviewFavoriteViewSet, basename="review-favorite")
router.register("collection-items", views.CollectionItemViewSet, basename="collection-item")
router.register("ad-units", views.AdUnitViewSet, basename="ad-unit")


urlpatterns = [
    path("", include(router.urls)),
    path("auth/login/", auth_views.LoginView.as_view(), name="auth-login"),
    path("auth/logout/", auth_views.LogoutView.as_view(), name="auth-logout"),
    path("auth/register/", auth_views.RegisterView.as_view(), name="auth-register"),
    path("profile/me/", views.MeProfileView.as_view(), name="me-profile"),
    path("feed/", views.FeedView.as_view(), name="feed"),
    path("recommendations/", views.GenreRecommendationsView.as_view(), name="recommendations"),
    path("listening-events/", views.ListeningEventsView.as_view(), name="listening-events"),
    path("stats/listening/", views.ListeningStatsView.as_view(), name="stats-listening"),
    path("ads/", views.AdsView.as_view(), name="ads"),
]

