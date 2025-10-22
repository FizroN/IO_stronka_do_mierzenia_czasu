import os
import json
import time
import calendar
from flask import Flask, render_template, redirect, url_for, request, flash, session
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timezone, timedelta

# --- Definicje szablonów (aby wszystko było w 1 pliku) ---

# Folder, w którym będą szablony
TEMPLATE_DIR = 'templates'

# Zawartość szablonu layout.html (baza) - bez zmian
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
        /* Styl dla kontenera wykresu */
        .chart-container { width: 100%; margin: 25px 0; }
        /* Style dla filtrów raportu */
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

# Zawartość szablonu login.html (bez zmian)
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

# Zawartość szablonu dashboard.html (bez zmian)
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
                {% for project_name in projects %}
                    <option value="{{ project_name }}">{{ project_name }}</option>
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

# ZAKTUALIZOWANA Zawartość szablonu report.html
# Logika dropdownów dla dat jest teraz dynamiczna
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
                    title: {
                        display: true,
                        text: 'Miesięczny skumulowany czas pracy (w godzinach)'
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                let label = context.dataset.label || '';
                                if (label) {
                                    label += ': ';
                                }
                                if (context.parsed.y !== null) {
                                    label += context.parsed.y + ' h';
                                }
                                return label;
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        stacked: true,
                    },
                    y: {
                        stacked: true,
                        title: {
                            display: true,
                            text: 'Godziny'
                        }
                    }
                }
            }
        });
    </script>
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
        # Zawsze nadpisuj plik report, aby wprowadzić zmiany
        if not os.path.exists(filepath) or filename in ['report.html', 'layout.html']:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"Utworzono/Zaktualizowano plik szablonu: {filepath}")

# --- Konfiguracja Aplikacji Flask ---
app = Flask(__name__)
app.config['SECRET_KEY'] = 'bardzo-tajny-klucz-zmien-to-na-cos-innego'

# --- Konfiguracja Flask-Login ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Musisz się zalogować, aby zobaczyć tę stronę.'
login_manager.login_message_category = 'error'

# --- Logika Zarządzania plikami JSON (bez zmian) ---

DATA_DIR = 'data'
TIME_ENTRIES_DIR = os.path.join(DATA_DIR, 'time_entries')
USERS_FILE = os.path.join(DATA_DIR, 'users.json')
PROJECTS_FILE = os.path.join(DATA_DIR, 'projects.json')

USERS_DB = {}
PROJECTS_SET = set()

def load_json(file_path, default_value):
    if not os.path.exists(file_path):
        return default_value
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        print(f"Błąd odczytu pliku {file_path}, zwracam wartość domyślną.")
        return default_value

def save_json(file_path, data):
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except IOError:
        print(f"Błąd zapisu do pliku {file_path}")

def get_user_entries_path(user_id):
    return os.path.join(TIME_ENTRIES_DIR, f"entries_user_{user_id}.json")

def load_user_time_entries(user_id):
    file_path = get_user_entries_path(user_id)
    entries = load_json(file_path, [])
    valid_entries = []
    for entry in entries:
        try:
            entry['start_time'] = datetime.fromisoformat(entry['start_time_str'])
            entry['end_time'] = datetime.fromisoformat(entry['end_time_str'])
            valid_entries.append(entry)
        except (ValueError, KeyError):
            print(f"Pomijam błędny wpis czasu: {entry.get('id', '???')} dla użytkownika {user_id}")
            continue
    return valid_entries

def save_user_time_entries(user_id, entries):
    file_path = get_user_entries_path(user_id)
    entries_to_save = []
    for entry in entries:
        entry_copy = entry.copy()
        if 'start_time' in entry_copy and isinstance(entry_copy['start_time'], datetime):
            entry_copy['start_time_str'] = entry_copy['start_time'].isoformat()
        if 'end_time' in entry_copy and isinstance(entry_copy['end_time'], datetime):
            entry_copy['end_time_str'] = entry_copy['end_time'].isoformat()
        
        entry_copy.pop('start_time', None)
        entry_copy.pop('end_time', None)
        entries_to_save.append(entry_copy)
        
    save_json(file_path, entries_to_save)

