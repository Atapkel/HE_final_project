"""Lesson Ready: AI-assisted readiness and learning check for university lessons.

Run:  ANTHROPIC_API_KEY=... python app.py   then open http://localhost:5000
"""
import json
import os
import secrets
import sqlite3
from collections import Counter, defaultdict
from urllib.parse import quote_plus

from flask import Flask, abort, flash, g, redirect, render_template, request, session, url_for

import ai

BASE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE, "lessons.db")
LEVELS = ["Basic", "Medium", "Advanced"]
LANGUAGES = ["English", "Russian", "Kazakh"]

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-change-me")


# ---------------- Database ----------------

SCHEMA = """
CREATE TABLE IF NOT EXISTS lessons (
    id INTEGER PRIMARY KEY, code TEXT UNIQUE, topic TEXT, course TEXT, language TEXT,
    prereqs TEXT DEFAULT '[]', created TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS quizzes (
    id INTEGER PRIMARY KEY, lesson_id INTEGER, kind TEXT, level TEXT,
    questions TEXT, resources TEXT DEFAULT '[]', status TEXT DEFAULT 'draft');
CREATE TABLE IF NOT EXISTS attempts (
    id INTEGER PRIMARY KEY, quiz_id INTEGER, student_id TEXT, student_name TEXT,
    answers TEXT, score INTEGER, total INTEGER, created TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(quiz_id, student_id));
"""


def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_):
    conn = g.pop("db", None)
    if conn:
        conn.close()


def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript(SCHEMA)


def one(sql, *args):
    row = db().execute(sql, args).fetchone()
    if row is None:
        abort(404)
    return row


def lesson_quizzes(lesson_id):
    return {q["kind"]: q for q in db().execute(
        "SELECT * FROM quizzes WHERE lesson_id=? ORDER BY id", (lesson_id,))}


def new_code():
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O/1/I to avoid confusion
    while True:
        code = "".join(secrets.choice(alphabet) for _ in range(5))
        if not db().execute("SELECT 1 FROM lessons WHERE code=?", (code,)).fetchone():
            return code


# ---------------- Statistics ----------------

def quiz_stats(quiz):
    questions = json.loads(quiz["questions"])
    attempts = db().execute("SELECT * FROM attempts WHERE quiz_id=? ORDER BY student_name",
                            (quiz["id"],)).fetchall()
    per_q = [{"right": 0, "wrong": Counter()} for _ in questions]
    per_topic = defaultdict(lambda: [0, 0])  # topic -> [right, asked]
    for a in attempts:
        answers = json.loads(a["answers"])
        for i, q in enumerate(questions):
            chosen = answers[i] if i < len(answers) else None
            ok = chosen == q["correct_index"]
            per_q[i]["right"] += ok
            if not ok and chosen is not None:
                per_q[i]["wrong"][chosen] += 1
            per_topic[q["prerequisite"]][0] += ok
            per_topic[q["prerequisite"]][1] += 1

    n = len(attempts)
    question_rows = []
    for q, s in zip(questions, per_q):
        common = s["wrong"].most_common(1)
        question_rows.append({
            "text": q["text"],
            "pct": round(100 * s["right"] / n) if n else 0,
            "common_wrong": q["options"][common[0][0]] if common else None,
        })
    topic_rows = sorted(
        ({"name": t, "pct": round(100 * r / asked)} for t, (r, asked) in per_topic.items()),
        key=lambda x: x["pct"])
    avg = round(100 * sum(a["score"] for a in attempts) / sum(a["total"] for a in attempts)) if n else 0
    return {"count": n, "avg": avg, "topics": topic_rows, "questions": question_rows,
            "students": attempts}


# ---------------- Home ----------------

@app.route("/")
def home():
    return render_template("home.html")


# ---------------- Teacher ----------------

@app.route("/teacher")
def teacher_home():
    lessons = db().execute("SELECT * FROM lessons ORDER BY id DESC").fetchall()
    return render_template("teacher_home.html", lessons=lessons, languages=LANGUAGES)


@app.post("/teacher/new")
def teacher_new():
    topic = request.form.get("topic", "").strip()
    course = request.form.get("course", "").strip()
    language = request.form.get("language", "English")
    if not topic:
        flash("Please write the lesson topic.")
        return redirect(url_for("teacher_home"))
    try:
        prereqs = ai.get_prerequisites(topic, course, language)
    except ai.AIError as e:
        flash(str(e))
        return redirect(url_for("teacher_home"))
    cur = db().execute(
        "INSERT INTO lessons (code, topic, course, language, prereqs) VALUES (?,?,?,?,?)",
        (new_code(), topic, course, language, json.dumps(prereqs)))
    db().commit()
    return redirect(url_for("teacher_prereqs", lesson_id=cur.lastrowid))


