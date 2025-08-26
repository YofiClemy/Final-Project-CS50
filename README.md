# PlantWeb

Track your houseplants, store photos, and never miss a watering. Built with **Flask** and **SQLite** for a CS50 final project.

- Auth (register/login) with hashed passwords and server-side sessions
- Add plants with either an uploaded image or a stock image from the built-in gallery
- Due-date logic: next watering is computed from the last watering or the added date
- Clean Bootstrap UI with an empty state, badges, and a simple “Water now” action

> **Live demo:** _TBD_ → add your deployed URL here (Render/Railway/Fly.io).  
> **Docs site:** optional GitHub Pages landing in `index.html`.

---

## Screenshots

> Put images in `assets/` and link them here, or remove this section.

- Login  
  `assets/login.jpg`
- Album  
  `assets/album.jpg`
- Add Plant  
  `assets/add.jpg`

---

## Features

- User accounts (username + password, hashed with Werkzeug)
- Plant album: name, room, when added, last watered, interval
- Image options:
  - Upload a small image (2 MB cap, MIME validated)
  - Choose from a stock library in `static/stock/` (no upload required)
- Due badges:
  - Red = overdue, Yellow = due soon, Green = fine
  - Green = OK
- One-click “Water now” updates last-watered date to today

---

## Tech Stack

- **Backend:** Python 3.11+, Flask 3
- **DB:** SQLite (file at `instance/database.db`)
- **Sessions:** Flask-Session (filesystem)
- **Frontend:** Jinja templates, Bootstrap 5
- **WSGI:** gunicorn (for deployment)

---

## Project Structure

```
.
├── app.py
├── schema.sql
├── requirements.txt
├── gunicorn_config.py            # used in deployment
├── templates/
│   ├── layout.html
│   ├── login.html
│   ├── main.html
│   ├── add_plant.html
│   └── album.html
├── static/
│   ├── logo.png
│   ├── default_plant.jpg
│   ├── empty-plants.svg
│   └── stock/                    # put stock images here (e.g., cactus.jpg)
└── instance/                     # created at runtime (ignored by git)
    └── database.db              # SQLite DB (auto-created)
```

> `instance/` is created automatically and must be **gitignored**.

---

## Quickstart (Local)

Requirements: Python 3.11+

```bash
# 1) Create a venv
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate

# 2) Install deps
pip install -r requirements.txt

# 3) Set env vars (at least SECRET_KEY)
export SECRET_KEY="change-me"

# 4) Run
flask --app app run  # http://127.0.0.1:5000
```

The database is stored at `instance/database.db`. The schema is **auto-applied** at startup.  
If you prefer manual init:

```bash
sqlite3 instance/database.db < schema.sql
```

---

## Configuration

Environment variables:

- `SECRET_KEY` (required): random string used to sign sessions
- `DATABASE_FILE` (optional): absolute path to a custom SQLite file. If unset, defaults to `instance/database.db`.

Runtime config (in `app.py`):

- `MAX_CONTENT_LENGTH = 2 * 1024 * 1024` to cap uploads at 2 MB
- Session cookie settings (HTTPOnly, SameSite, etc.)

---

## Stock Image Library

1. Put JPG/PNG files into `static/stock/` (keep them small, e.g., ≤ 200 KB).
2. Map keys to filenames in `app.py`:

```python
STOCK_IMAGES = {
    "cactus": "stock/cactus.jpg",
    "ficus": "stock/ficus.jpg",
    "monstera": "stock/monstera.jpg",
    "succulent": "stock/succulent.jpg",
    "snake_plant": "stock/snake_plant.jpg",
    "pothos": "stock/pothos.jpg",
}
```

On the Add Plant page, switch “Image source” between **Upload** and **Choose from image library**.

---

## Commands you may want

Rebuild venv:
```bash
rm -rf .venv && python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
```

See tables:
```bash
sqlite3 instance/database.db ".tables"
```

Dump schema:
```bash
sqlite3 instance/database.db ".schema Plants"
```

---

## Deployment

You need a real Python host for the Flask app. GitHub Pages is **static only**.  
Use one of the following:

### Render (clicky UI)

- Create a Web Service from this GitHub repo.
- **Build Command:** `pip install -r requirements.txt`
- **Start Command:** `gunicorn -c gunicorn_config.py app:app`
- Add environment variables:
  - `SECRET_KEY=change-me`
  - (optional) `DATABASE_FILE=/opt/render/project/src/instance/database.db`
- Make sure `gunicorn` is in `requirements.txt`.

### Railway (quick)

- Create a new service from repo.
- Service variables:
  - `SECRET_KEY=change-me`
- **Start Command:** `gunicorn -c gunicorn_config.py app:app`

### Fly.io (CLI)

```bash
flyctl launch --now    # accept defaults, choose a region
flyctl secrets set SECRET_KEY=change-me
flyctl deploy
```

> Add a `Procfile` if you want Heroku-like parity:
> ```
> web: gunicorn -c gunicorn_config.py app:app
> ```

After deployment, put the URL in this README and on your GitHub Pages landing.

---

## Security Notes

- Passwords are hashed; never store plaintext.
- Server-side sessions live on disk; `instance/` must not be tracked in git.
- Upload validation: format + size checked. Consider CSRF tokens if you keep it public.

---

## CS50 “Distinctiveness and Complexity”

- Auth with hashed passwords and server-side session storage
- BLOB uploads plus alternative stock library with explicit whitelist
- Auto DB bootstrap and lightweight migrations on startup
- Computed scheduling with status badges
- Clean Bootstrap UI and a minimal deployment config for a real host

---

## License

MIT — see `LICENSE` (or choose a license you prefer).
