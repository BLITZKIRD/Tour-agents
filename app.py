from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import sqlite3
import os
import logging
from datetime import datetime
from functools import wraps

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-in-production'

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('tour_agency.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Инициализация базы данных
def init_db():
    conn = sqlite3.connect('tour_agency.db')
    c = conn.cursor()
    
    # Таблица пользователей
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  username TEXT UNIQUE NOT NULL,
                  email TEXT UNIQUE NOT NULL,
                  password TEXT NOT NULL,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    # Таблица туров
    c.execute('''CREATE TABLE IF NOT EXISTS tours
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  title TEXT NOT NULL,
                  description TEXT,
                  price REAL NOT NULL,
                  duration INTEGER,
                  destination TEXT,
                  image_url TEXT,
                  available INTEGER DEFAULT 1,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    # Таблица бронирований
    c.execute('''CREATE TABLE IF NOT EXISTS bookings
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER NOT NULL,
                  tour_id INTEGER NOT NULL,
                  booking_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  status TEXT DEFAULT 'pending',
                  FOREIGN KEY (user_id) REFERENCES users (id),
                  FOREIGN KEY (tour_id) REFERENCES tours (id))''')
    
    # Таблица логов
    c.execute('''CREATE TABLE IF NOT EXISTS activity_logs
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  action TEXT NOT NULL,
                  details TEXT,
                  ip_address TEXT,
                  timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    # Добавляем тестовые туры, если их нет
    c.execute('SELECT COUNT(*) FROM tours')
    if c.fetchone()[0] == 0:
        sample_tours = [
            ('Отдых в Турции', 'Прекрасный пляжный отдых на побережье Средиземного моря', 45000, 7, 'Турция', '/static/images/turkey.svg', 1),
            ('Экскурсия по Парижу', 'Романтическое путешествие в столицу Франции', 65000, 5, 'Франция', '/static/images/paris.svg', 1),
            ('Сафари в Африке', 'Незабываемое приключение в дикой природе', 120000, 10, 'Кения', '/static/images/africa.svg', 1),
            ('Горнолыжный курорт', 'Катание на лыжах в Альпах', 80000, 7, 'Швейцария', '/static/images/ski.svg', 1),
            ('Отдых на Мальдивах', 'Райские острова с кристально чистой водой', 150000, 10, 'Мальдивы', '/static/images/maldives.svg', 1),
            ('Культурный тур по Японии', 'Погружение в традиции и современность', 95000, 8, 'Япония', '/static/images/japan.svg', 1),
        ]
        c.executemany('INSERT INTO tours (title, description, price, duration, destination, image_url, available) VALUES (?, ?, ?, ?, ?, ?, ?)', sample_tours)
    
    conn.commit()
    conn.close()

# Декоратор для проверки авторизации
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Функция для логирования действий
def log_activity(user_id, action, details=None):
    ip_address = request.remote_addr
    conn = sqlite3.connect('tour_agency.db')
    c = conn.cursor()
    c.execute('INSERT INTO activity_logs (user_id, action, details, ip_address) VALUES (?, ?, ?, ?)',
              (user_id, action, details, ip_address))
    conn.commit()
    conn.close()
    logger.info(f"User {user_id}: {action} - {details}")

@app.route('/')
def index():
    conn = sqlite3.connect('tour_agency.db')
    c = conn.cursor()
    c.execute('SELECT * FROM tours WHERE available = 1 ORDER BY created_at DESC')
    tours = c.fetchall()
    conn.close()
    
    tours_list = []
    for tour in tours:
        tours_list.append({
            'id': tour[0],
            'title': tour[1],
            'description': tour[2],
            'price': tour[3],
            'duration': tour[4],
            'destination': tour[5],
            'image_url': tour[6]
        })
    
    return render_template('index.html', tours=tours_list, user=session.get('username'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        
        if password != confirm_password:
            flash('Пароли не совпадают', 'error')
            return render_template('register.html')
        
        conn = sqlite3.connect('tour_agency.db')
        c = conn.cursor()
        
        try:
            hashed_password = generate_password_hash(password)
            c.execute('INSERT INTO users (username, email, password) VALUES (?, ?, ?)',
                     (username, email, hashed_password))
            conn.commit()
            user_id = c.lastrowid
            conn.close()
            
            log_activity(user_id, 'REGISTER', f'User {username} registered')
            flash('Регистрация успешна! Войдите в систему.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            conn.close()
            flash('Пользователь с таким именем или email уже существует', 'error')
            return render_template('register.html')
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = sqlite3.connect('tour_agency.db')
        c = conn.cursor()
        c.execute('SELECT id, username, password FROM users WHERE username = ?', (username,))
        user = c.fetchone()
        conn.close()
        
        if user and check_password_hash(user[2], password):
            session['user_id'] = user[0]
            session['username'] = user[1]
            log_activity(user[0], 'LOGIN', f'User {username} logged in')
            flash('Вы успешно вошли в систему!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Неверное имя пользователя или пароль', 'error')
            return render_template('login.html')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    user_id = session.get('user_id')
    username = session.get('username')
    log_activity(user_id, 'LOGOUT', f'User {username} logged out')
    session.clear()
    flash('Вы вышли из системы', 'info')
    return redirect(url_for('index'))

@app.route('/tours')
def tours():
    conn = sqlite3.connect('tour_agency.db')
    c = conn.cursor()
    c.execute('SELECT * FROM tours WHERE available = 1 ORDER BY price')
    tours = c.fetchall()
    conn.close()
    
    tours_list = []
    for tour in tours:
        tours_list.append({
            'id': tour[0],
            'title': tour[1],
            'description': tour[2],
            'price': tour[3],
            'duration': tour[4],
            'destination': tour[5],
            'image_url': tour[6]
        })
    
    return render_template('tours.html', tours=tours_list, user=session.get('username'))

@app.route('/tour/<int:tour_id>')
def tour_detail(tour_id):
    conn = sqlite3.connect('tour_agency.db')
    c = conn.cursor()
    c.execute('SELECT * FROM tours WHERE id = ?', (tour_id,))
    tour = c.fetchone()
    conn.close()
    
    if not tour:
        flash('Тур не найден', 'error')
        return redirect(url_for('tours'))
    
    tour_data = {
        'id': tour[0],
        'title': tour[1],
        'description': tour[2],
        'price': tour[3],
        'duration': tour[4],
        'destination': tour[5],
        'image_url': tour[6]
    }
    
    return render_template('tour_detail.html', tour=tour_data, user=session.get('username'))

@app.route('/book/<int:tour_id>', methods=['POST'])
@login_required
def book_tour(tour_id):
    user_id = session.get('user_id')
    
    conn = sqlite3.connect('tour_agency.db')
    c = conn.cursor()
    c.execute('INSERT INTO bookings (user_id, tour_id, status) VALUES (?, ?, ?)',
              (user_id, tour_id, 'pending'))
    conn.commit()
    conn.close()
    
    log_activity(user_id, 'BOOK_TOUR', f'Booked tour {tour_id}')
    flash('Тур успешно забронирован!', 'success')
    return redirect(url_for('my_bookings'))

@app.route('/my-bookings')
@login_required
def my_bookings():
    user_id = session.get('user_id')
    
    conn = sqlite3.connect('tour_agency.db')
    c = conn.cursor()
    c.execute('''SELECT b.id, b.booking_date, b.status, t.title, t.price, t.destination
                 FROM bookings b
                 JOIN tours t ON b.tour_id = t.id
                 WHERE b.user_id = ?
                 ORDER BY b.booking_date DESC''', (user_id,))
    bookings = c.fetchall()
    conn.close()
    
    bookings_list = []
    for booking in bookings:
        bookings_list.append({
            'id': booking[0],
            'booking_date': booking[1],
            'status': booking[2],
            'tour_title': booking[3],
            'price': booking[4],
            'destination': booking[5]
        })
    
    return render_template('my_bookings.html', bookings=bookings_list, user=session.get('username'))

@app.route('/api/tours')
def api_tours():
    conn = sqlite3.connect('tour_agency.db')
    c = conn.cursor()
    c.execute('SELECT * FROM tours WHERE available = 1 ORDER BY created_at DESC')
    tours = c.fetchall()
    conn.close()
    
    tours_list = []
    for tour in tours:
        tours_list.append({
            'id': tour[0],
            'title': tour[1],
            'description': tour[2],
            'price': tour[3],
            'duration': tour[4],
            'destination': tour[5],
            'image_url': tour[6]
        })
    
    return jsonify(tours_list)

@app.route('/api/stats')
@login_required
def api_stats():
    user_id = session.get('user_id')
    
    conn = sqlite3.connect('tour_agency.db')
    c = conn.cursor()
    
    # Статистика бронирований пользователя
    c.execute('SELECT COUNT(*) FROM bookings WHERE user_id = ?', (user_id,))
    total_bookings = c.fetchone()[0]
    
    c.execute('SELECT COUNT(*) FROM bookings WHERE user_id = ? AND status = ?', (user_id, 'pending'))
    pending_bookings = c.fetchone()[0]
    
    c.execute('SELECT SUM(t.price) FROM bookings b JOIN tours t ON b.tour_id = t.id WHERE b.user_id = ?', (user_id,))
    total_spent = c.fetchone()[0] or 0
    
    conn.close()
    
    return jsonify({
        'total_bookings': total_bookings,
        'pending_bookings': pending_bookings,
        'total_spent': total_spent
    })

if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)

