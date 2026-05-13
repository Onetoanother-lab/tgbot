"""
admin_web.py — Lightweight Flask admin dashboard.

Runs in a daemon thread alongside the Telegram bot.
Shares the same SQLite database.

Endpoints:
  GET  /              → login page
  POST /login         → authenticate
  GET  /dashboard     → stats overview
  GET  /submissions   → paginated submissions table
  GET  /api/chart     → JSON data for charts
  GET  /api/export    → CSV download
  GET  /logout        → clear session

Auth: single secret token stored in env ADMIN_PASSWORD.
"""

import csv
import io
import json
import logging
import os
import threading
from datetime import datetime, timedelta
from functools import wraps

logger = logging.getLogger(__name__)

ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
FLASK_SECRET   = os.getenv("FLASK_SECRET", "homeworkbot-secret-key-change-me")

try:
    from flask import (
        Flask, render_template_string, request, redirect,
        url_for, session, jsonify, send_file, Response,
    )
    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False
    logger.warning("Flask not installed — web dashboard disabled.")


# ── HTML templates (inline to keep the project single-directory) ──────────────

BASE_HTML = """<!DOCTYPE html>
<html lang="uz">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>HomeworkBot Admin</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
  body { background: #f0f2f5; font-family: 'Segoe UI', sans-serif; }
  .sidebar { min-height: 100vh; background: #1a1a2e; }
  .sidebar a { color: #ccc; text-decoration: none; display: block; padding: 10px 20px; }
  .sidebar a:hover, .sidebar a.active { color: #fff; background: #e94560; border-radius: 6px; }
  .sidebar .brand { color: #fff; font-size: 1.3rem; font-weight: 700; padding: 20px; }
  .stat-card { border-radius: 12px; border: none; box-shadow: 0 2px 12px rgba(0,0,0,.08); }
  .stat-number { font-size: 2.2rem; font-weight: 700; }
  .badge-pill { font-size: .75rem; border-radius: 50px; }
  table td, table th { vertical-align: middle !important; }
</style>
</head>
<body>
<div class="container-fluid">
<div class="row">
  <nav class="col-md-2 sidebar d-none d-md-block py-3">
    <div class="brand">📚 HomeworkBot</div>
    <a href="/dashboard" class="{{ 'active' if page=='dashboard' else '' }}">📊 Dashboard</a>
    <a href="/submissions" class="{{ 'active' if page=='submissions' else '' }}">📄 Topshiriqlar</a>
    <a href="/students" class="{{ 'active' if page=='students' else '' }}">👤 O'quvchilar</a>
    <a href="/logs" class="{{ 'active' if page=='logs' else '' }}">📋 Loglar</a>
    <hr style="border-color:#444">
    <a href="/export_csv">⬇️ CSV Eksport</a>
    <a href="/logout">🔐 Chiqish</a>
  </nav>
  <main class="col-md-10 py-4">
    {% block content %}{% endblock %}
  </main>
</div>
</div>
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>"""

LOGIN_HTML = """<!DOCTYPE html>
<html lang="uz">
<head>
<meta charset="UTF-8">
<title>HomeworkBot — Kirish</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
<style>
  body { background: #1a1a2e; display: flex; align-items: center; justify-content: center; min-height: 100vh; }
  .card { border-radius: 16px; border: none; box-shadow: 0 8px 32px rgba(0,0,0,.2); }
</style>
</head>
<body>
<div class="card p-5" style="width: 380px">
  <h2 class="text-center mb-1">📚 HomeworkBot</h2>
  <p class="text-center text-muted mb-4">Admin Panel</p>
  {% if error %}<div class="alert alert-danger">{{ error }}</div>{% endif %}
  <form method="post">
    <div class="mb-3">
      <label class="form-label">Parol</label>
      <input type="password" name="password" class="form-control form-control-lg" autofocus>
    </div>
    <button class="btn btn-danger w-100 btn-lg">Kirish</button>
  </form>
</div>
</body>
</html>"""

