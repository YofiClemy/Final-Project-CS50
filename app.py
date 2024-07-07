from flask import Flask, redirect, render_template, session, request
from functools import wraps
from flask_session import Session
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
from datetime import datetime, timedelta
import base64

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key_here'

app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

def login_required(f):
    """
    Decorate routes to require login.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("login")
        return f(*args, **kwargs)
    return decorated_function

def get_db_connection():
    con = sqlite3.connect('database.db')
    con.row_factory = sqlite3.Row
    return con

@app.route("/")
def index():
    return render_template("main.html")

@app.route('/login', methods=['POST','GET'])
def login():
    session.clear()
    if request.method == "POST":
        form_type = request.form.get('form_type')
        if form_type == 'login':
            username = request.form.get('username')
            password = request.form.get('password')

            con = get_db_connection()
            user = con.execute('SELECT * FROM Users WHERE username = ?', (username,)).fetchone()
            con.close()
            
            if user and check_password_hash(user['hashed_password'], password):
                session["user_id"] = user['user_id']
                return redirect("/album")
            else:
                return render_template("login.html", error="Invalid username or password")
    return render_template("login.html")



@app.route('/register', methods=['POST','GET'])
def register():
    if request.method == "POST":
        form_type = request.form.get('form_type')
        if form_type == 'register':
            username = request.form.get('username')
            password = request.form.get('password')
            confirm_password = request.form.get('confirm_password')
            
            if password != confirm_password:
                return render_template("login.html", error="Passwords do not match")
            
            hashed_password = generate_password_hash(password)
            
            con = get_db_connection()
            try:
                con.execute('INSERT INTO Users (username, hashed_password) VALUES (?, ?)',
                             (username, hashed_password))
                con.commit()
                user = con.execute('SELECT * FROM Users WHERE username = ?', (username,)).fetchone()
                session["user_id"] = user['user_id']
                con.close()
                return redirect("/album")
            except sqlite3.IntegrityError:
                con.close()
                return render_template("login.html", error="Username already exists")
    return render_template("login.html")

@app.route('/add_plant')
def add_plant():
    return render_template('add_plant.html')

@app.route('/album')
@login_required
def my_plants():

    user_id = session['user_id']
    con = get_db_connection()
    cur = con.cursor()

    cur.execute('''
        SELECT id_plant, name, photo, room, added, watered, winterval
        FROM Plants
        WHERE user_id = ?
    ''', (user_id,))

    plants_data = cur.fetchall()
    con.close()

    plants = []
    for plant in plants_data:
        added_date = datetime.strptime(plant['added'], '%Y-%m-%d').date()
        
        if plant['watered']:
            watered_date = datetime.strptime(plant['watered'], '%Y-%m-%d').date()
            next_watering = watered_date + timedelta(days=plant['winterval'])
        else:
            watered_date = None
            next_watering = added_date + timedelta(days=plant['winterval'])

        photo_b64 = base64.b64encode(plant['photo']).decode('utf-8') if plant['photo'] else None

        plants.append({
            'id_plant': plant['id_plant'],
            'name': plant['name'],
            'photo': photo_b64,
            'room': plant['room'],
            'added': added_date.strftime('%Y-%m-%d'),
            'watered': watered_date.strftime('%Y-%m-%d') if watered_date else None,
            'next_watering': next_watering.strftime('%Y-%m-%d') if next_watering else None
        })
    return render_template('my_plants.html', plants=plants)

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")