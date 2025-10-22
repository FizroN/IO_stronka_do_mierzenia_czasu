import os
import time
from flask import Flask, render_template, redirect, url_for, request, flash, session
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timezone, timedelta

# --- Definicje szablonów (aby wszystko było w 1 pliku) ---

# Folder, w którym będą szablony
TEMPLATE_DIR = 'templates'

# ZAKTUALIZOWANA Zawartość szablonu layout.html (baza)
# DODANO link do Chart.js w <head>
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
# DODANO <canvas> dla wykresu i blok <script> do jego renderowania
REPORT_HTML = """
{% extends "layout.html" %}
{% block content %}
    <h2>Raport czasu pracy</h2>
    <p>Raport dla: <strong>{{ report_data.user_name }} {{ report_data.user_surname }}</strong></p>

    <div class="chart-container">
        <canvas id="monthlyChart"></canvas>
    </div>

    <hr>
    
    <h3>Szczegółowe wpisy</h3>
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

    <script>
        const ctx = document.getElementById('monthlyChart').getContext('2d');
        
        // Dane wykresu przekazane z Flaska i bezpiecznie wstrzyknięte jako JSON
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
                        stacked: true, // Kluczowe dla skumulowanego
                    },
                    y: {
                        stacked: true, // Kluczowe dla skumulowanego
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
        # Zawsze nadpisuj pliki layout i report, aby wprowadzić zmiany
        if not os.path.exists(filepath) or filename in ['dashboard.html', 'layout.html', 'report.html']:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"Utworzono/Zaktualizowano plik szablonu: {filepath}")

# --- Konfiguracja Aplikacji Flask ---
app = Flask(__name__)
# Klucz jest wymagany do sesji i flash messages
app.config['SECRET_KEY'] = 'bardzo-tajny-klucz-zmien-to-na-cos-innego'

# --- Konfiguracja Flask-Login ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login' # Gdzie przekierować niezalogowanych
login_manager.login_message = 'Musisz się zalogować, aby zobaczyć tę stronę.'
login_manager.login_message_category = 'error'


# --- Hardcoded Baza Danych (zgodnie z prośbą i dokumentacją) ---

# Użytkownicy
# Hasło dla 'mateusz.wator' to 'superhaslo123'
# Hasło dla 'jakub.zak' to 'haslo456'
USERS_DB = {
    1: {
        "id": 1,
        "email": "mateusz.wator@timemasters.pl",
        "password_hash": generate_password_hash("superhaslo123", method="pbkdf2:sha256"), #
        "name": "Mateusz",
        "surname": "Wątor",
        "role": "Pracownik"
    },
    2: {
        "id": 2,
        "email": "jakub.zak@timemasters.pl",
        "password_hash": generate_password_hash("haslo456", method="pbkdf2:sha256"), #
        "name": "Jakub",
        "surname": "Żak",
        "role": "Pracownik"
    }
}

# ZMODYFIKOWANA BAZA PROJEKTÓW
# Używamy zbioru (set) do przechowywania unikalnych nazw projektów
# Można je dodawać dynamicznie
PROJECTS_SET = {
    "Projekt Alfa", 
    "Projekt Delta", 
    "Zadania Wewnętrzne"
}

# Wpisy czasu pracy (Time Entries)
# Użyjemy listy, aby symulować bazę danych
TIME_ENTRIES_DB = []
_next_time_entry_id = 1 # Symulacja auto-inkrementacji ID

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

def format_duration(seconds):
    """Formatuje sekundy do czytelnego formatu H:M:S."""
    if seconds is None:
        return "N/A"
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
        
        # Wyszukiwanie użytkownika po emailu
        user_data = None
        for uid, udata in USERS_DB.items():
            if udata['email'] == email:
                user_data = udata
                break
        
        # Weryfikacja hasła
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
    session.clear() # Wyczyść całą sesję
    print("Użytkownik wylogowany.")
    flash('Zostałeś pomyślnie wylogowany.', 'success')
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    # Pobierz posortowaną listę projektów do wyświetlenia
    projects_list = sorted(list(PROJECTS_SET))
    # Ustaw domyślną datę na dzisiaj
    today_date = datetime.now().strftime('%Y-%m-%d')
    return render_template('dashboard.html', 
                           projects=projects_list,
                           today_date=today_date)

@app.route('/add_time_entry', methods=['POST'])
@login_required
def add_time_entry():
    global _next_time_entry_id
    
    # Pobranie danych z formularza
    date_str = request.form.get('date')
    start_str = request.form.get('start_time')
    end_str = request.form.get('end_time')
    existing_project = request.form.get('project_select')
    new_project = request.form.get('project_new', '').strip()
    
    # Walidacja projektu
    project_name = ""
    if new_project:
        project_name = new_project
        if new_project not in PROJECTS_SET:
            PROJECTS_SET.add(new_project)
            print(f"Dodano nowy projekt: {new_project}")
            flash(f"Dodano nowy projekt do listy: {new_project}", 'success')
    elif existing_project:
        project_name = existing_project
    
    if not project_name:
        flash("Musisz wybrać istniejący projekt lub dodać nowy.", 'error')
        return redirect(url_for('dashboard'))

    # Walidacja i parsowanie czasu
    if not all([date_str, start_str, end_str]):
        flash("Wszystkie pola czasu (data, start, koniec) są wymagane.", 'error')
        return redirect(url_for('dashboard'))

    try:
        # Tworzymy obiekty datetime z podanych stringów
        # Zakładamy, że użytkownik wprowadza czas lokalny
        start_naive = datetime.fromisoformat(f"{date_str}T{start_str}")
        end_naive = datetime.fromisoformat(f"{date_str}T{end_str}")

        # Konwertujemy czas lokalny na UTC do zapisu w bazie
        # .astimezone() bez argumentu dodaje lokalną strefę czasową
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

    # Zapis do "bazy danych"
    new_entry = {
        "id": _next_time_entry_id,
        "user_id": current_user.id,
        "project_name": project_name, # Przechowujemy nazwę
        "start_time": start_utc,     # Zapisujemy w UTC
        "end_time": end_utc,         # Zapisujemy w UTC
        "duration_sec": duration_sec
    }
    TIME_ENTRIES_DB.append(new_entry)
    _next_time_entry_id += 1

    print(f"Dodano wpis {new_entry['id']} dla {current_user.email}: {project_name}, {format_duration(duration_sec)}")
    flash(f"Pomyślnie dodano wpis czasu pracy ({format_duration(duration_sec)}).", 'success')
    return redirect(url_for('dashboard'))


# ZAKTUALIZOWANA trasa /report
@app.route('/report')
@login_required
def report():
    # --- 1. Przygotowanie danych do tabeli (jak wcześniej) ---
    user_entries = []
    total_today_sec = 0
    today_local = datetime.now().date() # Dzień w lokalnej strefie czasowej

    for entry in TIME_ENTRIES_DB:
        if entry['user_id'] == current_user.id:
            project_name = entry.get('project_name', 'Nieznany')
            start_local = entry['start_time'].replace(tzinfo=timezone.utc).astimezone(tz=None)
            
            if entry['end_time']:
                end_local = entry['end_time'].replace(tzinfo=timezone.utc).astimezone(tz=None)
                end_str = end_local.strftime('%H:%M:%S')
            else:
                end_str = "N/A"

            if entry['duration_sec'] and start_local.date() == today_local:
                 total_today_sec += entry['duration_sec']
            
            formatted_entry = {
                'project_name': project_name,
                'date': start_local.strftime('%Y-%m-%d'),
                'start': start_local.strftime('%H:%M:%S'),
                'end': end_str,
                'duration': format_duration(entry['duration_sec'])
            }
            user_entries.append(formatted_entry)
    
    report_data = {
        'user_name': current_user.name,
        'user_surname': current_user.surname,
        'entries': sorted(user_entries, key=lambda x: (x['date'], x['start']), reverse=True),
        'total_today': format_duration(total_today_sec)
    }

    # --- 2. Przygotowanie danych do wykresu miesięcznego ---
    
    # Etykiety: Dni od 1 do dzisiaj w bieżącym miesiącu (w strefie lokalnej)
    today = datetime.now().date()
    first_day_of_month = today.replace(day=1)
    num_days_so_far = (today - first_day_of_month).days + 1
    
    # `date_labels` to etykiety dla osi X (np. "Oct 01")
    # `date_keys` to klucze do wyszukiwania danych (np. "2025-10-01")
    date_labels = []
    date_keys = []
    for i in range(num_days_so_far):
        current_day = first_day_of_month + timedelta(days=i)
        date_labels.append(current_day.strftime('%b %d'))
        date_keys.append(current_day.strftime('%Y-%m-%d'))
        
    # Agregacja danych: { '2025-10-22': {'Projekt A': 3600, 'Projekt B': 1800}, ... }
    daily_project_summary = {}
    all_projects_in_month = set()
    
    # Używamy UTC do filtrowania miesiąca/roku, aby być spójnym z bazą
    now_utc = datetime.now(timezone.utc)
    current_month_utc = now_utc.month
    current_year_utc = now_utc.year
    
    for entry in TIME_ENTRIES_DB:
        # Filtruj wpisy: tylko bieżący użytkownik i bieżący miesiąc/rok (wg UTC)
        if (entry['user_id'] == current_user.id and
            entry['start_time'].year == current_year_utc and
            entry['start_time'].month == current_month_utc):
            
            # Klucz daty bierzemy z czasu lokalnego, aby pasował do osi X
            local_date_str = entry['start_time'].astimezone(tz=None).strftime('%Y-%m-%d')
            project = entry['project_name']
            duration = entry['duration_sec']
            
            all_projects_in_month.add(project)
            
            if local_date_str not in daily_project_summary:
                daily_project_summary[local_date_str] = {}
            if project not in daily_project_summary[local_date_str]:
                daily_project_summary[local_date_str][project] = 0
                
            daily_project_summary[local_date_str][project] += duration

    # Budowanie zestawów danych (dataset) dla Chart.js
    chart_datasets = []
    # Kolory dla kolejnych projektów
    colors = ['#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', '#9966FF', '#FF9F40', '#E7E9ED']

    for i, project_name in enumerate(sorted(list(all_projects_in_month))):
        color = colors[i % len(colors)]
        data_list = []
        
        # Dla każdego dnia na osi X...
        for date_key in date_keys:
            # ...znajdź dane dla tego dnia...
            day_data = daily_project_summary.get(date_key, {})
            # ...i dla tego konkretnego projektu (domyślnie 0)
            project_seconds = day_data.get(project_name, 0)
            # Konwertuj na godziny
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

    # --- 3. Renderowanie szablonu z oboma zestawami danych ---
    return render_template('report.html', 
                           report_data=report_data, 
                           chart_data=chart_data)

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
    print("ZAKTUALIZOWANO: Dodano miesięczny wykres kolumnowy do raportu.")
    print("Pliki szablonów 'layout.html' i 'report.html' zostały zaktualizowane.")
    print("Uruchamianie serwera Flask pod adresem: http://127.0.0.1:5000")
    print("Aby się zalogować, użyj:")
    print("  Email: mateusz.wator@timemasters.pl")
    print("  Hasło: superhaslo123")
    print("Naciśnij CTRL+C aby zatrzymać serwer.")
    print("="*50)
    
    # Uruchom aplikację
    app.run(debug=True)