## Контракт API CRATES (Django + DRF)

### Базовые настройки
- **Base URL**: `http://127.0.0.1:8000`
- **Префикс API**: `/api/`
- **Аутентификация**: session-cookies (устанавливаются в `/api/auth/login/`), плюс BasicAuth включен.
- **Права по умолчанию**: для анонимных — чтение, для записи — нужна авторизация (часть ресурсов доступна только admin/staff).
- **Формат**: JSON (`application/json`)

### Общий формат ошибок
- **400**: `{"detail": "..."}`
- **403**: `{"detail": "Forbidden"}` (для некоторых endpoints)
- **401**: `{"detail": "Authentication credentials were not provided."}` (дефолт DRF)

---

## Авторизация

### POST `/api/auth/login/`
Логин через `username/password` и установка session cookie.

- **Body**:
  - `username` (string)
  - `password` (string)
- **200**: `{"detail":"ok"}`
- **400**: `{"detail":"Invalid credentials"}`

### POST `/api/auth/logout/`
Выход из сессии (нужна авторизация).

- **200**: `{"detail":"ok"}`
- **401**, если пользователь не залогинен.

---

## Профиль

### GET `/api/profile/me/`
Получить профиль текущего пользователя (при необходимости создаётся автоматически).

- **Auth**: требуется
- **200**: `Profile`

### PATCH `/api/profile/me/`
Частичное обновление профиля.

- **Auth**: требуется
- **Body**: поля, которые разрешены в `Profile` (см. схему)
- **200**: обновленный `Profile`

#### `Profile` (поля)
```json
{
  "id": 1,
  "user": 12,
  "nickname": "nick",
  "avatar_url": "https://...",
  "bio": "text",
  "is_premium": false,
  "premium_until": null,
  "favorite_genres": "rock,metal",
  "ui_theme_color": "#ff0000",
  "ui_background": "bg1",
  "ui_progress_color": "#00ff00",
  "player_preset": "{\"...\":true}",
  "created_at": "2026-03-18T12:00:00Z",
  "updated_at": "2026-03-18T12:00:00Z"
}
```

---

## Каталог музыки (кэш внешних сущностей)

### GET `/api/music-items/`
Список/поиск музыкальных объектов.

- **Query**:
  - `q` (string, optional) — поиск по `title` или `artist`
  - `provider` (string, optional)
  - `kind` (enum: `track|album|playlist`, optional)
- **200**: массив `MusicItem`

### POST `/api/music-items/`
Создать музыкальный объект (обычно заполняется админом).

- **Auth**: **admin/staff только**
- **Body**: `provider`, `external_id`, `kind`, `title`, опционально `artist`, `artwork_url`, `duration_sec`, `playback_ref`, `meta_json`
- **201**: созданный `MusicItem`
- **403**: если пользователь не staff/admin

### GET `/api/music-items/{id}/`
Получить `MusicItem`

### PATCH/PUT/DELETE `/api/music-items/{id}/`
- **Auth**: **admin/staff только** для записи

#### `MusicItem` (поля)
```json
{
  "id": 1,
  "provider": "yt",
  "external_id": "x",
  "kind": "track",
  "title": "Song",
  "artist": "Artist",
  "artwork_url": "https://...",
  "duration_sec": 235,
  "playback_ref": "uri_or_url",
  "meta_json": "{}",
  "updated_at": "2026-03-18T12:00:00Z"
}
```

---

## Подборки (плейлисты)

### GET `/api/collections/`
Список коллекций.

- **Auth**: не требуется (чтение открыто)
- **200**: массив `Collection`

### POST `/api/collections/`
Создать коллекцию.

- **Auth**: требуется
- **Body**: `title`, `description` (optional), `is_public` (optional), `cover_url` (optional)
- **201**: созданная `Collection` (владелец ставится автоматически)

### PATCH/PUT/DELETE `/api/collections/{id}/`
- **Auth**: требуется
- **Права**: редактировать/удалять может только **owner**

#### `Collection` (поля)
```json
{
  "id": 1,
  "owner": 12,
  "title": "My playlist",
  "description": "desc",
  "is_public": true,
  "cover_url": "https://...",
  "deleted_at": null,
  "created_at": "2026-03-18T12:00:00Z",
  "updated_at": "2026-03-18T12:00:00Z",
  "items": [
    {
      "id": 10,
      "collection": 1,
      "music_item": { "...": "MusicItem" },
      "position": 1,
      "added_at": "2026-03-18T12:00:00Z"
    }
  ]
}
```

---

## Рецензии

### GET `/api/reviews/`
Список рецензий.

- **Query**:
  - `q` (string, optional) — `text__icontains`
  - `author_id` (int, optional)
  - `music_item_id` (int, optional)
  - `collection_id` (int, optional)
- **200**: массив `Review`

### POST `/api/reviews/`
Создать рецензию.

- **Auth**: требуется
- **Body**:
  - `text` (string)
  - `spoiler` (bool)
  - ровно один target:
    - `music_item` (int) **или**
    - `collection` (int)
- **201**: созданная `Review` (автор ставится автоматически)

### PATCH/PUT/DELETE `/api/reviews/{id}/`
- **Auth**: требуется
- **Права**: редактировать/удалять может только **author**

