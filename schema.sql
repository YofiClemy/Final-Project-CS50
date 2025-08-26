PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS Users (
  user_id INTEGER PRIMARY KEY,
  email TEXT,
  username TEXT NOT NULL UNIQUE COLLATE NOCASE,
  hashed_password TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email ON Users(email);

CREATE TABLE IF NOT EXISTS Plants (
  id_plant   INTEGER PRIMARY KEY,
  user_id    INTEGER NOT NULL,
  name       TEXT NOT NULL,
  room       TEXT,
  added      TEXT NOT NULL,        -- 'YYYY-MM-DD'
  watered    TEXT,                 -- nullable
  winterval  INTEGER NOT NULL DEFAULT 7 CHECK (winterval > 0),
  photo      BLOB,                 -- optional upload
  photo_path TEXT,                 -- optional stock image path
  photo_source TEXT DEFAULT 'upload',
  photo_mime TEXT,
  FOREIGN KEY (user_id) REFERENCES Users(user_id)
);

CREATE INDEX IF NOT EXISTS idx_plants_user ON Plants(user_id);