import os
import json
import time
import calendar
from flask import Flask, render_template, redirect, url_for, request, flash, session
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timezone, timedelta
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func

# IMPORTY DO REJESTRACJI
from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadTimeSignature

# --- Definicje szablonów ---
TEMPLATE_DIR = 'templates'

# Zawartość szablonu layout.html (z linkiem do Rejestracji)
LAYOUT_HTML = """
<!doctype html>
<html lang="pl">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no">
    <title>Time Tracker</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; line-height: 1.6; background-color: #f4f4f4; margin: 0; padding: 20px; }
        .container { max-width: 900px; margin: 20px auto; padding: 20px; background-color: #fff; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }
        nav { background: #333; padding: 10px 20px; border-radius: 8px 8px 0 0; }
        nav a { color: white; text-decoration: none; padding: 10px 15px; display: inline-block; }
        nav a:hover { background: #555; }
        nav .user-info { float: right; color: #eee; padding: 10px; }
        .flash { padding: 15px; margin-bottom: 20px; border-radius: 4px; color: #fff; }
        .flash.success { background-color: #28a745; }
        .flash.error { background-color: #dc3545; }
        .form-group { margin-bottom: 15px; }
        .form-group label { display: block; margin-bottom: 5px; font-weight: bold; }
        .form-group input, .form-group select { width: 100%; padding: 8px; box-sizing: border-box; border: 1px solid #ccc; border-radius: 4px; }
        .btn { padding: 10px 15px; color: #fff; background-color: #007bff; border: none; border-radius: 4px; cursor: pointer; text-decoration: none; display: inline-block; }
        .btn-danger { background-color: #dc3545; }
        .btn-secondary { background-color: #6c757d; }
        table { width: 100%; border-collapse: collapse; margin-top: 20px; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background-color: #f2f2f2; }
        .chart-container { width: 100%; margin: 25px 0; }
        .report-filters { display: flex; gap: 15px; margin-bottom: 20px; }
        .report-filters .form-group { flex: 1; margin-bottom: 0; }
    </style>
</head>
<body>
    <div class="container">
        <nav>
            <a href="{{ url_for('dashboard') }}">Dashboard</a>
            <a href="{{ url_for('report') }}">Raport</a>
            {% if current_user.is_authenticated %}
                <span class="user-info">Witaj, {{ current_user.name }}!</span>
                <a href="{{ url_for('logout') }}" style="float: right;">Wyloguj</a>
            {% else %}
                <a href="{{ url_for('login') }}" style="float: right;">Zaloguj</a>
                <a href="{{ url_for('register') }}" style="float: right;">Zarejestruj się</a>
            {% endif %}
        </nav>
        
        {% with messages = get_flashed_messages(with_categories=true) %}
          {% if messages %}
            {% for category, message in messages %}
              <div class="flash {{ category }}">{{ message }}</div>
            {% endfor %}
          {% endif %}
        {% endwith %}

        {% block content %}{% endblock %}
    </div>
</body>
</html>
"""

# ZAKTUALIZOWANY login.html, aby zawierał link do rejestracji
LOGIN_HTML = """
{% extends "layout.html" %}
{% block content %}
    <h2>Logowanie</h2>
    <form method="POST" action="{{ url_for('login') }}">
        <div class="form-group">
            <label for="email">E-mail (login)</label>
            <input type="email" id="email" name="email" required>
        </div>
        <div class="form-group">
            <label for="password">Hasło</label>
            <input type="password" id="password" name="password" required>
        </div>
        <button type="submit" class="btn">Zaloguj</button>
    </form>
    <p style="margin-top: 15px;">
        Nie masz konta? <a href="{{ url_for('register') }}">Zarejestruj się tutaj</a>.
    </p>
{% endblock %}
"""

