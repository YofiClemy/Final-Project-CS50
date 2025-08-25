import sqlite3, pathlib
db = pathlib.Path("database.db")
with sqlite3.connect(db) as con:
    con.execute("PRAGMA foreign_keys = ON")
    con.executescript(open("schema.sql", encoding="utf-8").read())
print("DB initialized:", db.resolve())