# --- Model Użytkownika (bez zmian) ---
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

    @staticmethod
    def find_by_email(email):
        for uid, udata in USERS_DB.items():
            if udata['email'] == email:
                return udata
        return None

    @staticmethod
    def get_all_users():
        users = []
        for uid in USERS_DB.keys():
            users.append(User.get(uid))
        return sorted(users, key=lambda u: (u.surname, u.name))

@login_manager.user_loader
def load_user(user_id):
    return User.get(user_id)

# --- Funkcje pomocnicze (bez zmian) ---
def format_duration(seconds):
    if seconds is None:
        return "N/A"
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{int(hours)}h {int(minutes)}m {int(seconds)}s"


# --- Trasy (Routes) ---

# Trasy /login, /logout, /dashboard, /add_time_entry (bez zmian)
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
        user_data = User.find_by_email(email)
        
        if user_data and check_password_hash(user_data['password_hash'], password):
            user_obj = User.get(user_data['id'])
            login_user(user_obj)
            print(f"Użytkownik {user_obj.email} zalogowany.")
            return redirect(url_for('dashboard'))
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

@app.route('/dashboard')
@login_required
def dashboard():
    projects_list = sorted(list(PROJECTS_SET))
    today_date = datetime.now().strftime('%Y-%m-%d')
    return render_template('dashboard.html', 
                           projects=projects_list,
                           today_date=today_date)

@app.route('/add_time_entry', methods=['POST'])
@login_required
def add_time_entry():
    global PROJECTS_SET
    date_str = request.form.get('date')
    start_str = request.form.get('start_time')
    end_str = request.form.get('end_time')
    existing_project = request.form.get('project_select')
    new_project = request.form.get('project_new', '').strip()
    
    project_name = ""
    if new_project:
        project_name = new_project
        if new_project not in PROJECTS_SET:
            PROJECTS_SET.add(new_project)
            save_json(PROJECTS_FILE, list(PROJECTS_SET))
            print(f"Dodano nowy projekt: {new_project} i zapisano do pliku.")
            flash(f"Dodano nowy projekt do listy: {new_project}", 'success')
    elif existing_project:
        project_name = existing_project
    
    if not project_name:
        flash("Musisz wybrać istniejący projekt lub dodać nowy.", 'error')
        return redirect(url_for('dashboard'))

    try:
        start_naive = datetime.fromisoformat(f"{date_str}T{start_str}")
        end_naive = datetime.fromisoformat(f"{date_str}T{end_str}")
        start_utc = start_naive.astimezone().astimezone(timezone.utc)
        end_utc = end_naive.astimezone().astimezone(timezone.utc)

        if end_utc <= start_utc:
            flash("Godzina zakończenia musi być późniejsza niż godzina rozpoczęcia.", 'error')
            return redirect(url_for('dashboard'))
        
        duration = end_utc - start_utc
        duration_sec = int(duration.total_seconds())

    except ValueError:
        flash("Nieprawidłowy format daty lub godziny.", 'error')
        return redirect(url_for('dashboard'))

    user_entries = load_user_time_entries(current_user.id)
    new_entry = {
        "id": len(user_entries) + 1,
        "user_id": current_user.id,
        "project_name": project_name,
        "start_time": start_utc,
        "end_time": end_utc,
        "duration_sec": duration_sec
    }
    user_entries.append(new_entry)
    save_user_time_entries(current_user.id, user_entries)

    print(f"Dodano wpis {new_entry['id']} dla {current_user.email} i zapisano w pliku.")
    flash(f"Pomyślnie dodano wpis czasu pracy ({format_duration(duration_sec)}).", 'success')
    return redirect(url_for('dashboard'))