@app.route("/teacher/lesson/<int:lesson_id>/prerequisites", methods=["GET", "POST"])
def teacher_prereqs(lesson_id):
    lesson = one("SELECT * FROM lessons WHERE id=?", lesson_id)
    prereqs = json.loads(lesson["prereqs"])
    if request.method == "POST":
        chosen = request.form.getlist("prereq")
        chosen += [x.strip() for x in request.form.get("extra", "").splitlines() if x.strip()]
        if not chosen:
            flash("Keep at least one prerequisite.")
            return redirect(request.url)
        level = request.form.get("level", "Basic")
        n = int(request.form.get("n", 6))
        try:
            quiz = ai.make_pre_quiz(lesson["topic"], lesson["course"], chosen, level, n,
                                    lesson["language"])
        except ai.AIError as e:
            flash(str(e))
            return redirect(request.url)
        db().execute("DELETE FROM quizzes WHERE lesson_id=? AND kind='pre' AND status='draft'",
                     (lesson_id,))
        cur = db().execute(
            "INSERT INTO quizzes (lesson_id, kind, level, questions, resources) VALUES (?,?,?,?,?)",
            (lesson_id, "pre", level, json.dumps(quiz["questions"]), json.dumps(quiz["resources"])))
        db().commit()
        return redirect(url_for("teacher_review", quiz_id=cur.lastrowid))
    return render_template("teacher_prereqs.html", lesson=lesson, prereqs=prereqs, levels=LEVELS)


@app.post("/teacher/lesson/<int:lesson_id>/post-quiz")
def teacher_post_quiz(lesson_id):
    lesson = one("SELECT * FROM lessons WHERE id=?", lesson_id)
    level = request.form.get("level", "Basic")
    n = int(request.form.get("n", 6))
    notes = request.form.get("notes", "").strip()
    try:
        quiz = ai.make_post_quiz(lesson["topic"], lesson["course"], notes, level, n,
                                 lesson["language"])
    except ai.AIError as e:
        flash(str(e))
        return redirect(url_for("teacher_lesson", lesson_id=lesson_id))
    db().execute("DELETE FROM quizzes WHERE lesson_id=? AND kind='post' AND status='draft'",
                 (lesson_id,))
    cur = db().execute("INSERT INTO quizzes (lesson_id, kind, level, questions) VALUES (?,?,?,?)",
                       (lesson_id, "post", level, json.dumps(quiz["questions"])))
    db().commit()
    return redirect(url_for("teacher_review", quiz_id=cur.lastrowid))


@app.route("/teacher/quiz/<int:quiz_id>/review", methods=["GET", "POST"])
def teacher_review(quiz_id):
    quiz = one("SELECT * FROM quizzes WHERE id=?", quiz_id)
    lesson = one("SELECT * FROM lessons WHERE id=?", quiz["lesson_id"])
    questions = json.loads(quiz["questions"])
    if request.method == "POST":
        keep = {int(i) for i in request.form.getlist("keep")}
        questions = [q for i, q in enumerate(questions) if i in keep]
        if not questions:
            flash("Keep at least one question.")
            return redirect(request.url)
        # Only one published quiz of each kind per lesson.
        db().execute("DELETE FROM quizzes WHERE lesson_id=? AND kind=? AND id<>?",
                     (lesson["id"], quiz["kind"], quiz_id))
        db().execute("UPDATE quizzes SET questions=?, status='open' WHERE id=?",
                     (json.dumps(questions), quiz_id))
        db().commit()
        flash("Quiz published. Students can now take it with the lesson code.")
        return redirect(url_for("teacher_lesson", lesson_id=lesson["id"]))
    return render_template("teacher_review.html", quiz=quiz, lesson=lesson, questions=questions,
                           resources=json.loads(quiz["resources"]))


@app.post("/teacher/quiz/<int:quiz_id>/status")
def teacher_quiz_status(quiz_id):
    quiz = one("SELECT * FROM quizzes WHERE id=?", quiz_id)
    new = "closed" if quiz["status"] == "open" else "open"
    db().execute("UPDATE quizzes SET status=? WHERE id=?", (new, quiz_id))
    db().commit()
    return redirect(url_for("teacher_lesson", lesson_id=quiz["lesson_id"]))


