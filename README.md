# Lesson Ready

A minimal prototype for the *Minds and Machines in Learning* final exam.
Theme: **Human–AI collaboration in learning** (also supports equity: every student gets help on their own gaps before class).

## What it does

**Before the lesson**
1. The teacher types today's topic (and optionally course and language).
2. The AI suggests the prerequisite topics. The teacher unticks or adds topics.
3. The teacher picks a level (**Basic / Medium / Advanced**) and the number of questions. The AI writes a readiness quiz plus a short study note for each prerequisite.
4. The teacher reviews the quiz, removes bad questions, and publishes it. Students see nothing before this.
5. Students open the site, type the 5-letter lesson code and their name, then take the quiz. They get study notes and video/article search links **only for the topics they missed**.
6. The teacher sees readiness by prerequisite. Topics under 60% are flagged as "needs attention".

**After the lesson**
7. The teacher picks a level and can note what was actually covered. The AI writes a learning-check quiz, which the teacher reviews and publishes.
8. The teacher sees statistics: the average score, results by sub-topic, each question with its most common wrong answer, each student's score, and each student's score before vs after the lesson.

## Run it

```bash
# put your key in .env:   CLAUDE_API=sk-ant-...
./start.sh                               # then open http://localhost:5000
```
Students on the same network open `http://<teacher-computer-IP>:5000`.

## Files
- `app.py` – web pages, database (SQLite file `lessons.db`), grading and statistics
- `ai.py` – the three Claude calls (prerequisites, readiness quiz, learning check)
- `templates/`, `static/style.css` – the pages

## Minds and machines (who does what)
| AI (Claude Haiku 5.5, `claude-haiku-5-5`) | Teacher | Student |
|---|---|---|
| Suggests prerequisites, writes questions, explanations and study notes | Approves/edits prerequisites, chooses level, removes bad questions, publishes, decides what to recap | Takes quizzes, studies the notes, chooses a trusted source from the search links |

Grading and statistics are plain code, not AI, so they are exact.

## Honest limitations (for the poster)
- Prototype: no teacher login. Anyone who opens `/teacher` can see all lessons. Students are identified only by the name they type and a browser cookie.
- AI questions can contain mistakes, which is why the teacher must review them before publishing.
- The AI doesn't invent links. Resources are search links, so students must judge the source themselves.
- Only multiple-choice questions, so higher-level skills are measured only partly.
- The before vs after comparison uses two different quizzes, so it's a rough signal, not a measured learning gain.
- Data: only a typed name and answers are stored locally. Topic text is sent to the Claude API; no student data is sent to the AI.