# Zawartość szablonu dashboard.html (logika ręcznego wpisu)
DASHBOARD_HTML = """
{% extends "layout.html" %}
{% block content %}
    <h2>Zaraportuj czas pracy</h2>
    <form action="{{ url_for('add_time_entry') }}" method="POST">
        <div class="form-group">
            <label for="date">Data:</label>
            <input type="date" id="date" name="date" required value="{{ today_date }}">
        </div>
        <div class="form-group">
            <label for="start_time">Godzina rozpoczęcia:</label>
            <input type="time" id="start_time" name="start_time" required>
        </div>
        <div class="form-group">
            <label for="end_time">Godzina zakończenia:</label>
            <input type="time" id="end_time" name="end_time" required>
        </div>
        <hr>
        <div class="form-group">
            <label for="project_select">Wybierz istniejący projekt:</label>
            <select name="project_select" id="project_select">
                <option value="">-- Wybierz --</option>
                {% for project in projects %}
                    <option value="{{ project.name }}">{{ project.name }}</option>
                {% endfor %}
            </select>
        </div>
        <div class="form-group">
            <label for="project_new">...lub dodaj nowy projekt:</label>
            <input type="text" id="project_new" name="project_new" placeholder="Np. Nowy Projekt Klienta X">
        </div>
        <button type="submit" class="btn">Zapisz wpis czasu</button>
    </form>
{% endblock %}
"""

# Zawartość szablonu report.html (z filtrami dynamicznymi)
REPORT_HTML = """
{% extends "layout.html" %}
{% block content %}
    <h2>Raport czasu pracy</h2>
    <form method="GET" action="{{ url_for('report') }}">
        <div class="report-filters">
            <div class="form-group">
                <label for="user_select">Użytkownik:</label>
                <select name="user_id" id="user_select" class="form-control" onchange="this.form.submit()">
                    {% for user in all_users %}
                        <option value="{{ user.id }}" {% if user.id == selected_user_id %}selected{% endif %}>
                            {{ user.name }} {{ user.surname }}
                        </option>
                    {% endfor %}
                </select>
            </div>
            <div class="form-group">
                <label for="year_select">Rok:</label>
                <select name="year" id="year_select" class="form-control" onchange="this.form.submit()">
                    {% for year in available_years %}
                        <option value="{{ year }}" {% if year == selected_year %}selected{% endif %}>
                            {{ year }}
                        </option>
                    {% else %}
                        <option value="{{ selected_year }}">{{ selected_year }}</option>
                    {% endfor %}
                </select>
            </div>
            <div class="form-group">
                <label for="month_select">Miesiąc:</label>
                <select name="month" id="month_select" class="form-control" onchange="this.form.submit()">
                    {% for month_num, month_name in available_months %}
                        <option value="{{ month_num }}" {% if month_num == selected_month %}selected{% endif %}>
                            {{ month_name }}
                        </option>
                    {% else %}
                         <option value="{{ selected_month }}">{{ available_months[0][1] }}</option>
                    {% endfor %}
                </select>
            </div>
        </div>
    </form>
    <p>Raport dla: <strong>{{ report_data.user_name }} {{ report_data.user_surname }}</strong></p>
    <div class="chart-container">
        <canvas id="monthlyChart"></canvas>
    </div>
    <hr>
    <h3>Szczegółowe wpisy ({{ selected_year }}-{{ '%02d'|format(selected_month) }})</h3>
    <table>
        <thead>
            <tr>
                <th>Projekt</th>
                <th>Data</th>
                <th>Start</th>
                <th>Koniec</th>
                <th>Czas trwania</th>
            </tr>
        </thead>
        <tbody>
            {% for entry in report_data.entries %}
                <tr>
                    <td>{{ entry.project_name }}</td>
                    <td>{{ entry.date }}</td>
                    <td>{{ entry.start }}</td>
                    <td>{{ entry.end }}</td>
                    <td>{{ entry.duration }}</td>
                </tr>
            {% else %}
                <tr>
                    <td colspan="5">Brak wpisów czasu pracy w wybranym miesiącu.</td>
                </tr>
            {% endfor %}
            <tr style="background-color: #f2f2f2; font-weight: bold;">
                 <td colspan="4">Łączny czas w wybranym miesiącu:</td>
                 <td>{{ report_data.total_in_month }}</td>
            </tr>
        </tbody>
    </table>
    <script>
        const ctx = document.getElementById('monthlyChart').getContext('2d');
        const chartData = {{ chart_data|tojson }};
        new Chart(ctx, {
            type: 'bar',
            data: chartData,
            options: {
                responsive: true,
                plugins: {
                    title: { display: true, text: 'Miesięczny skumulowany czas pracy (w godzinach)' },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                let label = context.dataset.label || '';
                                if (label) { label += ': '; }
                                if (context.parsed.y !== null) { label += context.parsed.y + ' h'; }
                                return label;
                            }
                        }
                    }
                },
                scales: {
                    x: { stacked: true },
                    y: { stacked: true, title: { display: true, text: 'Godziny' } }
                }
            }
        });
    </script>
{% endblock %}
"""

