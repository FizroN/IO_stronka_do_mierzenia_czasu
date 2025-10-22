import os
import time
from flask import Flask, render_template, redirect, url_for, request, flash, session
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timezone

# --- Definicje szablonów (aby wszystko było w 1 pliku) ---

# Folder, w którym będą szablony
TEMPLATE_DIR = 'templates'

# Zawartość szablonu layout.html (baza)
LAYOUT_HTML = """
<!doctype html>
<html lang="pl">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no">
    <title>Time Tracker</title>
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

# Zawartość szablonu login.html
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
{% endblock %}
"""

# Zawartość szablonu dashboard.html
DASHBOARD_HTML = """
{% extends "layout.html" %}
{% block content %}
    <h2>Dashboard</h2>
    
    {% if active_project_name %}
        <div class="flash success">
            Obecnie pracujesz nad: <strong>{{ active_project_name }}</strong> (od {{ active_start_time.strftime('%H:%M:%S') }})
        </div>
    {% else %}
        <div class="flash">Obecnie nie pracujesz.</div>
    {% endif %}

    <hr>

    <h3>Rozpocznij / Zmień projekt</h3>
    <form action="{{ url_for('start_work') }}" method="POST">
        <div class="form-group">
            <label for="project_id">Wybierz projekt:</label>
            <select name="project_id" id="project_id" required>
                {% for pid, p in projects.items() %}
                    <option value="{{ pid }}">{{ p.name }}</option>
                {% endfor %}
            </select>
        </div>
        <button type="submit" class="btn">Start / Zmień Projekt</button>
    </form>

    {% if active_project_name %}
        <hr>
        <form action="{{ url_for('stop_work') }}" method="POST" style="margin-top: 20px;">
            <button type="submit" class="btn btn-danger">Zatrzymaj pracę</button>
        </form>
    {% endif %}
{% endblock %}
"""

# Zawartość szablonu report.html
REPORT_HTML = """
{% extends "layout.html" %}
{% block content %}
    <h2>Raport czasu pracy</h2>
    <p>Raport dla: <strong>{{ report_data.user_name }} {{ report_data.user_surname }}</strong></p>

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
                    <td colspan="5">Brak wpisów czasu pracy.</td>
                </tr>
            {% endfor %}
            <tr style="background-color: #f2f2f2; font-weight: bold;">
                 <td colspan="4">Łączny czas dzisiaj:</td>
                 <td>{{ report_data.total_today }}</td>
            </tr>
        </tbody>
    </table>
{% endblock %}
"""

# Funkcja do tworzenia plików szablonów
def create_templates():
    if not os.path.exists(TEMPLATE_DIR):
        os.makedirs(TEMPLATE_DIR)
        print(f"Utworzono katalog: {TEMPLATE_DIR}")

    templates_to_create = {
        'layout.html': LAYOUT_HTML,
        'login.html': LOGIN_HTML,
        'dashboard.html': DASHBOARD_HTML,
        'report.html': REPORT_HTML,
    }

    for filename, content in templates_to_create.items():
        filepath = os.path.join(TEMPLATE_DIR, filename)
        if not os.path.exists(filepath):
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"Utworzono plik szablonu: {filepath}")

# --- Konfiguracja Aplikacji Flask ---
app = Flask(__name__)
# Klucz jest wymagany do sesji i flash messages
app.config['SECRET_KEY'] = 'bardzo-tajny-klucz-zmien-to-na-cos-innego'

# --- Konfiguracja Flask-Login ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login' # Gdzie przekierować niezalogowanych [cite: 6]
login_manager.login_message = 'Musisz się zalogować, aby zobaczyć tę stronę.'
login_manager.login_message_category = 'error'


# --- Hardcoded Baza Danych (zgodnie z prośbą i dokumentacją) ---

# Użytkownicy [cite: 2, 6, 9]
# Hasło dla 'mateusz.wator' to 'superhaslo123'
# Hasło dla 'jakub.zak' to 'haslo456'
USERS_DB = {
    1: {
        "id": 1,
        "email": "mateusz.wator@timemasters.pl",
        "password_hash": generate_password_hash("superhaslo123", method="pbkdf2:sha256"), # [cite: 6]
        "name": "Mateusz",
        "surname": "Wątor",
        "role": "Pracownik"
    },
    2: {
        "id": 2,
        "email": "jakub.zak@timemasters.pl",
        "password_hash": generate_password_hash("haslo456", method="pbkdf2:sha256"), # [cite: 6]
        "name": "Jakub",
        "surname": "Żak",
        "role": "Pracownik"
    }
}

