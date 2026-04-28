"""Локализация: русский по умолчанию, английский через каталог строк."""

from __future__ import annotations

from ui import locale_settings

_EN: dict[str, str] = {
    "Нажмите, чтобы выбрать фото профиля": "Click to choose profile photo",
    "Пользователь": "User",
    "Выйти из аккаунта": "Log out",
    "АККАУНТ": "ACCOUNT",
    "Имя пользователя": "Username",
    "Электронная почта": "Email",
    "Сменить пароль": "Change password",
    "ИНТЕРФЕЙС": "INTERFACE",
    "Тёмная тема": "Dark theme",
    "Язык": "Language",
    "ВОСПРОИЗВЕДЕНИЕ": "PLAYBACK",
    "Качество звука": "Audio quality",
    "Меняет максимальную громкость: «Низкое» тише, «Высокое» — полный уровень ползунка.": (
        "Sets the maximum volume: “Low” is quieter, “High” is the full slider range."
    ),
    "Автовоспроизведение": "Autoplay",
    "Нормализация громкости": "Volume normalization",
    "Изображение для аватара": "Profile image",
    "Изображения (*.png *.jpg *.jpeg *.webp *.bmp);;Все файлы (*.*)": (
        "Images (*.png *.jpg *.jpeg *.webp *.bmp);;All files (*.*)"
    ),
    "Авто": "Auto",
    "Высокое": "High",
    "Среднее": "Medium",
    "Низкое": "Low",
    "Русский": "Russian",
    "English": "English",
    "При смене языка главное окно пересоздаётся (сессия сохраняется).": (
        "Changing the language recreates the main window (your session is kept)."
    ),
    "популярное": "popular",
    "рецензии": "reviews",
    "CRATES": "CRATES",
    # Плеер
    "ТРЕК": "TRACK",
    "ИМЯ АЛЬБОМА": "ALBUM NAME",
    "трек": "track",
    "альбом": "album",
    "плейлист": "playlist",
    "альбом:": "album:",
    "В избранное": "Add to favorites",
    "Написать рецензию": "Write a review",
    "Эквалайзер": "Equalizer",
    "ЭКВАЛАЙЗЕР": "EQUALIZER",
    "Профиль": "Profile",
    "Плоский": "Flat",
    "Усиление НЧ": "Bass boost",
    "Усиление ВЧ": "Treble boost",
    "Рок": "Rock",
    "Вокал": "Vocal",
    "Электроника": "Electronic",
    "Тёплый": "Warm",
    "Свой": "Custom",
    "Ползунки: −12…+12 дБ по полосам.": "Sliders: −12…+12 dB per band.",
    "Слушателей:": "Listeners:",
    "Наслушано всего:": "Total time listened:",
    "В избранном:": "In favorites:",
    "Рецензии:": "Reviews:",
    "Счётчики и избранное — после входа в аккаунт": "Stats and favorites — sign in to use",
    "название песни": "song title",
    "исполнитель": "artist",
    "0 с": "0 s",
    " с": " s",
    " мин ": " min ",
    " мин": " min",
    " ч ": " h ",
    # Главная / популярное
    "ПОПУЛЯРНОЕ": "POPULAR",
    "АЛЬБОМЫ": "ALBUMS",
    "ИСПОЛНИТЕЛИ": "ARTISTS",
    "ТРЕКИ": "TRACKS",
    "Без названия": "Untitled",
    "Обложка не указана": "No cover image",
    " слуш.": " plays",
    "Пока нет треков в каталоге.": "No tracks in the catalog yet.",
    "Нет связи с сервером:": "Cannot reach server:",
    "Ошибка загрузки:": "Load error:",
    "Сервер ответил": "Server returned",
    # «Моё»
    "МОЁ": "MY MUSIC",
    "избранное": "favorites",
    "мои загрузки": "my uploads",
    "ИЗБРАННОЕ": "FAVORITES",
    "Не удалось загрузить избранное с сервера.": "Could not load favorites from the server.",
    "ИЗБРАННЫЕ ТРЕКИ": "FAVORITE TRACKS",
    "Пока нет. ♥ для одного трека (поиск / не из очереди альбома).": (
        "None yet. Use ♥ on a single track (search / not from an album queue)."
    ),
    "ИЗБРАННЫЕ АЛЬБОМЫ": "FAVORITE ALBUMS",
    "Пока нет. Во время воспроизведения альбома нажмите ♥.": (
        "None yet. Press ♥ while playing an album."
    ),
    "ИЗБРАННЫЕ ПЛЕЙЛИСТЫ": "FAVORITE PLAYLISTS",
    "Пока нет.": "None yet.",
    "ИЗБРАННЫЕ РЕЦЕНЗИИ": "FAVORITE REVIEWS",
    "Не удалось загрузить избранные рецензии.": "Could not load favorite reviews.",
    "Пока нет. Отмечайте понравившиеся рецензии сердцем.": (
        "None yet. Heart reviews you like."
    ),
    "загрузить трек": "upload track",
    "загрузить альбом": "upload album",
    "МОИ ТРЕКИ": "MY TRACKS",
    "Не удалось загрузить ваши треки.": "Could not load your tracks.",
    "Вы пока не загружали треки.": "You have not uploaded any tracks yet.",
    "МОИ АЛЬБОМЫ": "MY ALBUMS",
    "Не удалось загрузить ваши альбомы.": "Could not load your albums.",
    "Вы пока не загружали альбомы.": "You have not uploaded any albums yet.",
    "МОИ РЕЦЕНЗИИ": "MY REVIEWS",
    "Не удалось загрузить рецензии.": "Could not load reviews.",
    "Рецензий пока нет. Добавьте из плеера.": "No reviews yet. Add one from the player.",
    "МОИ ПОДБОРКИ": "MY COLLECTIONS",
    "Не удалось загрузить подборки.": "Could not load collections.",
    "Подборок пока нет.": "No collections yet.",
    "Альбом": "Album",
    "Плейлист": "Playlist",
    "Рецензия": "Review",
    "Подборка": "Collection",
    "Трек": "Track",
    # Поиск
    "альбомы": "albums",
    "исполнители": "artists",
    "поиск . . . .": "search . . . .",
    "недавние треки": "recent tracks",
    "результаты": "results",
    # Main window / диалоги
    "Вы": "You",
    # Рецензии (вкладка на главной)
    "ТОП РЕЦЕНЗИЙ": "TOP REVIEWS",
    "Не удалось загрузить топ рецензий.": "Could not load the top reviews.",
    "Пока нет рецензий.": "No reviews yet.",
    # Страница артиста
    "← Назад": "← Back",
    "Не удалось загрузить страницу артиста.": "Could not load the artist page.",
    "Пользователь не найден.": "User not found.",
    "Пока нет треков.": "No tracks yet.",
    # Профиль исполнителя (из плеера / поиска)
    "← назад": "← back",
    "ПЛЕЙЛИСТЫ": "PLAYLISTS",
    "Нет треков в каталоге.": "No tracks in the catalog.",
    "загрузка…": "Loading…",
    "все треки": "all tracks",
    "свернуть": "collapse",
    "треков в каталоге:": "Tracks in catalog:",
    "Ошибка:": "Error:",
    "Ошибка воспроизведения трека": "Track playback error",
    # Смена пароля
    "Смена пароля": "Change password",
    "Текущий пароль": "Current password",
    "Новый пароль": "New password",
    "Повторите новый пароль": "Confirm new password",
    "ОТМЕНА": "CANCEL",
    "СОХРАНИТЬ": "SAVE",
    "Заполните все поля.": "Fill in all fields.",
    "Новый пароль и подтверждение не совпадают.": "New password and confirmation do not match.",
    "Пароль успешно изменён.": "Your password has been changed.",
    "Не удалось сменить пароль.": "Could not change password.",
    "Пароль не короче 6 символов.": "Password must be at least 6 characters.",
}