# --- NOWE SZABLONY ---

# NOWY szablon: register.html
REGISTER_HTML = """
{% extends "layout.html" %}
{% block content %}
    <h2>Rejestracja</h2>
    <p>Podaj swój adres e-mail, aby rozpocząć proces rejestracji.</p>
    <form method="POST" action="{{ url_for('register') }}">
        <div class="form-group">
            <label for="email">E-mail</label>
            <input type="email" id="email" name="email" required>
        </div>
        <div class="form-group">
            <label for="name">Imię</label>
            <input type="text" id="name" name="name" required>
        </div>
        <div class="form-group">
            <label for="surname">Nazwisko</label>
            <input type="text" id="surname" name="surname" required>
        </div>
        <button type="submit" class="btn">Zarejestruj</button>
    </form>
{% endblock %}
"""

# NOWY szablon: set_password.html
SET_PASSWORD_HTML = """
{% extends "layout.html" %}
{% block content %}
    <h2>Ustaw swoje hasło</h2>
    <p>Witaj, {{ email }}! Twój e-mail został zweryfikowany. Ustaw teraz swoje hasło.</p>
    <form method="POST">
        <div class="form-group">
            <label for="password">Nowe hasło</label>
            <input type="password" id="password" name="password" required>
        </div>
        <div class="form-group">
            <label for="password_confirm">Potwierdź hasło</label>
            <input type="password" id="password_confirm" name="password_confirm" required>
        </div>
        <button type="submit" class="btn">Ustaw hasło i zaloguj się</button>
    </form>
{% endblock %}
"""

# ZAKTUALIZOWANA funkcja do tworzenia szablonów
def create_templates():
    if not os.path.exists(TEMPLATE_DIR):
        os.makedirs(TEMPLATE_DIR)
        print(f"Utworzono katalog: {TEMPLATE_DIR}")
    templates_to_create = {
        'layout.html': LAYOUT_HTML,
        'login.html': LOGIN_HTML,
        'dashboard.html': DASHBOARD_HTML,
        'report.html': REPORT_HTML,
        'register.html': REGISTER_HTML,      # DODANO
        'set_password.html': SET_PASSWORD_HTML # DODANO
    }
    for filename, content in templates_to_create.items():
        filepath = os.path.join(TEMPLATE_DIR, filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
    print(f"Utworzono/Zaktualizowano pliki szablonów.")

# --- Konfiguracja Flask + SQLAlchemy ---
app = Flask(__name__)
app.config['SECRET_KEY'] = 'bardzo-tajny-klucz-zmien-to-na-cos-innego'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///time_tracker.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# --- KONFIGURACJA: Flask-Mail (Placeholdery) ---
# Te ustawienia są tu tylko po to, by Flask-Mail się załadował.
# NIE BĘDĄ UŻYWANE do wysyłki e-maila w Opcji 1.
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'TWOJ_EMAIL@gmail.com' 
app.config['MAIL_PASSWORD'] = 'TWOJE_HASLO_DO_APLIKACJI'
app.config['MAIL_DEFAULT_SENDER'] = ('Time Tracker', app.config['MAIL_USERNAME'])

# --- KONFIGURACJA: Tokeny (itsdangerous) ---
app.config['SECURITY_PASSWORD_SALT'] = 'moja-super-tajna-sol-do-tokenow'
ts = URLSafeTimedSerializer(app.config['SECRET_KEY'])

# Inicjalizacja rozszerzeń
db = SQLAlchemy(app)
mail = Mail(app) # Inicjalizacja Mail

# --- Konfiguracja Flask-Login (bez zmian) ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Musisz się zalogować, aby zobaczyć tę stronę.'
login_manager.login_message_category = 'error'


# --- Modele Bazy Danych (zmienione dla rejestracji) ---
class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(200), unique=True, nullable=False)
    password_hash = db.Column(db.String(300), nullable=True) # Hasło może być NULL
    name = db.Column(db.String(100), nullable=False)
    surname = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(50), nullable=False, default='Pracownik')
    is_verified = db.Column(db.Boolean, nullable=False, default=False) # Status weryfikacji

    def check_password(self, password):
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)