#### `Review` (поля)
```json
{
  "id": 1,
  "author": 12,
  "music_item": 1,
  "collection": null,
  "text": "review text",
  "spoiler": false,
  "deleted_at": null,
  "created_at": "2026-03-18T12:00:00Z",
  "updated_at": "2026-03-18T12:00:00Z"
}
```

---

## Комментарии

### GET `/api/comments/`
Список комментариев.

- **Query**:
  - `review_id` (int, optional)
- **200**: массив `Comment`

### POST `/api/comments/`
Создать комментарий.

- **Auth**: требуется
- **Body**:
  - `review` (int)
  - `text` (string)
  - `parent` (int|null, optional)
- **201**: созданный `Comment`
- **Побочный эффект**: создаётся уведомление автору review, если он отличается от текущего пользователя

### PATCH/PUT/DELETE `/api/comments/{id}/`
- **Auth**: требуется
- **Права**: редактировать/удалять может только **author**

---

## Реакции (лайк/дизлайк)

### GET `/api/reactions/`
Список реакций **текущего пользователя** (чужие реакции не возвращаются).

- **Auth**: требуется
- **Query**:
  - `target_type` (enum: `review|comment|music_item`, optional)
  - `target_id` (int, optional)
- **200**: массив `Reaction`

### POST `/api/reactions/`
Создать реакцию.

- **Auth**: требуется
- **Body**:
  - `target_type` (enum: `review|comment|music_item`)
  - `target_id` (int)
  - `value` (int: `1` или `-1`)
- **201**: созданная `Reaction`
- **Побочный эффект**: уведомление владельцу объекта (review/comment), если не сам себе

### PATCH `/api/reactions/{id}/`
Обновить реакцию (поле `value`).
- **Side-effect**: повторно создаёт уведомление аналогично create

### DELETE `/api/reactions/{id}/`
Удалить реакцию.

---

## Избранное

### GET `/api/favorites/`
Список избранного **текущего пользователя**.

- **Auth**: требуется
- **200**: массив `Favorite`

### POST `/api/favorites/`
Добавить в избранное.

- **Auth**: требуется
- **Body**: `music_item` (int)
- **201**: созданный `Favorite`

### DELETE `/api/favorites/{id}/`
Удалить из избранного.

---

## Подписки (друзья)

### GET `/api/follows/`
Получить подписки.

- **Auth**: требуется
- **Query**:
  - `user_id` (int, optional)
  - `kind`:
    - если `kind=followers` — вернуть всех, кто подписан на `user_id`
    - иначе — вернуть всех, на кого подписан `user_id`

**Если `user_id` не передан**: возвращаются подписки текущего пользователя **(following)**.

### POST `/api/follows/`
Подписаться.

- **Auth**: требуется
- **Body**: `followee` (int)
- **201**: `Follow` (follower = текущий пользователь)
- **Побочный эффект**: создаётся уведомление followee

### DELETE `/api/follows/{id}/`
Отписаться (удаление записи Follow).

---

## Лента

### GET `/api/feed/`
Рецензии пользователей, на которых вы подписаны.

- **Auth**: требуется
- **200**: массив `Review`

---

## Уведомления

### GET `/api/notifications/`
Уведомления текущего пользователя.

- **Auth**: требуется
- **Query**:
  - `is_read` (`0|1`, optional)
- **200**: массив `Notification`

### POST `/api/notifications/mark_read/`
Отметить набор уведомлений как прочитанные (bulk).

- **Auth**: требуется
- **Body**:
  - `ids` (массив int)
- **200**: `{"detail":"ok"}`

---

## Жалобы (reports)

### GET `/api/reports/`
Список жалоб.

- **Auth**: требуется
- **Права**:
  - обычный пользователь: только свои
  - staff/admin: все

### POST `/api/reports/`
Создать жалобу.

- **Auth**: требуется
- **Body**:
  - `target_type` (enum: `review|comment|user|collection`)
  - `target_id` (int)
  - `reason` (string)
- **201**: `Report` (reporter = текущий пользователь)

### PATCH/PUT `/api/reports/{id}/`
- **Auth**: требуется
- **Права**: staff/admin только (иначе 403)

---

## Чат (диалоги и сообщения)

### GET `/api/conversations/`
Список диалогов, в которых участвует текущий пользователь.

- **Auth**: требуется
- **200**: массив `Conversation`

### POST `/api/conversations/`
Создать диалог.

- **Auth**: требуется
- **Body**:
  - `participant_ids` (массив int) — остальные пользователи в диалоге (без текущего пользователя)
- **201**: `Conversation`
- **В диалог всегда включается текущий пользователь**.

Ответ `Conversation` содержит `participants` — массив user_id участников.

### GET `/api/conversations/{id}/messages/`
Получить сообщения диалога (только если вы участник).

- **Auth**: требуется
- **200**: массив `Message`
- **Если вы не участник диалога**: вернётся **404** (так как queryset ограничен участниками)

### POST `/api/conversations/{id}/messages/`
Отправить сообщение.

- **Auth**: требуется
- **Body**:
  - `text` (string, обязательное)
- **201**: созданное `Message`

#### `Message` (поля)
```json
{
  "id": 1,
  "conversation": 2,
  "author": 12,
  "text": "Привет!",
  "created_at": "2026-03-18T12:00:00Z"
}
```

