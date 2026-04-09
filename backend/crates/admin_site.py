"""
Отдельный AdminSite для CRATES: русские заголовки и порядок моделей по разделам.
"""

from django.contrib.admin import AdminSite


class CratesAdminSite(AdminSite):
    site_header = "Администрирование CRATES"
    site_title = "CRATES"
    index_title = "Панель управления"

    # Логический порядок моделей внутри приложения core (имя класса модели).
    _CORE_MODEL_ORDER = [
        # Пользователи и профили
        "Profile",
        # Каталог
        "MusicItem",
        # Подборки
        "Collection",
        "CollectionItem",
        # Контент
        "Review",
        "Comment",
        "Reaction",
        "Favorite",
        "ReviewFavorite",
        # Социальное
        "Follow",
        "Notification",
        # Чаты
        "Conversation",
        "ConversationMember",
        "Message",
        # Статистика прослушиваний
        "ListeningEvent",
        "MusicItemQualifiedListen",
        # Модерация и реклама
        "Report",
        "AdUnit",
    ]

    def get_app_list(self, request, app_label=None):
        app_list = super().get_app_list(request, app_label)
        order = {name: i for i, name in enumerate(self._CORE_MODEL_ORDER)}

        for app in app_list:
            if app.get("app_label") != "core":
                continue
            app["models"].sort(
                key=lambda m: order.get(m.get("object_name", ""), 999)
            )

        # Порядок приложений: сначала учётные записи, затем CRATES (core), потом остальное.
        def app_sort_key(entry):
            label = entry.get("app_label") or ""
            if label == "auth":
                return (0, "")
            if label == "core":
                return (1, "")
            return (2, entry.get("name") or "")

        app_list.sort(key=app_sort_key)
        return app_list


crates_admin_site = CratesAdminSite(name="admin")
