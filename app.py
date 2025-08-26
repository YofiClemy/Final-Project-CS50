from flask import Flask, g, redirect, render_template, session, request, url_for, abort
from functools import wraps
from flask_session import Session
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
from datetime import date, datetime, timedelta
import base64
import os
from PIL import Image, UnidentifiedImageError
from io import BytesIO
import secrets, hmac

# ---------- Stock image whitelist ----------
STOCK_IMAGES = {
    "cactus": "stock/cactus.jpg",
    "ficus": "stock/ficus.jpg",
    "monstera": "stock/monstera.jpg",
    "succulent": "stock/succulent.jpg",
    "snake_plant": "stock/snake_plant.jpg",
    "pothos": "stock/pothos.jpg",
}

# ---------- App & config ----------
app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", os.urandom(24))
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=7)

# 2 MB upload cap
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024

# Session cookie hygiene
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE = True if os.environ.get("RENDER") else False
)

# Ensure instance folder exists (db, sessions, etc.)
os.makedirs(app.instance_path, exist_ok=True)

# Server-side sessions (filesystem)
app.config["SESSION_TYPE"] = "filesystem"
app.config["SESSION_FILE_DIR"] = os.path.join(app.instance_path, "flask_session")
os.makedirs(app.config["SESSION_FILE_DIR"], exist_ok=True)
Session(app)


SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}

@app.before_request
def ensure_csrf_token():
    # give every session a token
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_urlsafe(32)

# csrf protection
@app.before_request
def csrf_protect():
    if request.method in SAFE_METHODS:
        return
    # allow static files etc.
    if request.endpoint in (None, "static",):
        return
    token_session = session.get("csrf_token")
    token_form = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token")
    if not token_session or not token_form or not hmac.compare_digest(token_session, token_form):
        abort(400)  # Bad Request

# SQLite DB path (defaults to instance/database.db)
DB_PATH = os.environ.get("DATABASE_FILE") or os.path.join(app.instance_path, "database.db")

# ---------- DB helpers ----------
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db

@app.teardown_appcontext
def close_db(exc):  # type: ignore
    db = g.pop("db", None)
    if db is not None:
        db.close()

def _table_exists(con, name: str) -> bool:
    return con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone() is not None

def _column_exists(con, table: str, column: str) -> bool:
    con.row_factory = sqlite3.Row
    cols = [r["name"] for r in con.execute(f"PRAGMA table_info('{table}')")]
    return column in cols

def ensure_schema_bootstrap():
    """Create tables and run tiny migrations at import time (Flask 3 safe)."""
    con = sqlite3.connect(DB_PATH)
    try:
        con.execute("PRAGMA foreign_keys = ON")

        if not _table_exists(con, "Users"):
            con.executescript("""
            PRAGMA foreign_keys = ON;
            CREATE TABLE IF NOT EXISTS Users (
              user_id INTEGER PRIMARY KEY,
              username TEXT NOT NULL UNIQUE COLLATE NOCASE,
              hashed_password TEXT NOT NULL
            );
            """)

        if not _table_exists(con, "Plants"):
            con.executescript("""
            PRAGMA foreign_keys = ON;
            CREATE TABLE IF NOT EXISTS Plants (
              id_plant   INTEGER PRIMARY KEY,
              user_id    INTEGER NOT NULL,
              email      TEXT NOT NULL UNIQUE NOCASE,
              name       TEXT NOT NULL,
              room       TEXT,
              added      TEXT NOT NULL,     -- 'YYYY-MM-DD'
              watered    TEXT,              -- nullable
              winterval  INTEGER NOT NULL DEFAULT 7 CHECK (winterval > 0),
              photo      BLOB,              -- optional upload
              photo_path TEXT,              -- optional stock image path
              photo_source TEXT DEFAULT 'upload',
              photo_mime TEXT,              -- MIME for data: URI
              FOREIGN KEY (user_id) REFERENCES Users(user_id)
            );
            """)
            con.execute("CREATE INDEX IF NOT EXISTS idx_plants_user ON Plants(user_id)")
        else:
            if not _column_exists(con, "Plants", "photo_path"):
                con.execute("ALTER TABLE Plants ADD COLUMN photo_path TEXT")
            if not _column_exists(con, "Plants", "photo_source"):
                con.execute("ALTER TABLE Plants ADD COLUMN photo_source TEXT DEFAULT 'upload'")
            if not _column_exists(con, "Plants", "photo_mime"):
                con.execute("ALTER TABLE Plants ADD COLUMN photo_mime TEXT")
            con.execute("CREATE INDEX IF NOT EXISTS idx_plants_user ON Plants(user_id)")

        con.commit()
    finally:
        con.close()