class Project(db.Model):
    __tablename__ = 'projects'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False, unique=True)

class TimeEntry(db.Model):
    __tablename__ = 'time_entries'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    start_time = db.Column(db.DateTime(timezone=True), nullable=False)
    end_time = db.Column(db.DateTime(timezone=True), nullable=True) 
    duration_sec = db.Column(db.Integer, nullable=True)
    user = db.relationship('User', backref=db.backref('time_entries', lazy=True))
    project = db.relationship('Project', backref=db.backref('time_entries', lazy=True))

# --- User loader (bez zmian) ---
@login_manager.user_loader
def load_user(user_id):
    if not user_id:
        return None
    return User.query.get(int(user_id))

# --- Funkcje pomocnicze (bez zmian) ---
def format_duration(seconds):
    if seconds is None:
        return "N/A"
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{int(hours)}h {int(minutes)}m {int(seconds)}s"

# --- FUNKCJA WYSYŁANIA E-MAILA (OPCJA 1: MOCK) ---
def send_verification_email(user_email, user_name, token):
    """Tworzy e-mail weryfikacyjny i drukuje link w konsoli."""
    
    # Tworzymy pełny link, który użytkownik kliknie
    verify_url = url_for('verify_email', token=token, _external=True)
    
    subject = "Potwierdź swoje konto w Time Tracker"
    
    # --- MOCKOWANIE WYSYŁKI ---
    # Zamiast wysyłać e-mail, drukujemy link w konsoli.
    print("="*50)
    print("MOCK E-MAIL SENT")
    print(f"DO: {user_email}")
    print(f"TEMAT: {subject}")
    print("SKOPIUJ I WKLEJ TEN LINK DO PRZEGLĄDARKI, ABY ZWERYFIKOWAĆ KONTO:")
    print(verify_url)
    print("="*50)
    
    # --- Prawdziwa wysyłka jest celowo zakomentowana ---
    # try:
    #     msg = Message(subject, recipients=[user_email], html="...")
    #     mail.send(msg)
    # except Exception as e:
    #     print(f"BŁĄD WYSYŁANIA E-MAILA: {e}")

# --- Trasy (Routes) ---

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        
        # Sprawdzamy, czy user istnieje i czy ma ustawione hasło
        if user and user.is_verified and user.check_password(password):
            login_user(user)
            print(f"Użytkownik {user.email} zalogowany.")
            return redirect(url_for('dashboard'))
        elif user and not user.is_verified:
             flash('Twoje konto nie zostało jeszcze zweryfikowane. Sprawdź e-mail (i konsolę).', 'error')
        else:
            flash('Nieprawidłowy e-mail lub hasło.', 'error')

    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    session.clear()
    print("Użytkownik wylogowany.")
    flash('Zostałeś pomyślnie wylogowany.', 'success')
    return redirect(url_for('login'))