# ZNACZĄCO ZAKTUALIZOWANA trasa /report
@app.route('/report')
@login_required
def report():
    # --- 0. Przygotowanie wstępne ---
    all_users = User.get_all_users()
    today = datetime.now().date()
    month_names = ["", "Styczeń", "Luty", "Marzec", "Kwiecień", "Maj", "Czerwiec", 
                   "Lipiec", "Sierpień", "Wrzesień", "Październik", "Listopad", "Grudzień"]

    # --- 1. Ustalenie wybranego UŻYTKOWNIKA ---
    try:
        selected_user_id = int(request.args.get('user_id', current_user.id))
    except ValueError:
        selected_user_id = current_user.id

    report_user_data = USERS_DB.get(selected_user_id)
    if not report_user_data:
        flash("Nie znaleziono takiego użytkownika.", 'error')
        return redirect(url_for('report'))

    # --- 2. Wczytanie WSZYSTKICH danych użytkownika i budowa dynamicznych filtrów ---
    all_user_entries = load_user_time_entries(selected_user_id)
    
    available_years_set = set()
    # Słownik: { 2025: {10, 11}, 2024: {12} }
    available_months_by_year = {} 
    
    for entry in all_user_entries:
        # Używamy czasu lokalnego do określenia roku/miesiąca
        start_local = entry['start_time'].replace(tzinfo=timezone.utc).astimezone(tz=None)
        year = start_local.year
        month = start_local.month
        
        available_years_set.add(year)
        if year not in available_months_by_year:
            available_months_by_year[year] = set()
        available_months_by_year[year].add(month)

    # --- 3. Ustalenie wybranego ROKU ---
    
    # Sortuj lata (najnowsze pierwsze), lub użyj bieżącego roku, jeśli brak danych
    if not available_years_set:
        available_years = [today.year]
    else:
        available_years = sorted(list(available_years_set), reverse=True)

    # Weź rok z URL, domyślnie 0
    try:
        selected_year = int(request.args.get('year', 0))
    except ValueError:
        selected_year = 0
    
    # Jeśli rok z URL jest nieprawidłowy (lub 0), wybierz najnowszy dostępny
    if selected_year not in available_years:
        selected_year = available_years[0]

    # --- 4. Ustalenie wybranego MIESIĄCA (na podstawie wybranego roku) ---
    
    # Pobierz dostępne miesiące dla wybranego roku
    months_set_for_year = available_months_by_year.get(selected_year, set())
    
    if not months_set_for_year:
        # Jeśli brak danych, użyj bieżącego miesiąca
        available_months = [(today.month, month_names[today.month])]
    else:
        # Zbuduj listę krotek (numer, nazwa) i posortuj (najnowsze pierwsze)
        available_months = sorted(
            [(m_num, month_names[m_num]) for m_num in months_set_for_year],
            key=lambda x: x[0],
            reverse=True 
        )

    # Weź miesiąc z URL, domyślnie 0
    try:
        selected_month = int(request.args.get('month', 0))
    except ValueError:
        selected_month = 0

    # Jeśli miesiąc z URL jest nieprawidłowy (lub 0), wybierz najnowszy dostępny
    available_month_nums = [m[0] for m in available_months]
    if selected_month not in available_month_nums:
        selected_month = available_month_nums[0]

    # --- 5. Przygotowanie osi X dla wykresu (cały wybrany miesiąc) ---
    try:
        num_days_in_month = calendar.monthrange(selected_year, selected_month)[1]
    except calendar.IllegalMonthError:
        num_days_in_month = 30 # Fallback

    first_day_of_month = datetime(selected_year, selected_month, 1).date()
    date_labels = [] # Etykiety dla osi X (np. "Oct 01")
    date_keys = []   # Klucze do wyszukiwania danych (np. "2025-10-01")
    
    for i in range(num_days_in_month):
        current_day = first_day_of_month + timedelta(days=i)
        date_labels.append(current_day.strftime('%b %d'))
        date_keys.append(current_day.strftime('%Y-%m-%d'))

    # --- 6. Filtrowanie danych i agregacja (Tabela i Wykres) ---
    
    user_entries_formatted = [] # Do tabeli
    total_month_sec = 0         # Do sumy w tabeli
    daily_project_summary = {}  # Do wykresu
    all_projects_in_month = set() # Do wykresu
    
    # Iterujemy po wczytanych wcześniej `all_user_entries`
    for entry in all_user_entries:
        start_local = entry['start_time'].replace(tzinfo=timezone.utc).astimezone(tz=None)
        
        # GŁÓWNY FILTR: Sprawdź, czy wpis pasuje do wybranego ROKU i MIESIĄCA
        if start_local.year == selected_year and start_local.month == selected_month:
            
            # --- Logika dla Tabeli ---
            total_month_sec += entry['duration_sec']
            end_local = entry['end_time'].replace(tzinfo=timezone.utc).astimezone(tz=None)
            
            formatted_entry = {
                'project_name': entry.get('project_name', 'Nieznany'),
                'date': start_local.strftime('%Y-%m-%d'),
                'start': start_local.strftime('%H:%M:%S'),
                'end': end_local.strftime('%H:%M:%S'),
                'duration': format_duration(entry['duration_sec'])
            }
            user_entries_formatted.append(formatted_entry)
            
            # --- Logika dla Wykresu ---
            local_date_str = start_local.strftime('%Y-%m-%d')
            project = entry['project_name']
            duration = entry['duration_sec']
            
            all_projects_in_month.add(project)
            
            if local_date_str not in daily_project_summary:
                daily_project_summary[local_date_str] = {}
            if project not in daily_project_summary[local_date_str]:
                daily_project_summary[local_date_str][project] = 0
                
            daily_project_summary[local_date_str][project] += duration

    # --- 7. Przygotowanie finalnych danych do przekazania ---
    
    report_data = {
        'user_name': report_user_data['name'],
        'user_surname': report_user_data['surname'],
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
            'label': project_name,
            'data': data_list,
            'backgroundColor': color
        })
    
    chart_data = {
        'labels': date_labels,
        'datasets': chart_datasets
    }

    # --- 8. Renderowanie szablonu ---
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