DASHBOARD_HTML = """{% extends base %}
{% block content %}
<h4 class="fw-bold mb-4">📊 Umumiy Ko'rinish</h4>
<div class="row g-3 mb-4">
  {% for label, value, color in stats_cards %}
  <div class="col-6 col-md-3">
    <div class="card stat-card p-3 border-start border-4 border-{{ color }}">
      <div class="stat-number text-{{ color }}">{{ value }}</div>
      <div class="text-muted small">{{ label }}</div>
    </div>
  </div>
  {% endfor %}
</div>
<div class="row g-3">
  <div class="col-md-7">
    <div class="card p-3">
      <h6 class="fw-bold">📈 Kunlik Topshiriqlar (14 kun)</h6>
      <canvas id="subChart" height="120"></canvas>
    </div>
  </div>
  <div class="col-md-5">
    <div class="card p-3">
      <h6 class="fw-bold">🏆 Baho Taqsimoti</h6>
      <canvas id="gradeChart" height="180"></canvas>
    </div>
  </div>
</div>
<script>
fetch('/api/chart').then(r=>r.json()).then(data=>{
  new Chart(document.getElementById('subChart'), {
    type: 'line',
    data: { labels: data.days.map(d=>d.date), datasets:[{
      label:'Topshiriqlar', data: data.days.map(d=>d.count),
      borderColor:'#e94560', backgroundColor:'rgba(233,69,96,.1)',
      fill:true, tension:0.4
    }]},
    options:{ plugins:{legend:{display:false}}, scales:{y:{beginAtZero:true}} }
  });
  new Chart(document.getElementById('gradeChart'), {
    type: 'doughnut',
    data: { labels: data.grades.map(g=>g.grade), datasets:[{
      data: data.grades.map(g=>g.count),
      backgroundColor:['#2ecc71','#27ae60','#f39c12','#e67e22','#e74c3c']
    }]},
    options:{ plugins:{legend:{position:'bottom'}} }
  });
});
</script>
{% endblock %}"""

SUBMISSIONS_HTML = """{% extends base %}
{% block content %}
<div class="d-flex justify-content-between align-items-center mb-3">
  <h4 class="fw-bold mb-0">📄 Topshiriqlar</h4>
  <form class="d-flex gap-2" method="get">
    <input name="q" value="{{ q }}" class="form-control" placeholder="Ism / guruh qidirish…" style="width:220px">
    <select name="status" class="form-select" style="width:160px">
      <option value="">Barcha holat</option>
      <option value="pending" {{ 'selected' if status=='pending' }}>Kutilmoqda</option>
      <option value="reviewed" {{ 'selected' if status=='reviewed' }}>Tekshirildi</option>
    </select>
    <button class="btn btn-primary">🔍</button>
  </form>
</div>
<div class="card">
<table class="table table-hover mb-0">
<thead class="table-dark">
  <tr><th>#</th><th>O'quvchi</th><th>Guruh</th><th>Sana</th><th>Baho</th><th>Holat</th></tr>
</thead>
<tbody>
{% for s in subs %}
<tr>
  <td><code>#{{ s.id }}</code></td>
  <td>{{ s.student_name }}</td>
  <td><span class="badge bg-secondary">{{ s.group_name }}</span></td>
  <td>{{ s.submitted_at[:10] }}</td>
  <td>{{ s.grade or '—' }}</td>
  <td>
    {% if s.status == 'reviewed' %}
      <span class="badge bg-success">✅ Tekshirildi</span>
    {% else %}
      <span class="badge bg-warning text-dark">🕐 Kutilmoqda</span>
    {% endif %}
  </td>
</tr>
{% else %}
<tr><td colspan="6" class="text-center text-muted py-4">Topshiriq topilmadi</td></tr>
{% endfor %}
</tbody>
</table>
</div>
<div class="d-flex justify-content-between mt-3">
  <small class="text-muted">{{ total }} ta natija</small>
  <nav>
    <ul class="pagination mb-0">
      {% if page > 1 %}
      <li class="page-item"><a class="page-link" href="?q={{ q }}&status={{ status }}&page={{ page-1 }}">‹</a></li>
      {% endif %}
      <li class="page-item active"><a class="page-link" href="#">{{ page }}/{{ total_pages }}</a></li>
      {% if page < total_pages %}
      <li class="page-item"><a class="page-link" href="?q={{ q }}&status={{ status }}&page={{ page+1 }}">›</a></li>
      {% endif %}
    </ul>
  </nav>
</div>
{% endblock %}"""

