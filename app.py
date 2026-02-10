import math
import os
import shutil
import io
import pandas as pd

from flask import Flask, render_template, request, redirect, url_for, flash, send_file, Response
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import date, datetime
from sqlalchemy.exc import IntegrityError


# ---------------- APP SETUP ---------------- #

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
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False)

class Line(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)

class Activity(db.Model):
    __table_args__ = (
        db.UniqueConstraint('line_id', 'seq_no', name='unique_line_seq'),
    )

    id = db.Column(db.Integer, primary_key=True)
    line_id = db.Column(db.Integer, db.ForeignKey("line.id"), nullable=False)
    seq_no = db.Column(db.Integer, nullable=False)
    text = db.Column(db.String(200), nullable=False)
    time_sec = db.Column(db.Integer, nullable=False)


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# ---------------- DB INIT (FLASK 3 SAFE) ---------------- #

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
        try:
            db.session.add_all([admin, dev])
            db.session.commit()
        except Exception:
            db.session.rollback()

with app.app_context():
    init_db()

# ---------------- AUTH ---------------- #

@app.route("/", methods=["GET", "POST"])
@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("daily_plan"))
    if request.method == "POST":
        user = User.query.filter_by(username=request.form["username"]).first()
        if user and check_password_hash(user.password_hash, request.form["password"]):
            login_user(user)
            return redirect(url_for("line_master"))
        flash("Invalid username or password", "danger")
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
    lines = Line.query.order_by(Line.name).all()

    if request.method == "POST":
        name = request.form["line_name"].strip()
        if name:
            try:
                db.session.add(Line(name=name))
                db.session.commit()
                flash("Line added successfully", "success")
            except Exception as e:
                db.session.rollback()
                flash("Error saving line. It may already exist.", "danger")
        return redirect(url_for("line_master"))

    return render_template("line_master.html", lines=lines)

@app.route("/line/<int:line_id>/activities", methods=["GET", "POST"])
@login_required
def line_activities(line_id):
    line = Line.query.get_or_404(line_id)

    if request.method == "POST":
        seq = int(request.form["seq"])
        text = request.form["text"].strip()
        time_sec = int(request.form["time_sec"])

        if time_sec <= 0:
            flash("Time must be greater than zero", "danger")
            return redirect(request.url)

        try:
            db.session.add(Activity(
                line_id=line.id,
                seq_no=seq,
                text=text,
                time_sec=time_sec
            ))
            db.session.commit()
            flash("Activity added successfully", "success")
        except IntegrityError:
            db.session.rollback()
            flash("Duplicate sequence number for this line.", "danger")
        except Exception:
            db.session.rollback()
            flash("Error saving activity.", "danger")


    activities = Activity.query.filter_by(line_id=line.id).order_by(Activity.seq_no).all()
    total_wc = sum(a.time_sec for a in activities)

    return render_template(
        "line_activities.html",
        line=line,
        activities=activities,
        total_wc=total_wc
    )


# ---------------- LINE MASTER: EXCEL TEMPLATE ---------------- #

@app.route("/line-master/template")
@login_required
def download_line_template():
    df = pd.DataFrame(columns=[
        "activity_seq_no",
        "activity_text",
        "time_sec"
    ])

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="Activities")

    output.seek(0)
    return send_file(
        output,
        as_attachment=True,
        download_name="line_activity_template.xlsx"
    )

# ---------------- LINE MASTER: EXPORT ---------------- #

@app.route("/line/<int:line_id>/export")
@login_required
def export_line_activities(line_id):
    line = Line.query.get_or_404(line_id)
    activities = Activity.query.filter_by(line_id=line.id).order_by(Activity.seq_no).all()

    data = [{
        "activity_seq_no": a.seq_no,
        "activity_text": a.text,
        "time_sec": a.time_sec
    } for a in activities]

    df = pd.DataFrame(data)

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name=line.name)

    output.seek(0)
    return send_file(
        output,
        as_attachment=True,
        download_name=f"{line.name}_activities.xlsx"
    )

# ---------------- LINE MASTER: IMPORT ---------------- #