# --- TRASY REJESTRACJI ---

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        email = request.form.get('email')
        name = request.form.get('name')
        surname = request.form.get('surname')

        if not all([email, name, surname]):
             flash('Wszystkie pola są wymagane.', 'error')
             return redirect(url_for('register'))

        existing_user = User.query.filter_by(email=email).first()

        if existing_user:
            if not existing_user.is_verified:
                token = ts.dumps(existing_user.email, salt=app.config['SECURITY_PASSWORD_SALT'])
                send_verification_email(existing_user.email, existing_user.name, token)
                flash('Ten e-mail jest już w systemie. Wysłano ponownie link weryfikacyjny (sprawdź konsolę).', 'success')
                return redirect(url_for('login'))
            else:
                flash('Użytkownik o tym adresie e-mail już istnieje.', 'error')
                return redirect(url_for('register'))
        
        new_user = User(
            email=email,
            name=name,
            surname=surname,
            is_verified=False
        )
        db.session.add(new_user)
        db.session.commit()

        # Wygeneruj token i "wyślij" e-mail (MOCK)
        token = ts.dumps(new_user.email, salt=app.config['SECURITY_PASSWORD_SALT'])
        send_verification_email(new_user.email, new_user.name, token)

        flash('Dziękujemy za rejestrację! Sprawdź swój e-mail (i konsolę), aby ustawić hasło.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/verify_email/<token>', methods=['GET', 'POST'])
def verify_email(token):
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    try:
        # Sprawdź token. Limit czasu: 1 dzień (86400 sekund)
        email = ts.loads(token, salt=app.config['SECURITY_PASSWORD_SALT'], max_age=86400)
    except SignatureExpired:
        flash('Link weryfikacyjny wygasł. Zarejestruj się ponownie, aby otrzymać nowy link.', 'error')
        return redirect(url_for('register'))
    except (BadTimeSignature, Exception):
        flash('Nieprawidłowy link weryfikacyjny.', 'error')
        return redirect(url_for('register'))

    user = User.query.filter_by(email=email).first()
    if not user:
        flash('Nie znaleziono użytkownika.', 'error')
        return redirect(url_for('register'))

    if request.method == 'POST':
        password = request.form.get('password')
        password_confirm = request.form.get('password_confirm')

        if not password or not password_confirm or password != password_confirm:
            flash('Hasła muszą być takie same i nie mogą być puste.', 'error')
            return render_template('set_password.html', email=email)
        
        # Ustaw hasło i zweryfikuj użytkownika
        user.password_hash = generate_password_hash(password, method="pbkdf2:sha256")
        user.is_verified = True
        db.session.commit()
        
        login_user(user)
        #session.clear()
        
        flash('Twoje konto zostało pomyślnie aktywowane! Jesteś zalogowany.', 'success')
        return redirect(url_for('dashboard'))

    # Jeśli GET, pokaż formularz ustawiania hasła
    return render_template('set_password.html', email=email)

# --- Pozostałe trasy (Dashboard, Add Entry, Report) ---

@app.route('/dashboard')
@login_required
def dashboard():
    projects_list = Project.query.order_by(Project.name).all()
    today_date = datetime.now().strftime('%Y-%m-%d')
    return render_template('dashboard.html', 
                           projects=projects_list,
                           today_date=today_date)

@app.route('/add_time_entry', methods=['POST'])
@login_required
def add_time_entry():
    date_str = request.form.get('date')
    start_str = request.form.get('start_time')
    end_str = request.form.get('end_time')
    existing_project = request.form.get('project_select')
    new_project = request.form.get('project_new', '').strip()
    
    project_name = ""
    if new_project:
        project_name = new_project
    elif existing_project:
        project_name = existing_project
    
    if not project_name:
        flash("Musisz wybrać istniejący projekt lub dodać nowy.", 'error')
        return redirect(url_for('dashboard'))

    project = Project.query.filter_by(name=project_name).first()
    if not project:
        project = Project(name=project_name)
        db.session.add(project)
        db.session.flush() 
        print(f"Dodano nowy projekt: {project_name} do bazy danych.")
        flash(f"Dodano nowy projekt do listy: {project_name}", 'success')

    try:
        start_naive = datetime.fromisoformat(f"{date_str}T{start_str}")
        end_naive = datetime.fromisoformat(f"{date_str}T{end_str}")
        start_utc = start_naive.astimezone().astimezone(timezone.utc)
        end_utc = end_naive.astimezone().astimezone(timezone.utc)
        if end_utc <= start_utc:
            flash("Godzina zakończenia musi być późniejsza niż godzina rozpoczęcia.", 'error')
            return redirect(url_for('dashboard'))
        duration_sec = int((end_utc - start_utc).total_seconds())
    except ValueError:
        flash("Nieprawidłowy format daty lub godziny.", 'error')
        return redirect(url_for('dashboard'))

    new_entry = TimeEntry(
        user_id=current_user.id,
        project_id=project.id,
        start_time=start_utc,
        end_time=end_utc,
        duration_sec=duration_sec
    )
    db.session.add(new_entry)
    db.session.commit()

    print(f"Dodano wpis dla {current_user.email} i zapisano w bazie.")
    flash(f"Pomyślnie dodano wpis czasu pracy ({format_duration(duration_sec)}).", 'success')
    return redirect(url_for('dashboard'))


