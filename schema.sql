-- schema.sql
CREATE TABLE IF NOT EXISTS Users (
  user_id INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT UNIQUE NOT NULL,
  hashed_password TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS Plants (
  id_plant INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  name TEXT NOT NULL,
  room TEXT,
  added DATE NOT NULL,
  watered DATE,
  winterval INTEGER NOT NULL DEFAULT 7,
  photo BLOB,
  FOREIGN KEY (user_id) REFERENCES Users(user_id)
);