# Projekty [cite: 43]
PROJECTS_DB = {
    1: {"name": "Projekt Alfa"},
    2: {"name": "Projekt Delta"},
    3: {"name": "Zadania Wewnętrzne"}
}

# Wpisy czasu pracy (Time Entries) [cite: 9, 31, 97]
# Użyjemy listy, aby symulować bazę danych
TIME_ENTRIES_DB = []
_next_time_entry_id = 1 # Symulacja auto-inkrementacji ID

# Aktywne sesje pracy (kto nad czym teraz pracuje) [cite: 7]
# mapowanie: user_id -> time_entry_id
# Zmieniamy na przechowywanie w sesji Flask, aby działało dla wielu użytkowników
# Zamiast globalnego dict, użyjemy `session['active_entry_id']`


# --- Model Użytkownika dla Flask-Login ---
class User(UserMixin):
    def __init__(self, id, email, name, surname, role):
        self.id = id
        self.email = email
        self.name = name
        self.surname = surname
        self.role = role
    
    @staticmethod
    def get(user_id):
        user_data = USERS_DB.get(int(user_id))
        if user_data:
            return User(
                id=user_data['id'],
                email=user_data['email'],
                name=user_data['name'],
                surname=user_data['surname'],
                role=user_data['role']
            )
        return None

@login_manager.user_loader
def load_user(user_id):
    return User.get(user_id)

# --- Funkcje pomocnicze ---

def get_active_session_entry(user_id):
    """Pobiera aktywny (niezakończony) wpis czasu dla użytkownika."""
    active_entry_id = session.get('active_entry_id')
    if active_entry_id:
        for entry in TIME_ENTRIES_DB:
            # Sprawdza ID, czy należy do usera i czy nie jest zakończony
            if entry['id'] == active_entry_id and \
               entry['user_id'] == user_id and \
               entry['end_time'] is None:
                return entry
    return None

def stop_active_session(user_id):
    """Zatrzymuje aktywną sesję pracy dla użytkownika."""
    active_entry = get_active_session_entry(user_id)
    if active_entry:
        active_entry['end_time'] = datetime.now(timezone.utc)
        duration = active_entry['end_time'] - active_entry['start_time']
        active_entry['duration_sec'] = int(duration.total_seconds()) # [cite: 33]
        session.pop('active_entry_id', None) # Usuń z sesji
        print(f"Zatrzymano sesję {active_entry['id']} dla użytkownika {user_id}")
        return True
    return False

def format_duration(seconds):
    """Formatuje sekundy do czytelnego formatu H:M:S."""
    if seconds is None:
        return "W trakcie"
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{int(hours)}h {int(minutes)}m {int(seconds)}s"


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
        
        # Wyszukiwanie użytkownika po emailu [cite: 6, 88]
        user_data = None
        for uid, udata in USERS_DB.items():
            if udata['email'] == email:
                user_data = udata
                break
        
        # Weryfikacja hasła [cite: 6, 89]
        if user_data and check_password_hash(user_data['password_hash'], password):
            user_obj = User.get(user_data['id'])
            login_user(user_obj)
            session.pop('active_entry_id', None) # Wyczyść stan sesji po zalogowaniu
            print(f"Użytkownik {user_obj.email} zalogowany.")
            return redirect(url_for('dashboard'))
        else:
            flash('Nieprawidłowy e-mail lub hasło.', 'error')

    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    # Zatrzymaj pracę przy wylogowaniu! [cite: 72]
    stop_active_session(current_user.id)
    logout_user()
    session.clear() # Wyczyść całą sesję
    print("Użytkownik wylogowany.")
    flash('Zostałeś pomyślnie wylogowany.', 'success')
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    active_entry = get_active_session_entry(current_user.id)
    active_project_name = None
    active_start_time = None
    if active_entry:
        active_project_name = PROJECTS_DB.get(active_entry['project_id'], {}).get('name', 'Nieznany Projekt')
        active_start_time = active_entry['start_time'].replace(tzinfo=timezone.utc).astimezone(tz=None) # Konwersja na czas lokalny
        
    return render_template('dashboard.html', 
                           projects=PROJECTS_DB, 
                           active_project_name=active_project_name,
                           active_start_time=active_start_time)

