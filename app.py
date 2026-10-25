import os
import re
import secrets
import sqlite3
import tempfile
from pathlib import Path

import spacy
from spacy.matcher import PhraseMatcher
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory, send_file, abort
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-local-demo-secret")
app.config["MAX_CONTENT_LENGTH"] = 4 * 1024 * 1024  # Keep uploads below Vercel's request-body limit.
ALLOWED_EXTENSIONS = {"txt", "pdf", "docx"}
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()

# On Vercel, use /tmp for temporary uploaded files. Locally, use the project uploads folder.
if os.environ.get("VERCEL"):
    UPLOAD_FOLDER = Path(tempfile.gettempdir()) / "resume_filter_uploads"
else:
    UPLOAD_FOLDER = Path("uploads")
UPLOAD_FOLDER.mkdir(exist_ok=True)

# spaCy performs NLP tokenization and phrase matching. No model download is required.
nlp = spacy.blank("en")
SKILL_ALIASES = {
    "Machine Learning": ["machine learning", "machine-learning", "ml"],
    "Deep Learning": ["deep learning", "deep-learning", "dl"],
    "Artificial Intelligence": ["artificial intelligence", "ai"],
    "Python": ["python"], "Java": ["java"], "JavaScript": ["javascript", "js"],
    "HTML": ["html"], "CSS": ["css"], "Flask": ["flask"], "Django": ["django"],
    "SQL": ["sql", "structured query language"], "Data Analysis": ["data analysis", "data analytics"],
    "Data Science": ["data science"], "Pandas": ["pandas"], "NumPy": ["numpy"],
    "TensorFlow": ["tensorflow"], "PyTorch": ["pytorch"],
    "Natural Language Processing": ["natural language processing", "nlp"],
    "Computer Vision": ["computer vision"], "Excel": ["excel", "microsoft excel"],
    "Power BI": ["power bi", "powerbi"], "Tableau": ["tableau"],
    "C++": ["c++"], "C#": ["c#"], "Git": ["git", "github"],
    "Communication": ["communication", "communication skills"],
    "Project Management": ["project management"],
}
matcher = PhraseMatcher(nlp.vocab, attr="LOWER")
for skill, aliases in SKILL_ALIASES.items():
    matcher.add(skill, [nlp.make_doc(alias) for alias in aliases])


def connect_db():
    """Use PostgreSQL when DATABASE_URL is set (deployment), SQLite for local testing."""
    if DATABASE_URL:
        import psycopg
        from psycopg.rows import dict_row
        return psycopg.connect(DATABASE_URL, row_factory=dict_row), True
    connection = sqlite3.connect("users.db")
    connection.row_factory = sqlite3.Row
    return connection, False


def init_db():
    connection, is_postgres = connect_db()
    try:
        cursor = connection.cursor()
        if is_postgres:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(120) NOT NULL,
                    email VARCHAR(255) UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL
                )
            """)
        else:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL
                )
            """)
        connection.commit()
    finally:
        connection.close()


def query_user_by_email(email):
    connection, is_postgres = connect_db()
    try:
        cursor = connection.cursor()
        placeholder = "%s" if is_postgres else "?"
        cursor.execute(f"SELECT id, name, email, password_hash FROM users WHERE email = {placeholder}", (email,))
        return cursor.fetchone()
    finally:
        connection.close()


def create_user(name, email, password_hash):
    connection, is_postgres = connect_db()
    try:
        cursor = connection.cursor()
        placeholder = "%s" if is_postgres else "?"
        cursor.execute(
            f"INSERT INTO users (name, email, password_hash) VALUES ({placeholder}, {placeholder}, {placeholder})",
            (name, email, password_hash),
        )
        connection.commit()
    finally:
        connection.close()


def extract_skills(text):
    doc = nlp.make_doc(text or "")
    found = set()
    for match_id, start, end in matcher(doc):
        found.add(nlp.vocab.strings[match_id])
    return sorted(found)


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def extract_text(path):
    try:
        extension = path.suffix.lower()
        if extension == ".txt":
            return path.read_text(encoding="utf-8", errors="ignore")
        if extension == ".pdf":
            from pypdf import PdfReader
            return "\n".join(page.extract_text() or "" for page in PdfReader(str(path)).pages)
        if extension == ".docx":
            from docx import Document
            return "\n".join(paragraph.text for paragraph in Document(str(path)).paragraphs)
    except Exception:
        return ""
    return ""