def tr(text: str) -> str:
    if not locale_settings.is_english():
        return text
    return _EN.get(text, text)


def track_stats_line(likes: int, listens: int) -> str:
    if locale_settings.is_english():
        return f"♥ {likes}  ·  {listens} plays"
    return f"♥ {likes}  ·  {listens} слуш."


def format_listen_total_sec(sec: int) -> str:
    if sec <= 0:
        return tr("0 с")
    if sec < 60:
        return f"{sec}{tr(' с')}"
    m, s = divmod(sec, 60)
    if m < 60:
        if s:
            return f"{m}{tr(' мин ')}{s:02d}{tr(' с')}"
        return f"{m}{tr(' мин')}"
    h, m = divmod(m, 60)
    return f"{h}{tr(' ч ')}{m}{tr(' мин')}"


def player_stats_line(listens_count: int, listen_total_sec: int, fav_count: int, reviews_count: int) -> str:
    total = format_listen_total_sec(listen_total_sec)
    return (
        f"{tr('Слушателей:')} {listens_count}  ·  {tr('Наслушано всего:')} {total}  ·  "
        f"{tr('В избранном:')} {fav_count}  ·  {tr('Рецензии:')} {reviews_count}"
    )


def music_kind_label(kind_raw: str) -> str:
    k = (kind_raw or "").strip().lower()
    mapping = {
        "track": tr("трек"),
        "album": tr("альбом"),
        "playlist": tr("плейлист"),
    }
    return mapping.get(k, kind_raw)


def volume_percent_tooltip(volume: int) -> str:
    v = max(0, min(100, int(volume)))
    if locale_settings.is_english():
        return f"Volume: {v}%"
    return f"Громкость: {v}%"
