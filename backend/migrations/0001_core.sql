-- 0001_core.sql
-- Core entities: users, settings, music catalog cache, reviews, comments, reactions.

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    email TEXT UNIQUE,
    password_hash TEXT,
    nickname TEXT NOT NULL UNIQUE,
    avatar_url TEXT,
    bio TEXT,
    is_premium INTEGER NOT NULL DEFAULT 0 CHECK (is_premium IN (0, 1)),
    premium_until TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    last_seen_at TEXT
);

CREATE TABLE IF NOT EXISTS user_settings (
    user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    favorite_genres TEXT,
    ui_theme_color TEXT,
    ui_background TEXT,
    ui_progress_color TEXT,
    player_preset TEXT
);

CREATE TABLE IF NOT EXISTS user_roles (
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    PRIMARY KEY (user_id, role)
);

CREATE TABLE IF NOT EXISTS music_items (
    id INTEGER PRIMARY KEY,
    provider TEXT NOT NULL,
    external_id TEXT NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('track', 'album', 'playlist')),
    title TEXT NOT NULL,
    artist TEXT,
    artwork_url TEXT,
    duration_sec INTEGER,
    playback_ref TEXT,
    meta_json TEXT,
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (provider, external_id, kind)
);

CREATE TABLE IF NOT EXISTS collections (
    id INTEGER PRIMARY KEY,
    owner_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    description TEXT,
    is_public INTEGER NOT NULL DEFAULT 1 CHECK (is_public IN (0, 1)),
    cover_url TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    deleted_at TEXT
);

CREATE TABLE IF NOT EXISTS reviews (
    id INTEGER PRIMARY KEY,
    author_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    music_item_id INTEGER REFERENCES music_items(id) ON DELETE SET NULL,
    collection_id INTEGER REFERENCES collections(id) ON DELETE SET NULL,
    text TEXT NOT NULL,
    spoiler INTEGER NOT NULL DEFAULT 0 CHECK (spoiler IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    deleted_at TEXT,
    CHECK (
        (music_item_id IS NOT NULL AND collection_id IS NULL)
        OR (music_item_id IS NULL AND collection_id IS NOT NULL)
    )
);

CREATE TABLE IF NOT EXISTS comments (
    id INTEGER PRIMARY KEY,
    review_id INTEGER NOT NULL REFERENCES reviews(id) ON DELETE CASCADE,
    author_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    parent_comment_id INTEGER REFERENCES comments(id) ON DELETE CASCADE,
    text TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    deleted_at TEXT
);

CREATE TABLE IF NOT EXISTS reactions (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    target_type TEXT NOT NULL CHECK (target_type IN ('review', 'comment', 'music_item')),
    target_id INTEGER NOT NULL,
    value INTEGER NOT NULL CHECK (value IN (-1, 1)),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (user_id, target_type, target_id)
);

CREATE INDEX IF NOT EXISTS idx_reviews_created_at ON reviews(created_at);
CREATE INDEX IF NOT EXISTS idx_reviews_author_created_at ON reviews(author_id, created_at);
CREATE INDEX IF NOT EXISTS idx_comments_review_created_at ON comments(review_id, created_at);
CREATE INDEX IF NOT EXISTS idx_reactions_target ON reactions(target_type, target_id);
CREATE INDEX IF NOT EXISTS idx_reactions_user ON reactions(user_id);
CREATE INDEX IF NOT EXISTS idx_music_items_title ON music_items(title);
CREATE INDEX IF NOT EXISTS idx_music_items_artist ON music_items(artist);

