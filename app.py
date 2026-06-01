"""
ResumeAI Pro - Flask Backend
Full-stack AI-powered resume checker with admin portal
"""

import os
import json
import uuid
import hashlib
from datetime import datetime, timedelta
from functools import wraps

from flask import Flask, request, jsonify, session, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_cors import CORS

# ── App Setup ──────────────────────────────────────────────────────────────────
app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = os.environ.get("SECRET_KEY", "resumeai-secret-key-change-in-prod")
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///resumeai.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=24)

db   = SQLAlchemy(app)
bcrypt = Bcrypt(app)
CORS(app, supports_credentials=True)

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

# ── Models ─────────────────────────────────────────────────────────────────────
class User(db.Model):
    id         = db.Column(db.Integer, primary_key=True)
    uid        = db.Column(db.String(36), unique=True, default=lambda: str(uuid.uuid4()))
    name       = db.Column(db.String(120), nullable=False)
    email      = db.Column(db.String(120), unique=True, nullable=False)
    password   = db.Column(db.String(200), nullable=False)
    is_admin   = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    checks     = db.relationship("ResumeCheck", backref="user", lazy=True)

    def to_dict(self):
        return {
            "id": self.id, "uid": self.uid, "name": self.name,
            "email": self.email, "is_admin": self.is_admin,
            "created_at": self.created_at.isoformat(),
            "total_checks": len(self.checks)
        }

class ResumeCheck(db.Model):
    id           = db.Column(db.Integer, primary_key=True)
    user_id      = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    filename     = db.Column(db.String(255))
    job_role     = db.Column(db.String(255))
    score        = db.Column(db.Float)
    ats_score    = db.Column(db.Float)
    result_json  = db.Column(db.Text)
    created_at   = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id, "filename": self.filename,
            "job_role": self.job_role, "score": self.score,
            "ats_score": self.ats_score,
            "result": json.loads(self.result_json) if self.result_json else {},
            "created_at": self.created_at.isoformat()
        }

class ActivityLog(db.Model):
    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    action     = db.Column(db.String(100))
    detail     = db.Column(db.String(500))
    ip_address = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# ── Helpers ────────────────────────────────────────────────────────────────────
def log_activity(action, detail="", user_id=None):
    try:
        entry = ActivityLog(
            user_id=user_id or session.get("user_id"),
            action=action, detail=detail,
            ip_address=request.remote_addr
        )
        db.session.add(entry)
        db.session.commit()
    except Exception:
        pass

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return jsonify({"error": "Authentication required"}), 401
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return jsonify({"error": "Authentication required"}), 401
        user = User.query.get(session["user_id"])
        if not user or not user.is_admin:
            return jsonify({"error": "Admin access required"}), 403
        return f(*args, **kwargs)
    return decorated

def analyze_resume_with_ai(resume_text: str, job_role: str) -> dict:
    """Call Anthropic API to analyze the resume."""
    import anthropic

    if not ANTHROPIC_API_KEY:
        return _mock_analysis(resume_text, job_role)

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    prompt = f"""You are an expert resume reviewer and ATS specialist. Analyze the following resume for the role of "{job_role}".

RESUME TEXT:
{resume_text[:4000]}

Return a JSON object (no markdown, pure JSON) with exactly this structure:
{{
  "overall_score": <0-100 number>,
  "ats_score": <0-100 number>,
  "summary": "<2-3 sentence overall assessment>",
  "sections": {{
    "contact": {{"score": <0-100>, "feedback": "<feedback>"}},
    "summary": {{"score": <0-100>, "feedback": "<feedback>"}},
    "experience": {{"score": <0-100>, "feedback": "<feedback>"}},
    "skills": {{"score": <0-100>, "feedback": "<feedback>"}},
    "education": {{"score": <0-100>, "feedback": "<feedback>"}}
  }},
  "strengths": ["<strength 1>", "<strength 2>", "<strength 3>"],
  "improvements": ["<improvement 1>", "<improvement 2>", "<improvement 3>"],
  "keywords_found": ["<keyword1>", "<keyword2>", "<keyword3>", "<keyword4>", "<keyword5>"],
  "keywords_missing": ["<keyword1>", "<keyword2>", "<keyword3>"],
  "action_items": ["<specific action 1>", "<specific action 2>", "<specific action 3>"]
}}"""

    try:
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}]
        )
        raw = message.content[0].text.strip()
        # Strip markdown fences if present
        raw = raw.replace("```json", "").replace("```", "").strip()
        return json.loads(raw)
    except Exception as e:
        return _mock_analysis(resume_text, job_role)

