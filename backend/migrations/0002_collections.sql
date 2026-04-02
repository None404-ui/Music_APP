-- 0002_collections.sql
-- User collections (items) and favorites.

CREATE TABLE IF NOT EXISTS collection_items (
    collection_id INTEGER NOT NULL REFERENCES collections(id) ON DELETE CASCADE,
    music_item_id INTEGER NOT NULL REFERENCES music_items(id) ON DELETE CASCADE,
    position INTEGER,
    added_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (collection_id, music_item_id)
);

CREATE TABLE IF NOT EXISTS favorites (
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    music_item_id INTEGER NOT NULL REFERENCES music_items(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (user_id, music_item_id)
);

CREATE INDEX IF NOT EXISTS idx_collection_items_collection_position
ON collection_items(collection_id, position);

