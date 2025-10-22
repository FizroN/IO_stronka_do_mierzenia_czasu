# app.py
import os
from datetime import datetime, timezone
from flask import Flask, render_template, redirect, url_for, request, flash, session
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy

# --- Templates (the exact strings you provided earlier) ---
TEMPLATE_DIR = 'templates'

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


def create_templates():
    if not os.path.exists(TEMPLATE_DIR):
        os.makedirs(TEMPLATE_DIR)
    templates_to_create = {
        'layout.html': LAYOUT_HTML,
        'login.html': LOGIN_HTML,
        'dashboard.html': DASHBOARD_HTML,
        'report.html': REPORT_HTML,
    }
    for filename, content in templates_to_create.items():
        filepath = os.path.join(TEMPLATE_DIR, filename)
        # Overwrite to ensure templates match code
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)


# --- Flask + SQLAlchemy config ---
app = Flask(__name__)
app.config['SECRET_KEY'] = 'bardzo-tajny-klucz-zmien-to-na-cos-innego'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///time_tracker.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# --- Flask-Login setup ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Musisz się zalogować, aby zobaczyć tę stronę.'
login_manager.login_message_category = 'error'


# --- Models ---
class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(200), unique=True, nullable=False)
    password_hash = db.Column(db.String(300), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    surname = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(50), nullable=False, default='Pracownik')

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Project(db.Model):
    __tablename__ = 'projects'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)


class TimeEntry(db.Model):
    __tablename__ = 'time_entries'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    start_time = db.Column(db.DateTime(timezone=True), nullable=False)
    end_time = db.Column(db.DateTime(timezone=True), nullable=True)
    duration_sec = db.Column(db.Integer, nullable=True)

    user = db.relationship('User', backref='time_entries')
    project = db.relationship('Project')


# --- User loader ---
@login_manager.user_loader
def load_user(user_id):
    if not user_id:
        return None
    return User.query.get(int(user_id))


# --- Helpers (DB-backed) ---
def get_active_session_entry(user_id):
    return TimeEntry.query.filter_by(user_id=user_id, end_time=None).first()


def stop_active_session(user_id):
    entry = get_active_session_entry(user_id)
    if entry:
        # ✅ Fix old naive datetimes (important!)
        if entry.start_time.tzinfo is None:
            entry.start_time = entry.start_time.replace(tzinfo=timezone.utc)

        entry.end_time = datetime.now(timezone.utc)
        duration = entry.end_time - entry.start_time
        entry.duration_sec = int(duration.total_seconds())
        db.session.commit()
        session.pop('active_entry_id', None)
        print(f"Stopped session {entry.id} for user {user_id}")
        return True
    return False


def format_duration(seconds):
    if seconds is None:
        return "W trakcie"
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{int(hours)}h {int(minutes)}m {int(seconds)}s"


# --- Routes ---
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
        if user and user.check_password(password):
            login_user(user)
            active = get_active_session_entry(user.id)
            if active:
                session['active_entry_id'] = active.id
            else:
                session.pop('active_entry_id', None)
            print(f"User {user.email} logged in.")
            return redirect(url_for('dashboard'))
        else:
            flash('Nieprawidłowy e-mail lub hasło.', 'error')
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    stop_active_session(current_user.id)
    logout_user()
    session.clear()
    flash('Zostałeś pomyślnie wylogowany.', 'success')
    return redirect(url_for('login'))


@app.route('/dashboard')
@login_required
def dashboard():
    active_entry = get_active_session_entry(current_user.id)
    active_project_name = None
    active_start_time = None
    if active_entry:
        active_project_name = active_entry.project.name if active_entry.project else 'Nieznany Projekt'
        active_start_time = active_entry.start_time.astimezone().replace(tzinfo=None)
        session['active_entry_id'] = active_entry.id
    else:
        session.pop('active_entry_id', None)

    projects_q = Project.query.all()
    # convert to dict like previous code expected (id -> project object)
    projects = {p.id: p for p in projects_q}

    return render_template('dashboard.html',
                           projects=projects,
                           active_project_name=active_project_name,
                           active_start_time=active_start_time)