@app.route("/line/<int:line_id>/import", methods=["POST"])
@login_required
def import_line_activities(line_id):
    line = Line.query.get_or_404(line_id)
    file = request.files.get("file")

    if not file:
        flash("No file uploaded", "danger")
        return redirect(url_for("line_activities", line_id=line.id))

    try:
        df = pd.read_excel(file)
    except Exception:
        flash("Invalid Excel file", "danger")
        return redirect(url_for("line_activities", line_id=line.id))

    required_cols = ["activity_seq_no", "activity_text", "time_sec"]
    if list(df.columns) != required_cols:
        flash("Excel format mismatch. Use the provided template.", "danger")
        return redirect(url_for("line_activities", line_id=line.id))

    # ---- VALIDATIONS ---- #
    if df.isnull().any().any():
        flash("Missing values found in Excel", "danger")
        return redirect(url_for("line_activities", line_id=line.id))

    if (df["time_sec"] <= 0).any():
        flash("Time must be greater than zero", "danger")
        return redirect(url_for("line_activities", line_id=line.id))

    seq = df["activity_seq_no"].astype(int).tolist()
    if seq != list(range(min(seq), min(seq) + len(seq))):
        flash("Sequence must be continuous and increasing", "danger")
        return redirect(url_for("line_activities", line_id=line.id))

    # ---- CLEAN OVERWRITE ---- #
    Activity.query.filter_by(line_id=line.id).delete(synchronize_session=False)

    for _, row in df.iterrows():
        db.session.add(Activity(
            line_id=line.id,
            seq_no=int(row["activity_seq_no"]),
            text=str(row["activity_text"]),
            time_sec=int(row["time_sec"])
        ))

    try:
        db.session.commit()
        flash("Activities imported successfully", "success")
    except IntegrityError:
        db.session.rollback()
        flash("Duplicate sequence numbers found in import.", "danger")
    except Exception:
        db.session.rollback()
        flash("Error importing activities.", "danger")

    return redirect(url_for("line_activities", line_id=line.id))

# ---------------- LINE MASTER: DELETE ---------------- #

@app.route("/activity/<int:activity_id>/delete", methods=["POST"])
@login_required
def delete_activity(activity_id):
    act = Activity.query.get_or_404(activity_id)
    line_id = act.line_id
    try:
        db.session.delete(act)
        db.session.commit()
        flash("Activity deleted", "warning")
    except Exception:
        db.session.rollback()
        flash("Error deleting activity.", "danger")

    return redirect(url_for("line_activities", line_id=line_id))

# ---------------- DAILY PLAN ---------------- #

@app.route("/daily-plan", methods=["GET", "POST"])
@login_required
def daily_plan():
    lines = Line.query.all()
    result = []

    if request.method == "POST":
        try:
            shift_min = int(request.form.get("shift", 0))
            line_id = int(request.form.get("line_id", 0))
            plan_qty = int(request.form.get("plan_qty", 0))

            if shift_min <= 0 or plan_qty <= 0:
                raise ValueError

        except (ValueError, TypeError):
            flash("Invalid input values.", "danger")
            return redirect(url_for("daily_plan"))

        result.append(
            compute_allocation(line_id, plan_qty, shift_min)
        )

    return render_template(
        "daily_plan.html",
        lines=lines,
        today=date.today(),
        result=result
    )

# ---------------- EXPORT DAILY PLAN (EXCEL) ---------------- #

@app.route("/export/daily-plan", methods=["POST"])
@login_required
def export_daily_plan():
    shift_min = int(request.form["shift"])
    line_id = int(request.form["line_id"])
    plan_qty = int(request.form["plan_qty"])

    r = compute_allocation(line_id, plan_qty, shift_min)

    rows = []
    for op in r["operators"]:
        rows.append({
            "Operator": op["name"],
            "Activities": " | ".join(
                f"{a.seq_no}. {a.text}" for a in op["acts"]
            ),
            "Total Time (sec)": op["time"],
            "Status": op["status"].upper()
        })

    df = pd.DataFrame(rows)

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        sheet_name = r["line"][:31]
        df.to_excel(writer, index=False, sheet_name=sheet_name)

    output.seek(0)
    return send_file(
        output,
        as_attachment=True,
        download_name=f"{r['line']}_Daily_Allocation.xlsx"
    )

# ---------------- PRINT DAILY PLAN ---------------- #

@app.route("/print/daily-plan", methods=["POST"])
@login_required
def print_daily_plan():
    shift_min = int(request.form["shift"])
    line_id = int(request.form["line_id"])
    plan_qty = int(request.form["plan_qty"])

    result = [
        compute_allocation(line_id, plan_qty, shift_min)
    ]

    return render_template("print_daily_plan.html", result=result)


