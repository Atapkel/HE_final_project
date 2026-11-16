# Lesson Ready

**Know the gaps before the lesson starts.** A working prototype for the *Minds and Machines in Learning* final exam (Pedagogy of Higher Education, Astana IT University).
Theme: **Human–AI collaboration in learning**, also supporting equity, because every student gets help on their own gaps.

## Run it

```bash
# 1. Put your Claude API key in .env:   CLAUDE_API=sk-ant-...
./share.sh     # public link + QR code: phones on any network (mobile data, uni Wi-Fi) can join
# or
./start.sh     # this computer only: http://localhost:5000
```

On the first run, both scripts create the demo data. Sign in with **Teacher sign in → Use the demo account** (`demo@lessonready.app` / `lessonready`), or create your own teacher account.

- `python seed.py` resets the demo data. The old database is kept as `lessons.backup-*.db`.
- `python seed.py --generate` regenerates the demo content with real AI calls.

`share.sh` downloads `cloudflared` once (into `bin/`) and opens a free Cloudflare quick tunnel. The QR codes in the app use that public link automatically. Press Ctrl+C to stop both the app and the link.

## Deploy online with the demo data (Render, free)

The repository includes `render.yaml`. On the first start, the server runs `python seed.py --if-empty`, which creates the demo teacher and sample classes. You don't need to upload a database.

1. Push this repository to GitHub. `.env`, the database and exam materials are git-ignored.
2. Go to [render.com](https://render.com) → **New → Blueprint** → choose the repository.
3. When asked for `CLAUDE_API`, paste your Claude key. `SECRET_KEY` is generated automatically.
4. Click **Deploy**. After about 2 minutes you get a link like `https://lesson-ready.onrender.com`.
5. Open it → **Teacher sign in → Use the demo account**. The QR codes already point to this address.

Good to know:
- **The free plan sleeps after 15 minutes without visitors.** The first visit then takes about a minute, so open the site 5 minutes before the pitch.
- **The free plan's disk is temporary.** Every redeploy or restart starts again from fresh demo data, which is handy for a clean demo. To reset on purpose: *Manual Deploy → Deploy latest commit*.
- To keep data permanently, add a Render disk (paid) and set `LESSONS_DB=/var/data/lessons.db`.
- **Other hosts** (Railway, Heroku-style): the `Procfile` runs the same start command. Set `CLAUDE_API` and `SECRET_KEY` as environment variables.

## What it does

| | Teacher | AI (Claude Haiku 5.5) | Student |
|---|---|---|---|
| **Before class** | Types the topic; chooses prerequisites and level (Basic / Medium / Advanced = revised Bloom); **reviews, edits, removes or adds** every question; publishes | Suggests prerequisites; drafts quiz, explanations and study notes (EN / RU / KZ) | Scans the QR code, enters code and name (no account), takes an **ungraded** quiz, gets notes **only for missed topics** |
| **In class** | Sees readiness **live** by topic; topics under 60% are flagged; sees who to check in with | | |
| **After class** | Creates and reviews a learning check; sees before vs after | Drafts the learning check | Takes it, sees explanations |
| **Insights** | Decides what to re-teach; edits and sends a message to the class | Analyses **anonymous** answer counts: misconceptions, teaching actions, next-lesson plan, draft message | Reads the teacher's message |

Grading and statistics are plain code (`stats.py`), not AI. The evidence next to each AI misconception ("R8 · 29% correct · 14 of 24 chose 7") is computed by the app.

## Files
- `app.py`: pages, accounts, database (SQLite `lessons.db`), live updates
- `ai.py`: the four Claude calls (prerequisites, readiness quiz, learning check, class analysis)
- `stats.py`: grading and statistics
- `seed.py` + `demo/demo_content.json`: the demo teacher and sample classes
- `templates/`, `static/`: the interface (same visual identity as the poster)

## Honest limitations
- **Sample classes use simulated students** (marked "Sample class"). Their quizzes and the KNN class analysis were produced by the app's real AI pipeline; the AI made two mistakes there, and the seed records them as teacher corrections (CALC2 Q1, BD2RU Q5).
- Students are identified only by the name they type and a browser cookie. Teacher accounts use hashed passwords, but there is no email verification, password reset or CSRF protection yet.
- AI questions can be wrong, which is why teacher review is required before publishing.
- The AI never invents links: resources are search links, and students judge the source.
- Multiple choice only, so higher-order skills are measured only partly.
- Before vs after compares two different quizzes: a rough signal, not a measured learning gain.
- Privacy: only a typed name and answers are stored locally. The AI receives the topic and anonymous answer counts, never student names.
- Needs internet and a paid AI API, at roughly 0.1–0.5 US cents per AI call with Haiku 5.5.

## AI use disclosure
Claude (Anthropic) helped write the prototype code, the demo content and the pitch draft. The team checked the content and is responsible for it.