def score_resume(resume_text, required_skills):
    resume_skills = set(extract_skills(resume_text))
    required = set(required_skills)
    matched = sorted(required & resume_skills)
    missing = sorted(required - resume_skills)
    score = round(100 * len(matched) / len(required)) if required else 0
    return score, matched, missing


@app.before_request
def prepare_database():
    # Ensure the user table exists. For a real high-traffic app, run migrations separately.
    init_db()


@app.route("/style.css")
def css_file():
    return send_from_directory("public", "style.css")


@app.route("/script.js")
def js_file():
    return send_from_directory("public", "script.js")


@app.route("/")
def home():
    if not session.get("user_id"):
        return redirect(url_for("login"))
    return render_template("index.html", user_name=session.get("user_name", "HR"))


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if not name or not email or not password:
            flash("Please complete every field.")
        elif len(password) < 8:
            flash("Use a password with at least 8 characters.")
        elif not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            flash("Enter a valid email address.")
        elif query_user_by_email(email):
            flash("An account with this email already exists. Please log in.")
        else:
            try:
                create_user(name, email, generate_password_hash(password))
                flash("Account created. You can now log in.")
                return redirect(url_for("login"))
            except Exception:
                flash("We couldn't create the account. Please try again.")
    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = query_user_by_email(email)
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            session["user_name"] = user["name"]
            return redirect(url_for("home"))
        flash("Incorrect email or password. If you are new, create an account first.")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/filter", methods=["POST"])
def filter_resumes():
    if not session.get("user_id"):
        return redirect(url_for("login"))
    job_description = request.form.get("job_description", "").strip()
    files = request.files.getlist("resumes")
    if not job_description:
        flash("Please enter a job description.")
        return redirect(url_for("home"))
    if not files or all(not f.filename for f in files):
        flash("Please choose at least one resume.")
        return redirect(url_for("home"))

    required_skills = extract_skills(job_description)
    if not required_skills:
        flash("No supported skills found. Try Machine Learning, ML, Python, SQL, or NLP.")
        return redirect(url_for("home"))

    results = []
    # Keep a per-session list of opaque file tokens so HR can open only files
    # uploaded in their current session. The actual resume bytes are not put in the cookie.
    session_files = session.get("resume_files", {})

    for file in files:
        if not file.filename or not allowed_file(file.filename):
            continue
        safe_name = secure_filename(file.filename)
        suffix = Path(safe_name).suffix.lower()
        token = secrets.token_urlsafe(18)
        stored_name = f"{token}{suffix}"
        temp_path = UPLOAD_FOLDER / stored_name
        file.save(temp_path)

        text = extract_text(temp_path)
        score, matched, missing = score_resume(text, required_skills)
        email_match = re.search(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", text, re.IGNORECASE)
        candidate_email = email_match.group(0) if email_match else ""

        session_files[token] = {
            "stored_name": stored_name,
            "original_name": Path(file.filename).name,
        }
        results.append({
            "filename": Path(file.filename).name,
            "score": score,
            "matched": matched,
            "missing": missing,
            "text_found": bool(text.strip()),
            "email": candidate_email,
            "file_token": token,
        })

    session["resume_files"] = session_files
    results.sort(key=lambda item: item["score"], reverse=True)
    return render_template("results.html", results=results, required_skills=required_skills)


@app.route("/resume/<token>")
def open_resume(token):
    """Open a resume uploaded during this HR session."""
    if not session.get("user_id"):
        return redirect(url_for("login"))

    record = session.get("resume_files", {}).get(token)
    if not record:
        abort(404)

    # Never accept a path from the URL or session without reducing it to a filename.
    stored_name = Path(record.get("stored_name", "")).name
    path = UPLOAD_FOLDER / stored_name
    if not stored_name or not path.is_file():
        abort(404)

    return send_file(path, as_attachment=False, download_name=record.get("original_name", "resume"))


@app.errorhandler(413)
def file_too_large(error):
    flash("The upload was too large. Keep the total request below 4 MB for this demo.")
    return redirect(url_for("home"))


if __name__ == "__main__":
    app.run(debug=True)
