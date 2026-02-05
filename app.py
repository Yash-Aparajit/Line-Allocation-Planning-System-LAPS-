from flask import Flask, render_template, request, redirect, url_for, flash, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import date
import pandas as pd
import math
import os
import shutil

app = Flask(__name__)
app.secret_key = "laps_secret_key"

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "laps.db")

app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{DB_PATH}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.login_view = "login"
login_manager.init_app(app)

# ---------------- MODELS ---------------- #

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True)
    password_hash = db.Column(db.String(200))
    role = db.Column(db.String(20))  # admin / developer

class Line(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True)

class Activity(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    line_id = db.Column(db.Integer, db.ForeignKey("line.id"))
    seq_no = db.Column(db.Integer)
    text = db.Column(db.String(200))
    time_sec = db.Column(db.Integer)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ---------------- INIT ---------------- #

@app.before_first_request
def init_db():
    db.create_all()

    if not User.query.first():
        admin = User(
            username="admin",
            password_hash=generate_password_hash("admin123"),
            role="admin"
        )
        dev = User(
            username="developer",
            password_hash=generate_password_hash("dev123"),
            role="developer"
        )
        db.session.add_all([admin, dev])
        db.session.commit()

# ---------------- AUTH ---------------- #

@app.route("/", methods=["GET", "POST"])
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = User.query.filter_by(username=request.form["username"]).first()
        if user and check_password_hash(user.password_hash, request.form["password"]):
            login_user(user)
            return redirect(url_for("line_master"))
        flash("Invalid credentials")
    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))

# ---------------- LINE MASTER ---------------- #

@app.route("/line-master", methods=["GET", "POST"])
@login_required
def line_master():
    lines = Line.query.all()

    if request.method == "POST":
        line_name = request.form["line_name"].strip()
        if line_name:
            db.session.add(Line(name=line_name))
            db.session.commit()
            flash("Line added")
        return redirect(url_for("line_master"))

    return render_template("line_master.html", lines=lines)

@app.route("/line/<int:line_id>/activities", methods=["GET", "POST"])
@login_required
def line_activities(line_id):
    line = Line.query.get_or_404(line_id)

    if request.method == "POST":
        seq = int(request.form["seq"])
        text = request.form["text"]
        time_sec = int(request.form["time_sec"])

        if time_sec <= 0:
            flash("Time must be > 0")
            return redirect(request.url)

        db.session.add(Activity(
            line_id=line.id,
            seq_no=seq,
            text=text,
            time_sec=time_sec
        ))
        db.session.commit()

    activities = Activity.query.filter_by(line_id=line.id).order_by(Activity.seq_no).all()
    total_wc = sum(a.time_sec for a in activities)

    return render_template(
        "line_activities.html",
        line=line,
        activities=activities,
        total_wc=total_wc
    )

# ---------------- DAILY PLAN ---------------- #

@app.route("/daily-plan", methods=["GET", "POST"])
@login_required
def daily_plan():
    lines = Line.query.all()
    result = []

    if request.method == "POST":
        shift_min = int(request.form["shift"])
        plan_date = request.form["date"]

        for line in lines:
            qty = request.form.get(f"qty_{line.id}")
            if qty and int(qty) > 0:
                allocation = compute_allocation(line.id, int(qty), shift_min)
                result.append(allocation)

    return render_template(
        "daily_plan.html",
        lines=lines,
        today=date.today(),
        result=result
    )

# ---------------- CORE LOGIC ---------------- #

def compute_allocation(line_id, plan_qty, shift_min):
    activities = Activity.query.filter_by(line_id=line_id).order_by(Activity.seq_no).all()
    wc = sum(a.time_sec for a in activities)

    shift_sec = shift_min * 60
    takt = shift_sec / plan_qty

    manpower = math.ceil(wc / takt)

    while True:
        buckets = [[] for _ in range(manpower)]
        times = [0] * manpower
        target = wc / manpower

        op = 0
        for act in activities:
            if times[op] + act.time_sec > target and op < manpower - 1:
                op += 1
            buckets[op].append(act)
            times[op] += act.time_sec

        if max(times) <= takt or manpower >= len(activities):
            break
        manpower += 1

    operators = []
    for i, acts in enumerate(buckets):
        t = sum(a.time_sec for a in acts)
        if t > takt:
            status = "over"
        elif t < 0.6 * takt:
            status = "under"
        else:
            status = "ok"

        operators.append({
            "name": f"OP{i+1}",
            "acts": acts,
            "time": t,
            "status": status
        })

    return {
        "line": Line.query.get(line_id).name,
        "plan": plan_qty,
        "shift": shift_min,
        "takt": round(takt, 2),
        "wc": wc,
        "manpower": manpower,
        "max_time": max(times),
        "operators": operators
    }

# ---------------- BACKUP / RESTORE ---------------- #

@app.route("/backup")
@login_required
def backup():
    backup_path = os.path.join(BASE_DIR, "laps_backup.db")
    shutil.copy(DB_PATH, backup_path)
    return send_file(backup_path, as_attachment=True)

@app.route("/restore", methods=["POST"])
@login_required
def restore():
    if current_user.role != "developer":
        return "Unauthorized", 403

    file = request.files["db"]
    file.save(DB_PATH)
    flash("Database restored. Restart app.")
    return redirect(url_for("line_master"))

# ---------------- RUN ---------------- #

if __name__ == "__main__":
    app.run(debug=True)
