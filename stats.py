"""Grading statistics. Plain code, no AI, so every number on the dashboard is exact and explainable."""
import json
from collections import Counter, defaultdict

WEAK = 60  # a topic below this % correct is flagged "Needs attention"
SUPPORT = 50  # a student below this % on the readiness quiz is suggested for a check-in


def pct(part, whole):
    return round(100 * part / whole) if whole else 0


def quiz_stats(quiz, attempts):
    questions = json.loads(quiz["questions"])
    prefix = "R" if quiz["kind"] == "pre" else "L"
    n = len(attempts)
    counts = [[0] * len(q["options"]) for q in questions]
    per_topic = defaultdict(lambda: [0, 0])  # topic -> [right, asked]
    students = []

    for a in attempts:
        answers = json.loads(a["answers"])
        missed = Counter()
        for i, q in enumerate(questions):
            chosen = answers[i] if i < len(answers) else None
            if chosen is not None and 0 <= chosen < len(q["options"]):
                counts[i][chosen] += 1
            ok = chosen == q["correct_index"]
            per_topic[q["prerequisite"]][0] += ok
            per_topic[q["prerequisite"]][1] += 1
            if not ok:
                missed[q["prerequisite"]] += 1
        students.append({
            "id": a["student_id"], "name": a["student_name"], "score": a["score"],
            "total": a["total"], "pct": pct(a["score"], a["total"]), "created": a["created"],
            "missed": [t for t, _ in missed.most_common()],
        })

    question_rows = []
    for i, q in enumerate(questions):
        right = counts[i][q["correct_index"]]
        wrong = [(j, c) for j, c in enumerate(counts[i]) if j != q["correct_index"] and c]
        top = max(wrong, key=lambda x: x[1]) if wrong else None
        question_rows.append({
            "ref": f"{prefix}{i + 1}", "text": q["text"], "topic": q["prerequisite"],
            "pct": pct(right, n), "right": right,
            "options": [{"text": o, "count": counts[i][j], "pct": pct(counts[i][j], n),
                         "correct": j == q["correct_index"]} for j, o in enumerate(q["options"])],
            "common_wrong": q["options"][top[0]] if top else None,
            "common_wrong_count": top[1] if top else 0,
        })

    topics = sorted(({"name": t, "pct": pct(r, asked)} for t, (r, asked) in per_topic.items()),
                    key=lambda x: x["pct"])
    bins = [0, 0, 0, 0]  # 0-24, 25-49, 50-74, 75-100 %
    for s in students:
        bins[min(3, s["pct"] // 25)] += 1
    total_score = sum(a["score"] for a in attempts)
    total_q = sum(a["total"] for a in attempts)
    return {
        "kind": quiz["kind"], "count": n, "avg": pct(total_score, total_q),
        "topics": topics, "weak_topics": [t for t in topics if t["pct"] < WEAK],
        "questions": question_rows, "bins": bins,
        "students": sorted(students, key=lambda s: s["name"].lower()),
        "support": sorted((s for s in students if s["pct"] < SUPPORT), key=lambda s: s["pct"]),
    }


def progress(pre, post):
    """Before vs after for students who took both quizzes (matched by browser id, not by name)."""
    if not pre or not post:
        return []
    before = {s["id"]: s for s in pre["students"]}
    rows = [{"name": s["name"], "pre": before[s["id"]]["pct"], "post": s["pct"]}
            for s in post["students"] if s["id"] in before]
    return sorted(rows, key=lambda r: r["name"].lower())


def analysis_input(stats, progress_rows):
    """Anonymous summary for the AI: only counts per answer option. No names, no ids."""
    lines = []
    for kind, title in (("pre", "READINESS QUIZ (before class, tests prerequisites)"),
                        ("post", "LEARNING CHECK (after class, tests the lesson)")):
        s = stats.get(kind)
        if not s or not s["count"]:
            continue
        lines.append(f"{title}: {s['count']} students, average {s['avg']}% correct.")
        for q in s["questions"]:
            lines.append(f'{q["ref"]} [topic: {q["topic"]}] "{q["text"]}" -> {q["pct"]}% correct')
            for letter, o in zip("ABCDEFGH", q["options"]):
                mark = "  (correct)" if o["correct"] else ""
                lines.append(f'    {letter}) "{o["text"]}": {o["count"]} students{mark}')
        lines.append("Topic averages: " + "; ".join(f'{t["name"]} {t["pct"]}%' for t in s["topics"]))
        lines.append(f"Score spread: {s['bins'][0]} students under 25%, {s['bins'][1]} at 25-49%, "
                     f"{s['bins'][2]} at 50-74%, {s['bins'][3]} at 75% or more.")
        lines.append("")
    if progress_rows:
        avg_pre = round(sum(r["pre"] for r in progress_rows) / len(progress_rows))
        avg_post = round(sum(r["post"] for r in progress_rows) / len(progress_rows))
        improved = sum(r["post"] > r["pre"] for r in progress_rows)
        lines.append(f"{len(progress_rows)} students took both quizzes: average {avg_pre}% before -> "
                     f"{avg_post}% after; {improved} of them scored higher after class. "
                     "(The two quizzes test different content.)")
    return "\n".join(lines)


def evidence(stats, refs):
    """Exact numbers for the question ids the AI cited, computed by code."""
    by_ref = {q["ref"]: (q, s["count"]) for s in stats.values() if s for q in s["questions"]}
    out = []
    for ref in refs:
        ref = ref.strip().upper()
        if ref in by_ref:
            q, n = by_ref[ref]
            out.append({"ref": ref, "text": q["text"], "pct": q["pct"], "n": n,
                        "wrong": q["common_wrong"], "wrong_count": q["common_wrong_count"]})
    return out