# ---------------- CORE LOGIC ---------------- #

def compute_allocation(line_id, plan_qty, shift_min):
    activities = Activity.query.filter_by(line_id=line_id).order_by(Activity.seq_no).all()
    line_obj = Line.query.get(line_id)
    line_name = line_obj.name if line_obj else "Unknown Line"
    if not activities:
        return {
            "line": line_name,
            "plan": plan_qty,
            "shift": shift_min,
            "takt": 0,
            "wc": 0,
            "manpower_used": 0,
            "operators": [],
            "error": "No activities defined for this line."
        }
    wc = sum(a.time_sec for a in activities)

    shift_sec = shift_min * 60
    takt = shift_sec / plan_qty
    manpower = math.ceil(wc / takt)
    manpower = min(manpower, len(activities))

    LOWER_BOUND = takt - 10
    UPPER_BOUND = takt + 2

    while True:
        buckets = [[] for _ in range(manpower)]
        times = [0] * manpower

        op = 0
        for act in activities:
            if times[op] + act.time_sec > UPPER_BOUND and op < manpower - 1:
                op += 1

            buckets[op].append(act)
            times[op] += act.time_sec

        if max(times) <= UPPER_BOUND or manpower >= len(activities):
            break

        manpower += 1

    operators = []
    for i, acts in enumerate(buckets):
        t = sum(a.time_sec for a in acts)
        status = "ok"
        if t > takt:
            status = "over"
        elif t < 0.6 * takt:
            status = "under"

        if t > 0:
            operators.append({
                "name": f"OP{i+1}",
                "acts": acts,
                "time": t,
                "status": status
            })

    return {
        "line": line_name,
        "plan": plan_qty,
        "shift": shift_min,
        "takt": round(takt, 2),
        "wc": wc,
        "manpower_used": len(operators),
        "operators": operators
    }


# ---------------- BACKUP / RESTORE ---------------- #

@app.route("/backup")
@login_required
def backup():
    now = datetime.now()
    date_str = now.strftime("%d-%m-%Y")   # Indian date 
    filename = f"LAPS_Backup_{date_str}.db"

    return send_file(
        DB_PATH,
        as_attachment=True,
        download_name=filename
    )

@app.route("/restore", methods=["GET", "POST"])
@login_required
def restore_page():
    if current_user.role != "developer":
        return "Unauthorized", 403

    if request.method == "POST":
        file = request.files.get("db")
        if not file:
            flash("No backup file selected", "danger")
            return redirect(request.url)

        file.save(DB_PATH)
        flash("Database restored successfully. Please restart the app.", "warning")
        return redirect(url_for("line_master"))

    return render_template("restore.html")

# ---------------- HELP PAGE ---------------- #

@app.route("/help")
@login_required
def help_page():
    return render_template("help.html")

# ---------------- CHANGE PASSWORD PAGE ---------------- #

@app.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    if request.method == "POST":
        current_pw = request.form["current_password"]
        new_pw = request.form["new_password"]
        confirm_pw = request.form["confirm_password"]

        if not check_password_hash(current_user.password_hash, current_pw):
            flash("Current password is incorrect", "danger")
            return redirect(request.url)

        if new_pw != confirm_pw:
            flash("New passwords do not match", "danger")
            return redirect(request.url)

        try:
            current_user.password_hash = generate_password_hash(new_pw)
            db.session.commit()
            flash("Password updated successfully", "success")
        except Exception:
            db.session.rollback()
            flash("Error updating password.", "danger")

        return redirect(url_for("daily_plan"))

    return render_template("change_password.html")

# ---------------- PASSWORD RESET PAGE ---------------- #

@app.route("/reset-password", methods=["GET", "POST"])
@login_required
def reset_password():
    if current_user.role != "developer":
        return "Unauthorized", 403

    users = User.query.all()

    if request.method == "POST":
        user_id = int(request.form["user_id"])
        new_pw = request.form["new_password"]

        user = User.query.get_or_404(user_id)
        try:
            user.password_hash = generate_password_hash(new_pw)
            db.session.commit()
            flash(f"Password reset for user '{user.username}'", "warning")
        except Exception:
            db.session.rollback()
            flash("Error resetting password.", "danger")

        return redirect(url_for("line_master"))

    return render_template("reset_password.html", users=users)

# ---------------- RUN ---------------- #

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050, debug=False)
