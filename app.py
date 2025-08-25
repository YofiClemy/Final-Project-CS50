from flask import Flask, g, redirect, render_template, session, request, url_for
from functools import wraps
from flask_session import Session
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
from datetime import date, datetime, timedelta
import base64
import os

# --- App & config ---
app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", os.urandom(24))

# Ensure instance folder exists (for session files, etc.)
os.makedirs(app.instance_path, exist_ok=True)

# Server-side sessions (filesystem)
app.config["SESSION_TYPE"] = "filesystem"
app.config["SESSION_FILE_DIR"] = os.path.join(app.instance_path, "flask_session")
os.makedirs(app.config["SESSION_FILE_DIR"], exist_ok=True)
Session(app)

DB_PATH = os.environ.get("DATABASE_FILE") or os.path.join(app.instance_path, "database.db")

# --- DB helpers (single source of truth) ---
def get_db():
    """Return a per-request SQLite connection with rows as dicts."""
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db

SCHEMA_PATH = os.path.join(app.root_path, "schema.sql")

def ensure_schema():
    db = get_db()
    exists = db.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='Users'"
    ).fetchone()
    if not exists:
        # load schema from file (fallback to inline if missing)
        if os.path.exists(SCHEMA_PATH):
            with open(SCHEMA_PATH, encoding="utf-8") as f:
                db.executescript(f.read())
        else:
            db.executescript("""
            PRAGMA foreign_keys = ON;
            CREATE TABLE IF NOT EXISTS Users(
              user_id INTEGER PRIMARY KEY,
              username TEXT NOT NULL UNIQUE COLLATE NOCASE,
              hashed_password TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS Plants(
              id_plant INTEGER PRIMARY KEY,
              user_id INTEGER NOT NULL,
              name TEXT NOT NULL,
              room TEXT,
              added TEXT NOT NULL,
              watered TEXT,
              winterval INTEGER NOT NULL DEFAULT 7 CHECK (winterval > 0),
              photo BLOB,
              FOREIGN KEY (user_id) REFERENCES Users(user_id)
            );
            """)
        db.commit()

@app.before_first_request
def _init_db():
    ensure_schema()

@app.teardown_appcontext
def close_db(exc):
    """Close connection at the end of the request."""
    db = g.pop("db", None)
    if db is not None:
        db.close()

# --- Auth decorator ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function

# --- Util for due date ---
def next_due_from(row):
    """Compute next watering date from a DB row (sqlite3.Row)."""
    ref = row["watered"] or row["added"]  # 'YYYY-MM-DD'
    y, m, d = map(int, ref.split("-"))
    return date(y, m, d) + timedelta(days=row["winterval"])

# --- Routes ---
@app.route("/")
def index():
    return render_template("main.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    session.clear()
    if request.method == "POST":
        form_type = request.form.get("form_type")
        if form_type == "login":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")

            db = get_db()
            user = db.execute(
                "SELECT * FROM Users WHERE username = ?", (username,)
            ).fetchone()

            if user and check_password_hash(user["hashed_password"], password):
                session["user_id"] = user["user_id"]
                return redirect(url_for("my_plants"))
            return render_template("login.html", error="Invalid username or password")
    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        form_type = request.form.get("form_type")
        if form_type == "register":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            confirm_password = request.form.get("confirm_password", "")

            if not username or not password:
                return render_template("login.html", error="Username and password required")
            if password != confirm_password:
                return render_template("login.html", error="Passwords do not match")

            hashed_password = generate_password_hash(password)

            db = get_db()
            try:
                db.execute(
                    "INSERT INTO Users (username, hashed_password) VALUES (?, ?)",
                    (username, hashed_password),
                )
                db.commit()
                user = db.execute(
                    "SELECT * FROM Users WHERE username = ?", (username,)
                ).fetchone()
                session["user_id"] = user["user_id"]
                return redirect(url_for("my_plants"))
            except sqlite3.IntegrityError:
                return render_template("login.html", error="Username already exists")
    return render_template("login.html")

@app.route("/add_plant", methods=["GET", "POST"])
@login_required
def add_plant():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        room = request.form.get("room", "").strip()
        added = request.form.get("added") or date.today().isoformat()  # YYYY-MM-DD
        winterval = int(request.form.get("winterval", 7))
        file = request.files.get("photo")
        photo_bytes = file.read() if file and file.filename else None

        if not name:
            return render_template("add_plant.html", error="Name is required")

        db = get_db()
        db.execute(
            "INSERT INTO Plants (user_id, name, room, added, winterval, photo) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (session["user_id"], name, room, added, winterval, photo_bytes),
        )
        db.commit()
        return redirect(url_for("my_plants"))
    return render_template("add_plant.html")

@app.route("/album")
@login_required
def my_plants():
    db = get_db()
    rows = db.execute(
        "SELECT id_plant, name, photo, room, added, watered, winterval "
        "FROM Plants WHERE user_id = ? ORDER BY name",
        (session["user_id"],),
    ).fetchall()

    today = date.today()
    plants = []
    for r in rows:
        # Parse dates stored as 'YYYY-MM-DD'
        added_date = datetime.strptime(r["added"], "%Y-%m-%d").date()
        if r["watered"]:
            watered_date = datetime.strptime(r["watered"], "%Y-%m-%d").date()
        else:
            watered_date = None

        # Compute next watering
        ref_date = watered_date or added_date
        next_watering = ref_date + timedelta(days=r["winterval"])
        days_left = (next_watering - today).days

        photo_b64 = base64.b64encode(r["photo"]).decode("utf-8") if r["photo"] else None

        plants.append({
            "id_plant": r["id_plant"],
            "name": r["name"],
            "photo": photo_b64,
            "room": r["room"],
            "added": added_date.strftime("%Y-%m-%d"),
            "watered": watered_date.strftime("%Y-%m-%d") if watered_date else None,
            "next_watering": next_watering.strftime("%Y-%m-%d"),
            "days_left": days_left,
        })

    return render_template("my_plants.html", plants=plants)

@app.route("/water/<int:plant_id>", methods=["POST"])
@login_required
def water(plant_id):
    today = date.today().isoformat()
    db = get_db()
    db.execute(
        "UPDATE Plants SET watered=? WHERE id_plant=? AND user_id=?",
        (today, plant_id, session["user_id"]),
    )
    db.commit()
    return redirect(url_for("my_plants"))

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# Optional: quick health check route for deployment
@app.route("/healthz")
def healthz():
    return {"ok": True}, 200

if __name__ == "__main__":
    # For local dev only
    app.run(debug=True)