# Run schema bootstrap now (no deprecated hooks)
ensure_schema_bootstrap()

# ---------- Small helpers ----------
def read_interval(value, default=7, lo=1, hi=365):
    try:
        n = int(value)
    except (TypeError, ValueError):
        n = default
    return max(lo, min(n, hi))

def make_thumb_and_mime(data: bytes, max_px=800):
    """
    Normalize arbitrary image bytes to a web-friendly JPEG thumbnail.
    Returns (bytes, mime) where mime == 'image/jpeg'.
    """
    im = Image.open(BytesIO(data))
    im = im.convert("RGB")
    im.thumbnail((max_px, max_px))
    out = BytesIO()
    im.save(out, format="JPEG", quality=85)
    return out.getvalue(), "image/jpeg"

# ---------- Auth decorator ----------
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function

# ---------- Routes ----------
@app.route("/")
def index():
    return render_template("main.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    session.clear()
    if request.method == "POST":
        form_type = request.form.get("form_type")
        remember = request.form.get("remember") == "on"
        session.permanent = bool(remember)
        if form_type == "login":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")

            db = get_db()
            user = db.execute("SELECT * FROM Users WHERE username = ?", (username,)).fetchone()
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
            email = request.form.get("email","").strip()
            password = request.form.get("password", "")
            confirm_password = request.form.get("confirm_password", "")

            if not username or not password:
                return render_template("login.html", error="Username and password required")
            if password != confirm_password:
                return render_template("login.html", error="Passwords do not match")

            hashed_password = generate_password_hash(password)
            db = get_db()
            try:                
                db.execute("INSERT INTO Users (username, email, hashed_password) VALUES (?, ?, ?)",
                (username, email, hashed_password))
                db.commit()
                user = db.execute("SELECT * FROM Users WHERE username = ?", (username,)).fetchone()
                session["user_id"] = user["user_id"]
                return redirect(url_for("my_plants"))
            except sqlite3.IntegrityError:
                return render_template("login.html", error="Username already exists")
    return render_template("login.html")

@app.route("/add_plant", methods=["GET", "POST"])
@login_required
def add_plant():
    if request.method == "POST":
        name  = request.form.get("name", "").strip()
        room  = request.form.get("room", "").strip()
        added = request.form.get("added") or date.today().isoformat()

        winterval = read_interval(request.form.get("winterval", "7"))

        photo_mode   = request.form.get("photo_mode", "upload")  # 'upload' or 'stock'
        photo_bytes  = None
        photo_path   = None
        photo_source = None
        photo_mime   = None

        if not name:
            return render_template("add_plant.html", error="Name is required", stock_images=STOCK_IMAGES)

        if photo_mode == "stock":
            key = request.form.get("stock_key", "")
            if key in STOCK_IMAGES:
                photo_path = STOCK_IMAGES[key]
                photo_source = "stock"
            else:
                return render_template("add_plant.html", error="Choose a valid stock image", stock_images=STOCK_IMAGES)
        else:
            file = request.files.get("photo")
            if file and file.filename:
                data = file.read()
                if len(data) > 2_000_000:
                    return render_template("add_plant.html", error="Image too large (2 MB max)", stock_images=STOCK_IMAGES)
                try:
                    photo_bytes, photo_mime = make_thumb_and_mime(data)
                except UnidentifiedImageError:
                    return render_template("add_plant.html", error="Unsupported image format. Use JPG, PNG, GIF, or WEBP.", stock_images=STOCK_IMAGES)
                photo_source = "upload"

        db = get_db()
        db.execute(
            "INSERT INTO Plants (user_id, name, room, added, winterval, photo, photo_path, photo_source, photo_mime) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (session["user_id"], name, room, added, winterval, photo_bytes, photo_path, photo_source, photo_mime),
        )
        db.commit()
        return redirect(url_for("my_plants"))

    return render_template("add_plant.html", stock_images=STOCK_IMAGES)

@app.route("/plant/<int:plant_id>/edit", methods=["GET", "POST"])
@login_required
def edit_plant(plant_id):
    db = get_db()
    row = db.execute(
        "SELECT id_plant, name, room, added, watered, winterval, photo, photo_path, photo_source, photo_mime "
        "FROM Plants WHERE id_plant=? AND user_id=?",
        (plant_id, session["user_id"]),
    ).fetchone()
    if not row:
        return redirect(url_for("my_plants"))

    if request.method == "POST":
        name  = (request.form.get("name") or row["name"]).strip()
        room  = (request.form.get("room") or (row["room"] or "")).strip()
        added = request.form.get("added") or row["added"]

        winterval = read_interval(request.form.get("winterval", row["winterval"]))

        photo_mode   = request.form.get("photo_mode") or row["photo_source"] or "upload"
        photo_bytes  = row["photo"]
        photo_path   = row["photo_path"]
        photo_source = row["photo_source"]
        photo_mime   = row["photo_mime"]

        if photo_mode == "stock":
            key = request.form.get("stock_key", "")
            if key in STOCK_IMAGES:
                photo_path   = STOCK_IMAGES[key]
                photo_source = "stock"
                photo_bytes  = None
                photo_mime   = None
            else:
                return render_template("edit_plant.html", plant=dict(row), stock_images=STOCK_IMAGES, error="Choose a valid stock image")
        elif photo_mode == "upload":
            file = request.files.get("photo")
            if file and file.filename:
                data = file.read()
                if len(data) > 2_000_000:
                    return render_template("edit_plant.html", plant=dict(row), stock_images=STOCK_IMAGES, error="Image too large (2 MB max)")
                try:
                    photo_bytes, photo_mime = make_thumb_and_mime(data)
                except UnidentifiedImageError:
                    return render_template("edit_plant.html", plant=dict(row), stock_images=STOCK_IMAGES, error="Unsupported image format")
                photo_source = "upload"
                photo_path   = None
        # else keep existing

        db.execute(
            "UPDATE Plants SET name=?, room=?, added=?, winterval=?, photo=?, photo_path=?, photo_source=?, photo_mime=? "
            "WHERE id_plant=? AND user_id=?",
            (name, room, added, winterval, photo_bytes, photo_path, photo_source, photo_mime, plant_id, session["user_id"])
        )
        db.commit()
        return redirect(url_for("my_plants"))

    return render_template("edit_plant.html", plant=dict(row), stock_images=STOCK_IMAGES)

@app.route("/album")
@login_required
def my_plants():
    db = get_db()
    rows = db.execute(
        "SELECT id_plant, name, room, added, watered, winterval, photo, photo_path, photo_mime "
        "FROM Plants WHERE user_id=? ORDER BY name",
        (session["user_id"],),
    ).fetchall()

    today = date.today()
    plants = []
    for r in rows:
        added_date = datetime.strptime(r["added"], "%Y-%m-%d").date()
        watered_date = datetime.strptime(r["watered"], "%Y-%m-%d").date() if r["watered"] else None
        ref_date = watered_date or added_date
        next_watering = ref_date + timedelta(days=r["winterval"])
        days_left = (next_watering - today).days

        photo_b64 = base64.b64encode(r["photo"]).decode("utf-8") if r["photo"] else None
        photo_mime = (r["photo_mime"] or "image/jpeg") if photo_b64 else None

        plants.append({
            "id_plant": r["id_plant"],
            "name": r["name"],
            "room": r["room"],
            "added": added_date.strftime("%Y-%m-%d"),
            "watered": watered_date.strftime("%Y-%m-%d") if watered_date else None,
            "next_watering": next_watering.strftime("%Y-%m-%d"),
            "days_left": days_left,
            "photo": photo_b64,
            "photo_mime": photo_mime,
            "photo_path": r["photo_path"],
            "winterval": r["winterval"],
        })

    return render_template("album.html", plants=plants)

@app.route("/water/<int:plant_id>", methods=["POST"])
@login_required
def water(plant_id):
    today = date.today().isoformat()
    db = get_db()
    db.execute("UPDATE Plants SET watered=? WHERE id_plant=? AND user_id=?", (today, plant_id, session["user_id"]))
    db.commit()
    return redirect(url_for("my_plants"))

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/healthz")
def healthz():
    return {"ok": True}, 200

if __name__ == "__main__":
    # Local dev only; all routes are defined above this line
    app.run(debug=True)