@app.route('/report')
@login_required
def report():
    all_users = User.query.filter_by(is_verified=True).order_by(User.surname, User.name).all() # Tylko zweryfikowani
    today = datetime.now().date()
    month_names = ["", "Styczeń", "Luty", "Marzec", "Kwiecień", "Maj", "Czerwiec", 
                   "Lipiec", "Sierpień", "Wrzesień", "Październik", "Listopad", "Grudzień"]

    try:
        selected_user_id = int(request.args.get('user_id', current_user.id))
    except ValueError:
        selected_user_id = current_user.id

    report_user = User.query.get(selected_user_id)
    if not report_user or not report_user.is_verified:
        flash("Nie znaleziono takiego użytkownika.", 'error')
        return redirect(url_for('report'))

    all_user_entries = TimeEntry.query.filter_by(user_id=selected_user_id).all()
    
    available_years_set = set()
    available_months_by_year = {} 
    
    for entry in all_user_entries:
        start_local = entry.start_time.replace(tzinfo=timezone.utc).astimezone(tz=None)
        year = start_local.year
        month = start_local.month
        available_years_set.add(year)
        if year not in available_months_by_year:
            available_months_by_year[year] = set()
        available_months_by_year[year].add(month)

    if not available_years_set:
        available_years = [today.year]
    else:
        available_years = sorted(list(available_years_set), reverse=True)

    try:
        selected_year = int(request.args.get('year', 0))
    except ValueError:
        selected_year = 0
    
    if selected_year not in available_years:
        selected_year = available_years[0]

    months_set_for_year = available_months_by_year.get(selected_year, set())
    
    if not months_set_for_year:
        available_months = [(today.month, month_names[today.month])]
    else:
        available_months = sorted(
            [(m_num, month_names[m_num]) for m_num in months_set_for_year],
            key=lambda x: x[0],
            reverse=True 
        )

    try:
        selected_month = int(request.args.get('month', 0))
    except ValueError:
        selected_month = 0

    available_month_nums = [m[0] for m in available_months]
    if selected_month not in available_month_nums:
        selected_month = available_month_nums[0]

    try:
        num_days_in_month = calendar.monthrange(selected_year, selected_month)[1]
    except calendar.IllegalMonthError:
        num_days_in_month = 30 

    first_day_of_month = datetime(selected_year, selected_month, 1).date()
    date_labels = [] 
    date_keys = []   
    
    for i in range(num_days_in_month):
        current_day = first_day_of_month + timedelta(days=i)
        date_labels.append(current_day.strftime('%b %d'))
        date_keys.append(current_day.strftime('%Y-%m-%d'))

    user_entries_formatted = [] 
    total_month_sec = 0         
    daily_project_summary = {}  
    all_projects_in_month = set() 
    
    for entry in all_user_entries:
        start_local = entry.start_time.replace(tzinfo=timezone.utc).astimezone(tz=None)
        
        if start_local.year == selected_year and start_local.month == selected_month:
            project_name = entry.project.name if entry.project else "Nieznany Projekt"
            total_month_sec += entry.duration_sec
            end_local = entry.end_time.replace(tzinfo=timezone.utc).astimezone(tz=None)
            
            formatted_entry = {
                'project_name': project_name,
                'date': start_local.strftime('%Y-%m-%d'),
                'start': start_local.strftime('%H:%M:%S'),
                'end': end_local.strftime('%H:%M:%S'),
                'duration': format_duration(entry.duration_sec)
            }
            user_entries_formatted.append(formatted_entry)
            
            local_date_str = start_local.strftime('%Y-%m-%d')
            all_projects_in_month.add(project_name)
            
            if local_date_str not in daily_project_summary:
                daily_project_summary[local_date_str] = {}
            if project_name not in daily_project_summary[local_date_str]:
                daily_project_summary[local_date_str][project_name] = 0
            daily_project_summary[local_date_str][project_name] += entry.duration_sec

    report_data = {
        'user_name': report_user.name, 
        'user_surname': report_user.surname,
        'entries': sorted(user_entries_formatted, key=lambda x: (x['date'], x['start']), reverse=True),
        'total_in_month': format_duration(total_month_sec)
    }

    chart_datasets = []
    colors = ['#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', '#9966FF', '#FF9F40', '#E7E9ED']

    for i, project_name in enumerate(sorted(list(all_projects_in_month))):
        color = colors[i % len(colors)]
        data_list = []
        for date_key in date_keys:
            day_data = daily_project_summary.get(date_key, {})
            project_seconds = day_data.get(project_name, 0)
            project_hours = round(project_seconds / 3600, 2)
            data_list.append(project_hours)
        chart_datasets.append({
            'label': project_name, 'data': data_list, 'backgroundColor': color
        })
    
    chart_data = { 'labels': date_labels, 'datasets': chart_datasets }

    return render_template('report.html', 
                           report_data=report_data, 
                           chart_data=chart_data,
                           all_users=all_users,
                           selected_user_id=selected_user_id,
                           available_years=available_years,
                           selected_year=selected_year,
                           available_months=available_months,
                           selected_month=selected_month
                           )