# --- Funkcja Inicjalizująca Dane (bez zmian) ---
def initialize_data_files():
    global USERS_DB, PROJECTS_SET
    
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(TIME_ENTRIES_DIR, exist_ok=True)
    
    loaded_users = load_json(USERS_FILE, {})
    if loaded_users:
        USERS_DB = {int(k): v for k, v in loaded_users.items()}
    else:
        print("Tworzenie domyślnego pliku users.json...")
        USERS_DB = {
            1: { "id": 1, "email": "mateusz.wator@timemasters.pl", "password_hash": generate_password_hash("superhaslo123", method="pbkdf2:sha256"), "name": "Mateusz", "surname": "Wątor", "role": "Pracownik" },
            2: { "id": 2, "email": "jakub.zak@timemasters.pl", "password_hash": generate_password_hash("haslo456", method="pbkdf2:sha256"), "name": "Jakub", "surname": "Żak", "role": "Pracownik" }
        }
        save_json(USERS_FILE, USERS_DB)
    
    loaded_projects = load_json(PROJECTS_FILE, None)
    if loaded_projects is not None:
        PROJECTS_SET = set(loaded_projects)
    else:
        print("Tworzenie domyślnego pliku projects.json...")
        PROJECTS_SET = {"Projekt Alfa", "Projekt Delta", "Zadania Wewnętrzne"}
        save_json(PROJECTS_FILE, list(PROJECTS_SET))
    
    print(f"Gotowe. Załadowano {len(USERS_DB)} użytkowników i {len(PROJECTS_SET)} projektów z plików.")


# --- Uruchomienie aplikacji ---
if __name__ == '__main__':
    create_templates()
    initialize_data_files()
    
    print("="*50)
    print("Aplikacja Time Tracker jest gotowa.")
    print("ZAKTUALIZOWANO: Filtry dat w raporcie są teraz dynamiczne (na podstawie danych).")
    print("Plik szablonu 'report.html' został zaktualizowany.")
    print("Uruchamianie serwera Flask pod adresem: http://127.0.0.1:5000")
    print("="*50)
    
    app.run(debug=True)