def _mock_analysis(resume_text: str, job_role: str) -> dict:
    """Fallback mock analysis when no API key is set."""
    word_count = len(resume_text.split())
    base = min(75, 40 + word_count // 10)
    return {
        "overall_score": base,
        "ats_score": base - 5,
        "summary": f"Your resume has been analyzed for the {job_role} position. The document shows moderate alignment with industry standards. Consider the recommendations below to improve your score.",
        "sections": {
            "contact": {"score": 90, "feedback": "Contact information is present and well-formatted."},
            "summary": {"score": 65, "feedback": "Professional summary could be more targeted to the role."},
            "experience": {"score": base, "feedback": "Work experience section needs stronger action verbs and quantifiable achievements."},
            "skills": {"score": 70, "feedback": "Good skills listed but could add more role-specific technical skills."},
            "education": {"score": 85, "feedback": "Education section is clear and complete."}
        },
        "strengths": [
            "Clear contact information", "Relevant work history",
            "Good educational background"
        ],
        "improvements": [
            "Add quantifiable achievements (e.g., 'Increased revenue by 30%')",
            "Include more keywords relevant to the job description",
            "Strengthen your professional summary"
        ],
        "keywords_found": ["management", "communication", "leadership", "analysis", "teamwork"],
        "keywords_missing": ["agile", "KPIs", "cross-functional", "stakeholder"],
        "action_items": [
            "Rewrite your summary to directly address the job requirements",
            "Add metrics to at least 3 bullet points in your experience section",
            "Include a dedicated skills section with role-specific technologies"
        ]
    }

def extract_text_from_upload(file_content: bytes, filename: str) -> str:
    """Extract plain text from uploaded file."""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if ext == "pdf":
        try:
            import PyPDF2, io
            reader = PyPDF2.PdfReader(io.BytesIO(file_content))
            return " ".join(p.extract_text() or "" for p in reader.pages)
        except Exception:
            return file_content.decode("utf-8", errors="ignore")
    elif ext in ("doc", "docx"):
        try:
            import docx, io
            doc = docx.Document(io.BytesIO(file_content))
            return " ".join(p.text for p in doc.paragraphs)
        except Exception:
            return file_content.decode("utf-8", errors="ignore")
    else:
        return file_content.decode("utf-8", errors="ignore")

# ── Auth Routes ────────────────────────────────────────────────────────────────
@app.route("/api/auth/register", methods=["POST"])
def register():
    data = request.get_json()
    name, email, password = data.get("name",""), data.get("email",""), data.get("password","")

    if not all([name, email, password]):
        return jsonify({"error": "All fields required"}), 400
    if User.query.filter_by(email=email).first():
        return jsonify({"error": "Email already registered"}), 409
    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters"}), 400

    hashed = bcrypt.generate_password_hash(password).decode("utf-8")
    user = User(name=name, email=email, password=hashed)
    db.session.add(user)
    db.session.commit()
    log_activity("register", f"New user: {email}", user.id)
    return jsonify({"message": "Account created successfully"}), 201

@app.route("/api/auth/login", methods=["POST"])
def login():
    data = request.get_json()
    email, password = data.get("email",""), data.get("password","")
    user = User.query.filter_by(email=email).first()

    if not user or not bcrypt.check_password_hash(user.password, password):
        return jsonify({"error": "Invalid credentials"}), 401

    session.permanent = True
    session["user_id"] = user.id
    user.last_login = datetime.utcnow()
    db.session.commit()
    log_activity("login", f"Login: {email}", user.id)
    return jsonify({"user": user.to_dict()})

@app.route("/api/auth/logout", methods=["POST"])
def logout():
    log_activity("logout")
    session.clear()
    return jsonify({"message": "Logged out"})

@app.route("/api/auth/me", methods=["GET"])
@login_required
def me():
    user = User.query.get(session["user_id"])
    return jsonify({"user": user.to_dict()})

# ── Resume Routes ──────────────────────────────────────────────────────────────
@app.route("/api/resume/check", methods=["POST"])
@login_required
def check_resume():
    job_role = request.form.get("job_role", "General")
    resume_text = request.form.get("resume_text", "")
    filename = "pasted_text.txt"

    if "file" in request.files:
        f = request.files["file"]
        filename = f.filename
        content = f.read()
        resume_text = extract_text_from_upload(content, filename)

    if not resume_text.strip():
        return jsonify({"error": "No resume content provided"}), 400

    result = analyze_resume_with_ai(resume_text, job_role)

    check = ResumeCheck(
        user_id=session["user_id"],
        filename=filename,
        job_role=job_role,
        score=result.get("overall_score", 0),
        ats_score=result.get("ats_score", 0),
        result_json=json.dumps(result)
    )
    db.session.add(check)
    db.session.commit()
    log_activity("resume_check", f"Checked: {filename} for {job_role}")
    return jsonify({"result": result, "check_id": check.id})

@app.route("/api/resume/history", methods=["GET"])
@login_required
def resume_history():
    checks = ResumeCheck.query.filter_by(user_id=session["user_id"])\
                              .order_by(ResumeCheck.created_at.desc()).limit(20).all()
    return jsonify({"history": [c.to_dict() for c in checks]})

# ── Admin Routes ───────────────────────────────────────────────────────────────
@app.route("/api/admin/stats", methods=["GET"])
@admin_required
def admin_stats():
    total_users   = User.query.count()
    total_checks  = ResumeCheck.query.count()
    today         = datetime.utcnow().date()
    checks_today  = ResumeCheck.query.filter(
        db.func.date(ResumeCheck.created_at) == today).count()
    new_users_today = User.query.filter(
        db.func.date(User.created_at) == today).count()
    avg_score = db.session.query(db.func.avg(ResumeCheck.score)).scalar() or 0

    recent_checks = ResumeCheck.query.order_by(
        ResumeCheck.created_at.desc()).limit(10).all()
    checks_data = []
    for c in recent_checks:
        u = User.query.get(c.user_id)
        checks_data.append({
            **c.to_dict(), "user_name": u.name if u else "Unknown",
            "user_email": u.email if u else ""
        })

    return jsonify({
        "stats": {
            "total_users": total_users,
            "total_checks": total_checks,
            "checks_today": checks_today,
            "new_users_today": new_users_today,
            "avg_score": round(avg_score, 1)
        },
        "recent_checks": checks_data
    })

@app.route("/api/admin/users", methods=["GET"])
@admin_required
def admin_users():
    users = User.query.order_by(User.created_at.desc()).all()
    return jsonify({"users": [u.to_dict() for u in users]})

@app.route("/api/admin/logs", methods=["GET"])
@admin_required
def admin_logs():
    logs = ActivityLog.query.order_by(ActivityLog.created_at.desc()).limit(100).all()
    result = []
    for l in logs:
        u = User.query.get(l.user_id) if l.user_id else None
        result.append({
            "id": l.id, "action": l.action, "detail": l.detail,
            "ip": l.ip_address, "created_at": l.created_at.isoformat(),
            "user_name": u.name if u else "Anonymous",
            "user_email": u.email if u else ""
        })
    return jsonify({"logs": result})

@app.route("/api/admin/toggle-admin/<int:uid>", methods=["POST"])
@admin_required
def toggle_admin(uid):
    user = User.query.get_or_404(uid)
    if user.id == session["user_id"]:
        return jsonify({"error": "Cannot modify your own admin status"}), 400
    user.is_admin = not user.is_admin
    db.session.commit()
    log_activity("toggle_admin", f"User {user.email} admin={user.is_admin}")
    return jsonify({"message": "Updated", "is_admin": user.is_admin})

# ── SPA Route ──────────────────────────────────────────────────────────────────
@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve_spa(path):
    return send_from_directory("templates", "index.html")

# ── Init ───────────────────────────────────────────────────────────────────────
def init_db():
    with app.app_context():
        db.create_all()
        # Create default admin if none exists
        if not User.query.filter_by(email="admin@resumeai.pro").first():
            hashed = bcrypt.generate_password_hash("Admin@123").decode("utf-8")
            admin = User(name="Admin", email="admin@resumeai.pro",
                         password=hashed, is_admin=True)
            db.session.add(admin)
            # Create a demo user
            demo_pw = bcrypt.generate_password_hash("Demo@123").decode("utf-8")
            demo = User(name="Demo User", email="demo@resumeai.pro", password=demo_pw)
            db.session.add(demo)
            db.session.commit()
            print("✓ Default admin created: admin@resumeai.pro / Admin@123")
            print("✓ Demo user created:  demo@resumeai.pro  / Demo@123")

if __name__ == "__main__":
    init_db()
    print("\n🚀 ResumeAI Pro running at http://localhost:5000\n")
    app.run(debug=True, port=5000)