# Dodanie filtra Jinja2 do szablonów
@app.template_filter('format_duration')
def _jinja_format_duration(seconds):
    return format_duration(seconds)

# --- Funkcja Inicjalizująca Bazę Danych ---
def init_db_and_seed():
    db.create_all()

    if Project.query.count() == 0:
        defaults = [
            Project(name="Projekt Alfa"), Project(name="Projekt Delta"), Project(name="Zadania Wewnętrzne")
        ]
        db.session.add_all(defaults)
        db.session.commit()
        print("Zainicjowano domyślne projekty w bazie danych.")

    # Zaktualizowano seeder, aby tworzył zweryfikowanych użytkowników
    if User.query.count() == 0:
        u1 = User(
            email="mateusz.wator@timemasters.pl",
            password_hash=generate_password_hash("superhaslo123", method="pbkdf2:sha256"),
            name="Mateusz",
            surname="Wątor",
            role="Pracownik",
            is_verified=True # Domyślni użytkownicy są zweryfikowani
        )
        u2 = User(
            email="jakub.zak@timemasters.pl",
            password_hash=generate_password_hash("haslo456", method="pbkdf2:sha256"),
            name="Jakub",
            surname="Żak",
            role="Pracownik",
            is_verified=True # Domyślni użytkownicy są zweryfikowani
        )
        db.session.add_all([u1, u2])
        db.session.commit()
        print("Zainicjowano domyślnych, zweryfikowanych użytkowników w bazie danych.")


# --- Uruchomienie aplikacji ---
if __name__ == '__main__':
    with app.app_context():
        create_templates()
        init_db_and_seed()
    
    print("="*50)
    print("Aplikacja Time Tracker jest gotowa.")
    print("ZAKTUALIZOWANO: Dodano system rejestracji i weryfikacji e-mail (OPCJA 1 - MOCK).")
    print("Weryfikacyjny e-mail zostanie wydrukowany w tej konsoli.")
    print("Uruchamianie serwera Flask pod adresem: http://127.0.0.1:5000")
    print("="*50)
    
    app.run(debug=True)