@app.route('/start_work', methods=['POST'])
@login_required
def start_work():
    # To obsługuje "Clock In" [cite: 23, 54] i "Switch Project" [cite: 24, 66]
    global _next_time_entry_id
    project_id = request.form.get('project_id')
    if not project_id:
        flash("Musisz wybrać projekt.", 'error')
        return redirect(url_for('dashboard'))

    project_id = int(project_id)
    project_name = PROJECTS_DB.get(project_id, {}).get('name', 'Nieznany')
    
    # Zgodnie z logiką[cite: 7]: rozpoczęcie innego kończy poprzedni.
    if stop_active_session(current_user.id):
        flash(f"Zakończono pracę nad poprzednim projektem.", 'success')

    # Rozpocznij nową sesję [cite: 61, 62]
    new_entry = {
        "id": _next_time_entry_id,
        "user_id": current_user.id,
        "project_id": project_id,
        "start_time": datetime.now(timezone.utc), # [cite: 9]
        "end_time": None, # [cite: 9]
        "duration_sec": None # [cite: 33]
    }
    TIME_ENTRIES_DB.append(new_entry)
    session['active_entry_id'] = new_entry['id'] # Zapisz w sesji
    _next_time_entry_id += 1

    print(f"Rozpoczęto sesję {new_entry['id']} dla użytkownika {current_user.id} na projekcie {project_id}")
    flash(f"Rozpocząłeś pracę nad projektem: {project_name}", 'success')

    return redirect(url_for('dashboard'))

@app.route('/stop_work', methods=['POST'])
@login_required
def stop_work():
    # To obsługuje "Stop Working" [cite: 25, 72, 74]
    if stop_active_session(current_user.id):
        flash("Zatrzymałeś pracę.", 'success')
    else:
        flash("Nie pracowałeś nad żadnym projektem.", 'error')
        
    return redirect(url_for('dashboard'))

@app.route('/report')
@login_required
def report():
    # Generowanie raportu on-demand [cite: 6, 20, 98]
    user_entries = []
    total_today_sec = 0
    today = datetime.now(timezone.utc).date()

    for entry in TIME_ENTRIES_DB:
        if entry['user_id'] == current_user.id:
            project_name = PROJECTS_DB.get(entry['project_id'], {}).get('name', 'Nieznany')
            
            # Konwersja czasów UTC na lokalne dla wyświetlenia
            start_local = entry['start_time'].replace(tzinfo=timezone.utc).astimezone(tz=None)
            
            if entry['end_time']:
                end_local = entry['end_time'].replace(tzinfo=timezone.utc).astimezone(tz=None)
                end_str = end_local.strftime('%H:%M:%S')
            else:
                end_str = "W trakcie"

            # Sumowanie czasu pracy z dzisiaj
            if entry['duration_sec'] and start_local.date() == today:
                 total_today_sec += entry['duration_sec']
            
            # Formatowanie na potrzeby raportu
            formatted_entry = {
                'project_name': project_name,
                'date': start_local.strftime('%Y-%m-%d'),
                'start': start_local.strftime('%H:%M:%S'),
                'end': end_str,
                'duration': format_duration(entry['duration_sec'])
            }
            user_entries.append(formatted_entry)
    
    # Dane użytkownika do raportu [cite: 6, 21]
    report_data = {
        'user_name': current_user.name,
        'user_surname': current_user.surname,
        'entries': sorted(user_entries, key=lambda x: (x['date'], x['start']), reverse=True), # Sortuj od najnowszych
        'total_today': format_duration(total_today_sec) # [cite: 76]
    }
    
    return render_template('report.html', report_data=report_data)

# Dodanie filtra Jinja2 do szablonów
@app.template_filter('format_duration')
def _jinja_format_duration(seconds):
    return format_duration(seconds)

# --- Uruchomienie aplikacji ---
if __name__ == '__main__':
    # Utwórz szablony przed uruchomieniem serwera
    create_templates()
    
    print("="*50)
    print("Aplikacja Time Tracker jest gotowa.")
    print("Utworzono pliki szablonów w folderze 'templates'.")
    print("Uruchamianie serwera Flask pod adresem: http://127.0.0.1:5000")
    print("Aby się zalogować, użyj:")
    print("  Email: mateusz.wator@timemasters.pl")
    print("  Hasło: superhaslo123")
    print("Naciśnij CTRL+C aby zatrzymać serwer.")
    print("="*50)
    
    # Uruchom aplikację
    app.run(debug=True)