STUDENTS_HTML = """{% extends base %}
{% block content %}
<h4 class="fw-bold mb-4">👤 O'quvchilar</h4>
<div class="card">
<table class="table table-hover mb-0">
<thead class="table-dark">
  <tr><th>O'quvchi</th><th>Guruh</th><th>Jami</th><th>Tekshirildi</th><th>O'rtacha</th></tr>
</thead>
<tbody>
{% for s in students %}
<tr>
  <td>{{ s.student_name }}</td>
  <td><span class="badge bg-secondary">{{ s.group_name }}</span></td>
  <td>{{ s.total }}</td>
  <td>{{ s.reviewed }}</td>
  <td>{{ s.avg if s.avg else '—' }}</td>
</tr>
{% else %}
<tr><td colspan="5" class="text-center text-muted py-4">O'quvchi topilmadi</td></tr>
{% endfor %}
</tbody>
</table>
</div>
{% endblock %}"""

LOGS_HTML = """{% extends base %}
{% block content %}
<h4 class="fw-bold mb-4">📋 Faoliyat Loglari</h4>
<div class="card">
<table class="table table-sm mb-0">
<thead class="table-dark">
  <tr><th>Vaqt</th><th>Harakat</th><th>Foydalanuvchi</th><th>Tafsilot</th></tr>
</thead>
<tbody>
{% for log in logs %}
<tr>
  <td><small>{{ log.created_at[:16] }}</small></td>
  <td><code>{{ log.action }}</code></td>
  <td>{{ log.user_id or '—' }}</td>
  <td><small>{{ log.details or '' }}</small></td>
</tr>
{% endfor %}
</tbody>
</table>
</div>
{% endblock %}"""


