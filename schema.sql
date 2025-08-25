-- schema.sql
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS Users (
  user_id INTEGER PRIMARY KEY,
  username TEXT NOT NULL UNIQUE COLLATE NOCASE,
  hashed_password TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS Plants (
  id_plant INTEGER PRIMARY KEY,
  user_id  INTEGER NOT NULL,
  name     TEXT NOT NULL,
  room     TEXT,
  added    TEXT NOT NULL,    -- 'YYYY-MM-DD'
  watered  TEXT,             -- nullable
  winterval INTEGER NOT NULL DEFAULT 7 CHECK (winterval > 0),
  photo    BLOB,
  FOREIGN KEY (user_id) REFERENCES Users(user_id)
);