@app.route("/teacher/lesson/<int:lesson_id>")
def teacher_lesson(lesson_id):
    lesson = one("SELECT * FROM lessons WHERE id=?", lesson_id)
    quizzes = lesson_quizzes(lesson_id)
    stats = {kind: quiz_stats(q) for kind, q in quizzes.items() if q["status"] != "draft"}

    # Pre vs post for students who took both
    progress = []
    if "pre" in stats and "post" in stats:
        pre = {a["student_id"]: a for a in stats["pre"]["students"]}
        for a in stats["post"]["students"]:
            if a["student_id"] in pre:
                p = pre[a["student_id"]]
                progress.append({"name": a["student_name"],
                                 "pre": round(100 * p["score"] / p["total"]),
                                 "post": round(100 * a["score"] / a["total"])})
    return render_template("teacher_lesson.html", lesson=lesson, quizzes=quizzes, stats=stats,
                           progress=progress, levels=LEVELS,
                           join_url=request.host_url.rstrip("/") + url_for("student_join"))


# ---------------- Student ----------------

@app.route("/join", methods=["GET", "POST"])
def student_join():
    if request.method == "POST":
        code = request.form.get("code", "").strip().upper()
        name = request.form.get("name", "").strip()
        if not name or not db().execute("SELECT 1 FROM lessons WHERE code=?", (code,)).fetchone():
            flash("Please check the lesson code and write your name.")
            return redirect(url_for("student_join"))
        if session.get("name") != name:
            session["student_id"] = secrets.token_hex(8)
        session["name"] = name
        return redirect(url_for("student_lesson", code=code))
    return render_template("student_join.html", code=request.args.get("code", ""))


def require_student():
    if "student_id" not in session:
        abort(redirect(url_for("student_join")))


@app.route("/lesson/<code>")
def student_lesson(code):
    require_student()
    lesson = one("SELECT * FROM lessons WHERE code=?", code.upper())
    quizzes = lesson_quizzes(lesson["id"])
    done = {r["quiz_id"] for r in db().execute(
        "SELECT quiz_id FROM attempts WHERE student_id=?", (session["student_id"],))}
    return render_template("student_lesson.html", lesson=lesson, quizzes=quizzes, done=done)


@app.route("/quiz/<int:quiz_id>", methods=["GET", "POST"])
def student_quiz(quiz_id):
    require_student()
    quiz = one("SELECT * FROM quizzes WHERE id=?", quiz_id)
    lesson = one("SELECT * FROM lessons WHERE id=?", quiz["lesson_id"])
    sid = session["student_id"]
    if db().execute("SELECT 1 FROM attempts WHERE quiz_id=? AND student_id=?", (quiz_id, sid)).fetchone():
        return redirect(url_for("student_result", quiz_id=quiz_id))
    if quiz["status"] != "open":
        flash("This quiz is not open right now.")
        return redirect(url_for("student_lesson", code=lesson["code"]))
    questions = json.loads(quiz["questions"])
    if request.method == "POST":
        answers = []
        for i in range(len(questions)):
            v = request.form.get(f"q{i}")
            answers.append(int(v) if v is not None and v.isdigit() else None)
        score = sum(a == q["correct_index"] for a, q in zip(answers, questions))
        db().execute("INSERT OR IGNORE INTO attempts (quiz_id, student_id, student_name, answers, score, total)"
                     " VALUES (?,?,?,?,?,?)",
                     (quiz_id, sid, session["name"], json.dumps(answers), score, len(questions)))
        db().commit()
        return redirect(url_for("student_result", quiz_id=quiz_id))
    return render_template("student_quiz.html", quiz=quiz, lesson=lesson, questions=questions)


@app.route("/quiz/<int:quiz_id>/result")
def student_result(quiz_id):
    require_student()
    quiz = one("SELECT * FROM quizzes WHERE id=?", quiz_id)
    lesson = one("SELECT * FROM lessons WHERE id=?", quiz["lesson_id"])
    attempt = one("SELECT * FROM attempts WHERE quiz_id=? AND student_id=?", quiz_id, session["student_id"])
    questions = json.loads(quiz["questions"])
    answers = json.loads(attempt["answers"])
    rows = [{"q": q, "chosen": a, "ok": a == q["correct_index"]} for q, a in zip(questions, answers)]

    # Resources only for prerequisites the student got wrong
    weak = {r["q"]["prerequisite"].strip().lower() for r in rows if not r["ok"]}
    resources = []
    for r in json.loads(quiz["resources"]):
        if r["prerequisite"].strip().lower() in weak:
            q = quote_plus(r["search_query"])
            r["youtube"] = f"https://www.youtube.com/results?search_query={q}"
            r["web"] = f"https://www.google.com/search?q={q}"
            resources.append(r)
    return render_template("student_result.html", quiz=quiz, lesson=lesson, attempt=attempt,
                           rows=rows, resources=resources)


init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