def create_app():
    if not FLASK_AVAILABLE:
        return None

    import database as db

    app = Flask(__name__)
    app.secret_key = FLASK_SECRET

    def login_required(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if not session.get("logged_in"):
                return redirect(url_for("login"))
            return f(*args, **kwargs)
        return decorated

    # ── Login ─────────────────────────────────────────────────────────────────

    @app.route("/", methods=["GET"])
    def index():
        return redirect(url_for("login"))

    @app.route("/login", methods=["GET", "POST"])
    def login():
        error = None
        if request.method == "POST":
            if request.form.get("password") == ADMIN_PASSWORD:
                session["logged_in"] = True
                return redirect(url_for("dashboard"))
            error = "Noto'g'ri parol"
        return render_template_string(LOGIN_HTML, error=error)

    @app.route("/logout")
    def logout():
        session.clear()
        return redirect(url_for("login"))

    # ── Dashboard ─────────────────────────────────────────────────────────────

    @app.route("/dashboard")
    @login_required
    def dashboard():
        stats = db.get_global_stats()
        cards = [
            ("Jami topshiriqlar", stats["total"],    "primary"),
            ("Kutilmoqda",        stats["pending"],  "warning"),
            ("Tekshirildi",       stats["reviewed"], "success"),
            ("Faol guruhlar",     stats["groups"],   "info"),
        ]
        return render_template_string(
            DASHBOARD_HTML,
            base=BASE_HTML, page="dashboard", stats_cards=cards,
        )

    # ── Submissions ───────────────────────────────────────────────────────────

    @app.route("/submissions")
    @login_required
    def submissions():
        q      = request.args.get("q", "")
        status = request.args.get("status", "")
        page   = int(request.args.get("page", 1))
        size   = 20

        if q or status:
            all_subs = db.search_submissions(q or status)
            if status and not q:
                all_subs = [s for s in db.get_all_submissions() if s["status"] == status]
        else:
            all_subs = db.get_all_submissions()

        total       = len(all_subs)
        total_pages = max(1, (total + size - 1) // size)
        page_subs   = all_subs[(page-1)*size : page*size]

        return render_template_string(
            SUBMISSIONS_HTML,
            base=BASE_HTML, page="submissions",
            subs=page_subs, q=q, status=status,
            total=total, total_pages=total_pages, page_num=page,
            **{"page": page},
        )

    # ── Students ──────────────────────────────────────────────────────────────

    @app.route("/students")
    @login_required
    def students():
        conn = db.get_connection()
        rows = conn.execute("""
            SELECT student_name, group_name,
                   COUNT(*) AS total,
                   SUM(CASE WHEN status='reviewed' THEN 1 ELSE 0 END) AS reviewed,
                   ROUND(AVG(CASE
                     WHEN grade="⭐ A'lo" THEN 5
                     WHEN grade='👍 Yaxshi' THEN 4
                     WHEN grade='📝 Qoniqarli' THEN 3
                     WHEN grade='⚠️ Yaxshilash kerak' THEN 2
                     WHEN grade='❌ Bajarilmagan' THEN 1
                     ELSE NULL END), 1) AS avg
            FROM submissions
            GROUP BY student_name, group_name
            ORDER BY student_name
        """).fetchall()
        conn.close()
        return render_template_string(
            STUDENTS_HTML,
            base=BASE_HTML, page="students",
            students=[dict(r) for r in rows],
        )

    # ── Logs ──────────────────────────────────────────────────────────────────

    @app.route("/logs")
    @login_required
    def logs():
        entries = db.get_recent_logs(100)
        return render_template_string(
            LOGS_HTML,
            base=BASE_HTML, page="logs", logs=entries,
        )

    # ── Chart API ─────────────────────────────────────────────────────────────

    @app.route("/api/chart")
    @login_required
    def chart_data():
        days   = db.get_submissions_per_day(14)
        grades = db.get_grade_distribution()
        # Strip emojis from grade labels for Chart.js
        import re
        clean_grades = [
            {"grade": re.sub(r"[^\x00-\x7F]+", "", g["grade"]).strip(), "count": g["count"]}
            for g in grades
        ]
        return jsonify({"days": days, "grades": clean_grades})

    # ── CSV export ────────────────────────────────────────────────────────────

    @app.route("/export_csv")
    @login_required
    def export_csv():
        subs   = db.get_all_submissions()
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "id","student_name","group_name","status","grade",
            "feedback","submitted_at","reviewed_at",
        ])
        for s in subs:
            writer.writerow([
                s["id"], s["student_name"], s["group_name"], s["status"],
                s.get("grade",""), s.get("feedback",""),
                s["submitted_at"], s.get("reviewed_at",""),
            ])
        output.seek(0)
        return Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition":
                     f'attachment; filename=submissions_{datetime.now().strftime("%Y%m%d")}.csv'}
        )

    return app


def start_web_server():
    """Start Flask in a daemon thread. Call once from main()."""
    if not FLASK_AVAILABLE:
        logger.warning("Flask unavailable — web dashboard not started.")
        return

    app  = create_app()
    port = int(os.getenv("ADMIN_PORT", 5000))

    def run():
        app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

    t = threading.Thread(target=run, daemon=True, name="web-dashboard")
    t.start()
    logger.info("Web dashboard started on port %s", port)