@app.route('/start_work', methods=['POST'])
@login_required
def start_work():
    project_id = request.form.get('project_id')
    if not project_id:
        flash("Musisz wybrać projekt.", 'error')
        return redirect(url_for('dashboard'))
    project_id = int(project_id)
    project = Project.query.get(project_id)
    project_name = project.name if project else 'Nieznany'

    if stop_active_session(current_user.id):
        flash("Zakończono pracę nad poprzednim projektem.", 'success')

    new_entry = TimeEntry(
        user_id=current_user.id,
        project_id=project_id,
        start_time=datetime.now(timezone.utc),
        end_time=None,
        duration_sec=None
    )
    db.session.add(new_entry)
    db.session.commit()
    session['active_entry_id'] = new_entry.id

    flash(f"Rozpocząłeś pracę nad projektem: {project_name}", 'success')
    return redirect(url_for('dashboard'))


@app.route('/stop_work', methods=['POST'])
@login_required
def stop_work():
    if stop_active_session(current_user.id):
        flash("Zatrzymałeś pracę.", 'success')
    else:
        flash("Nie pracowałeś nad żadnym projektem.", 'error')
    return redirect(url_for('dashboard'))


@app.route('/report')
@login_required
def report():
    user_entries = []
    total_today_sec = 0
    today_local_date = datetime.now(timezone.utc).astimezone().date()

    entries = TimeEntry.query.filter_by(user_id=current_user.id).order_by(TimeEntry.start_time.desc()).all()
    for entry in entries:
        project_name = entry.project.name if entry.project else 'Nieznany'
        start_local = entry.start_time.astimezone()
        if entry.end_time:
            end_local = entry.end_time.astimezone()
            end_str = end_local.strftime('%H:%M:%S')
        else:
            end_str = "W trakcie"

        if entry.duration_sec is not None and start_local.date() == today_local_date:
            total_today_sec += entry.duration_sec

        formatted_entry = {
            'project_name': project_name,
            'date': start_local.strftime('%Y-%m-%d'),
            'start': start_local.strftime('%H:%M:%S'),
            'end': end_str,
            'duration': format_duration(entry.duration_sec)
        }
        user_entries.append(formatted_entry)

    report_data = {
        'user_name': current_user.name,
        'user_surname': current_user.surname,
        'entries': user_entries,
        'total_today': format_duration(total_today_sec)
    }
    return render_template('report.html', report_data=report_data)


@app.template_filter('format_duration')
def _jinja_format_duration(seconds):
    return format_duration(seconds)


# --- DB initialization & seed ---
def init_db_and_seed():
    db.create_all()

    # seed projects
    if Project.query.count() == 0:
        defaults = [
            Project(name="Projekt Alfa"),
            Project(name="Projekt Delta"),
            Project(name="Zadania Wewnętrzne")
        ]
        db.session.add_all(defaults)
        db.session.commit()
        print("Seeded default projects.")

    # seed users
    if User.query.count() == 0:
        u1 = User(
            email="mateusz.wator@timemasters.pl",
            password_hash=generate_password_hash("superhaslo123", method="pbkdf2:sha256"),
            name="Mateusz",
            surname="Wątor",
            role="Pracownik"
        )
        u2 = User(
            email="jakub.zak@timemasters.pl",
            password_hash=generate_password_hash("haslo456", method="pbkdf2:sha256"),
            name="Jakub",
            surname="Żak",
            role="Pracownik"
        )
        db.session.add_all([u1, u2])
        db.session.commit()
        print("Seeded default users.")


# --- Run ---
if __name__ == "__main__":
    with app.app_context():  # ✅ This ensures a proper Flask context
        init_db_and_seed()
    app.run(debug=True)

    print("=" * 50)
    print("Aplikacja Time Tracker (z SQLite + SQLAlchemy) jest gotowa.")
    print("Uruchamianie serwera Flask pod adresem: http://127.0.0.1:5000")
    print("Przykładowe loginy:")
    print("  Email: mateusz.wator@timemasters.pl  Password: superhaslo123")
    print("  Email: jakub.zak@timemasters.pl       Password: haslo456")
    print("=" * 50)

    app.run(debug=True)
