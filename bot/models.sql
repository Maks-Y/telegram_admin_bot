-- Настройки
CREATE TABLE IF NOT EXISTS settings (
  key   TEXT PRIMARY KEY,
  value TEXT
);

-- Черновики
-- content_type: text|photo|video|document|album
CREATE TABLE IF NOT EXISTS drafts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  author_id INTEGER NOT NULL,
  channel_id INTEGER,                          -- куда планируем публиковать (если нужен локальный override)
  content_type TEXT NOT NULL,
  text TEXT,                                   -- текст или подпись для медиа/альбома (caption для 1-го элемента)
  parse_mode TEXT DEFAULT 'HTML',
  disable_web_page_preview INTEGER DEFAULT 1,  -- 1:true / 0:false
  silent INTEGER DEFAULT 0,                    -- 1:true / 0:false
  media_file_id TEXT,                          -- для одиночных медиа
  media_url TEXT,                              -- исходный URL медиа (если нет file_id)
  album_json TEXT,                             -- JSON: [{type:'photo'|'video'|'document', file_id:'...'}]
  buttons_json TEXT,                           -- JSON: [{text:'...', url:'...'}]
  source_url TEXT,                             -- ссылка на оригинал (для RSS)
  hash TEXT,                                   -- уникальный хеш черновика
  status TEXT NOT NULL DEFAULT 'draft',        -- draft|queued|published|deleted
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  published_at TIMESTAMP
);

-- Расписание (простая одноразовая публикация)
CREATE TABLE IF NOT EXISTS schedules (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  draft_id INTEGER NOT NULL,
  run_at TIMESTAMP NOT NULL,                   -- Europe/Berlin
  status TEXT NOT NULL DEFAULT 'pending',      -- pending|done|canceled
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (draft_id) REFERENCES drafts(id) ON DELETE CASCADE
);


-- RSS источники (если нет, создадим)
CREATE TABLE IF NOT EXISTS feeds (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  url TEXT UNIQUE NOT NULL,
  title TEXT,
  active INTEGER NOT NULL DEFAULT 1,
  tags TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Сырые записи из RSS
CREATE TABLE IF NOT EXISTS feed_entries (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  feed_id INTEGER NOT NULL,
  guid TEXT,
  url TEXT,
  hash TEXT,
  title TEXT,
  published_at TIMESTAMP,
  fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  content_html TEXT,
  content_text TEXT,
  image_url TEXT,
  FOREIGN KEY (feed_id) REFERENCES feeds(id) ON DELETE CASCADE
);

-- Метаданные для черновиков (происхождение, дубли, привязка к RSS)
CREATE TABLE IF NOT EXISTS draft_meta (
  draft_id INTEGER PRIMARY KEY,
  origin TEXT,               -- 'forwarded'|'rss_ai'|'manual'
  feed_id INTEGER,
  entry_id INTEGER,
  source_url TEXT,
  simhash INTEGER,
  ai_model TEXT,
  ai_version TEXT,
  ai_score REAL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (draft_id) REFERENCES drafts(id) ON DELETE CASCADE
);

-- Сообщения публикаций (для архива)
CREATE TABLE IF NOT EXISTS published_msgs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  draft_id INTEGER NOT NULL,
  chat_id INTEGER NOT NULL,
  message_id INTEGER NOT NULL,
  published_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (draft_id) REFERENCES drafts(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_entries_feed ON feed_entries(feed_id, published_at DESC);
CREATE INDEX IF NOT EXISTS idx_drafts_status_created ON drafts(status, created_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS uq_drafts_hash ON drafts(hash);
CREATE INDEX IF NOT EXISTS idx_draft_meta_simhash ON draft_meta(simhash);

-- Уникальность по (feed_id, hash)
CREATE UNIQUE INDEX IF NOT EXISTS uq_feed_entries_hash ON feed_entries(feed_id, hash);
CREATE INDEX IF NOT EXISTS idx_feed_entries_guid ON feed_entries(guid);
