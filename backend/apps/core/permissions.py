"""
DRF permission classes used to enforce strict ownership/admin rules.
"""

from rest_framework import permissions


class IsAdminOrReadOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return bool(request.user and request.user.is_staff)


class IsOwnerOrReadOnly(permissions.BasePermission):
    owner_field = "owner"

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        owner = getattr(obj, self.owner_field, None)
        return bool(owner and request.user and owner == request.user)


class IsAuthorOrReadOnly(IsOwnerOrReadOnly):
    owner_field = "author"


class IsConversationMember(permissions.BasePermission):
    """
    Разрешает доступ к диалогу только участникам.
    Используется для detail-действий (где obj = Conversation).
    """

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            # Для сообщений/просмотра также нужна принадлежность к диалогу.
            pass
        if not request.user or not request.user.is_authenticated:
            return False
        return obj.members.filter(user=request.user).exists()


class IsCollectionItemOwner(permissions.BasePermission):
    """
    Доступ к CollectionItem (трекам в плейлисте):
    - чтение: разрешаем
    - создание/изменение/удаление: только если коллекция принадлежит пользователю
    """

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return bool(obj.collection and obj.collection.owner == request.user)


class IsStaff(permissions.BasePermission):
    """
    Доступ только для staff/admin (используется для админ API).
    """

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_staff)

