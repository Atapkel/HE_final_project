"""All calls to Claude live here. Each function returns plain Python data (dicts/lists)."""
import os
from typing import List

import anthropic
from pydantic import BaseModel

MODEL = "claude-haiku-5-5"


def _load_env(path=os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")):
    """Read KEY=VALUE lines from .env into the environment (without overriding real env vars)."""
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            key, sep, value = line.strip().partition("=")
            if sep and not key.startswith("#"):
                os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_env()
_client = None


def get_client():
    global _client
    if _client is None:
        key = os.environ.get("CLAUDE_API") or os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise AIError("No AI key found. Put your key in the .env file as CLAUDE_API=sk-ant-...")
        _client = anthropic.Anthropic(api_key=key)
    return _client

LEVEL_GUIDE = {
    "Basic": "recall and simple understanding: definitions, recognising examples, one-step questions",
    "Medium": "application: using the idea in a familiar situation, two-step reasoning, common misconceptions",
    "Advanced": "analysis and transfer: unfamiliar situations, multi-step reasoning, comparing or justifying",
}

SYSTEM = (
    "You are a teaching assistant for university teachers. Your output is always reviewed by the "
    "teacher before students see it, so be accurate, neutral and free of cultural bias. Write for "
    "students who may be studying in a second language: short, clear sentences, no trick wording."
)


class AIError(Exception):
    """Raised with a message that is safe to show to the teacher."""


# ---------- Output shapes ----------

class Prerequisite(BaseModel):
    name: str
    why_needed: str


class PrerequisiteList(BaseModel):
    prerequisites: List[Prerequisite]


class Question(BaseModel):
    text: str
    options: List[str]
    correct_index: int
    explanation: str
    prerequisite: str  # which prerequisite (pre-quiz) or sub-topic (post-quiz) it checks


class Resource(BaseModel):
    prerequisite: str
    summary: str
    search_query: str


class PreQuiz(BaseModel):
    questions: List[Question]
    resources: List[Resource]


class PostQuiz(BaseModel):
    questions: List[Question]


class Misconception(BaseModel):
    topic: str
    question_refs: List[str]  # ids like "R3" or "L2" from the data we send; the app shows the exact numbers
    what_students_think: str
    why_it_happens: str
    teaching_action: str


class ClassInsight(BaseModel):
    headline: str
    summary: str
    misconceptions: List[Misconception]
    strengths: List[str]
    next_steps: List[str]
    note_to_students: str
    data_caution: str


# ---------- Helper ----------

def _ask(prompt: str, schema: type[BaseModel]) -> BaseModel:
    """One structured call to Claude; returns a validated pydantic object or raises AIError."""
    try:
        response = get_client().messages.parse(
            model=MODEL,
            max_tokens=16000,
            system=SYSTEM,
            messages=[{"role": "user", "content": prompt}],
            output_format=schema,
            output_config={"effort": "medium"},
        )
    except anthropic.AuthenticationError:
        raise AIError("The AI key is missing or wrong. Check CLAUDE_API in the .env file.")
    except anthropic.RateLimitError:
        raise AIError("The AI service is busy. Please wait a minute and try again.")
    except anthropic.APIConnectionError:
        raise AIError("Cannot reach the AI service. Check the internet connection.")
    except anthropic.APIStatusError as e:
        raise AIError(f"The AI service returned an error ({e.status_code}). Please try again.")

    if response.stop_reason == "refusal" or response.parsed_output is None:
        raise AIError("The AI could not create this content. Try rewording the topic.")
    return response.parsed_output


# ---------- Public functions ----------

def get_prerequisites(topic: str, course: str, language: str) -> list[dict]:
    prompt = f"""A university teacher will teach this lesson today.
Course: {course or "not specified"}
Lesson topic: {topic}

List the 3 to 6 most important prerequisite topics a student must already understand to follow
this lesson. Only include things taught BEFORE this lesson, not the lesson content itself.
For each, say in one sentence why it is needed. Write in {language}."""
    result = _ask(prompt, PrerequisiteList)
    return [p.model_dump() for p in result.prerequisites]


def make_pre_quiz(topic: str, course: str, prerequisites: list[str], level: str,
                  n_questions: int, language: str) -> dict:
    prompt = f"""Create a short readiness quiz that students take BEFORE the lesson "{topic}"
(course: {course or "not specified"}). It checks only these prerequisites:
{chr(10).join("- " + p for p in prerequisites)}

Rules:
- Exactly {n_questions} multiple-choice questions, spread evenly across the prerequisites.
- Difficulty: {level} = {LEVEL_GUIDE[level]}.
- 4 options each, exactly one correct; correct_index is 0-based. Vary the position of the correct answer.
- "prerequisite" must be copied exactly from the list above.
- "explanation": one or two sentences a student sees after answering.
- Also give one resource per prerequisite: "summary" is a 3-5 sentence plain explanation
  a student can read to catch up; "search_query" is a short query to find a video or article on it.
  Do NOT invent URLs.
Write everything in {language}."""
    return _ask(prompt, PreQuiz).model_dump()


def make_post_quiz(topic: str, course: str, notes: str, level: str,
                   n_questions: int, language: str) -> dict:
    prompt = f"""Create a quiz that students take AFTER the lesson "{topic}"
(course: {course or "not specified"}) to check what they learned.
What the teacher actually covered: {notes or "the standard content of this topic"}

Rules:
- Exactly {n_questions} multiple-choice questions about the lesson content.
- Difficulty: {level} = {LEVEL_GUIDE[level]}.
- 4 options each, exactly one correct; correct_index is 0-based. Vary the position of the correct answer.
- "prerequisite" = the short name of the sub-topic the question checks (reuse the same names so
  results can be grouped; 2-4 sub-topics in total).
- "explanation": one or two sentences a student sees after answering.
Write everything in {language}."""
    return _ask(prompt, PostQuiz).model_dump()


def analyse_class(topic: str, course: str, language: str, data: str) -> dict:
    """Read anonymous, aggregated class results and draft feedback for the teacher.

    `data` contains only counts per question/answer option. No student names or ids are sent."""
    prompt = f"""You help a university teacher understand class results for the lesson "{topic}"
(course: {course or "not specified"}). Below are ANONYMOUS, aggregated results: for each question,
how many students chose each option. "R" questions are the readiness quiz taken before class
(they test prerequisites); "L" questions are the learning check taken after class.

{data}

Write a short, practical analysis for the teacher:
- "headline": one sentence with the single most important finding.
- "summary": 2-3 sentences on the overall picture (readiness, learning, change before vs after).
- "misconceptions": up to 4, most important first. Only include a misconception when the data
  shows it (a question below ~65% correct, or many students choosing the same wrong option).
  For each: the topic; "question_refs" = the question ids that show it (e.g. ["R7","R8"]);
  what students seem to believe, based on the wrong option they chose; a likely reason;
  and one concrete teaching action for the next class (an example, a contrast, a quick task).
- "strengths": 1-3 things most students clearly understand.
- "next_steps": 3-4 short, ordered steps for the next lesson (with rough minutes).
- "note_to_students": a friendly 3-5 sentence message the teacher may send to the whole class:
  what went well, which idea to revise and how. No names, no scores of individuals, no blame.
- "data_caution": one sentence on the limits of this data (e.g. few students, multiple choice only,
  the two quizzes test different content).
Be specific and cite numbers only as they appear in the data. Do not invent data.
Write everything in {language}."""
    return _ask(prompt, ClassInsight).model_dump()
