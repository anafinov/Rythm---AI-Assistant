"""Three agent functions: analyst, methodologist, game designer.

Each agent is a plain async function that builds a prompt, calls LLM, and
returns structured data. No complex LangChain graphs — just prompt chains.
"""

from __future__ import annotations

import json
import logging
from datetime import date, timedelta

import pandas as pd

from src.database import CheckIn, Quest, User
from src.llm import LLM
from src.rag import KnowledgeBase

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Agent 1 — Analyst
# ---------------------------------------------------------------------------

ANALYST_SYSTEM = (
    "Ты — аналитик здоровья. Анализируешь данные чек-инов пользователя "
    "и возвращаешь JSON-объект с оценкой состояния. Отвечай ТОЛЬКО валидным JSON, "
    "без пояснений."
)

ANALYST_PROMPT = """\
Данные пользователя за последние дни:
{stats_json}

Верни JSON:
{{
  "weight_trend": "losing" | "stable" | "gaining",
  "avg_sleep": <float>,
  "avg_stress": <float>,
  "avg_mood": <float>,
  "risk_level": "low" | "medium" | "high",
  "soft_mode": true | false,
  "summary": "<краткое резюме на русском, 1-2 предложения>"
}}

Правила:
- soft_mode = true если avg_stress >= 4 ИЛИ avg_sleep < 5 ИЛИ avg_mood <= 2
- risk_level = "high" если soft_mode = true, "medium" если тренд gaining, иначе "low"
"""


async def analyze_state(
    llm: LLM, user: User, checkins: list[CheckIn]
) -> dict:
    """Analyse recent check-ins and return a state profile dict."""
    if not checkins:
        return _default_analysis()

    df = pd.DataFrame(
        [
            {
                "date": str(c.date),
                "weight": c.weight,
                "sleep_hours": c.sleep_hours,
                "stress": c.stress,
                "mood": c.mood,
            }
            for c in checkins
        ]
    )

    stats = {
        "current_weight": user.weight,
        "goal_weight": user.goal_weight,
        "days_tracked": len(df),
        "avg_sleep": round(df["sleep_hours"].mean(), 1) if df["sleep_hours"].notna().any() else None,
        "avg_stress": round(df["stress"].mean(), 1) if df["stress"].notna().any() else None,
        "avg_mood": round(df["mood"].mean(), 1) if df["mood"].notna().any() else None,
        "weight_first": df["weight"].dropna().iloc[0] if df["weight"].notna().any() else None,
        "weight_last": df["weight"].dropna().iloc[-1] if df["weight"].notna().any() else None,
    }

    prompt = ANALYST_PROMPT.format(stats_json=json.dumps(stats, ensure_ascii=False))

    try:
        raw = await llm.generate(prompt, system=ANALYST_SYSTEM, temperature=0.3, max_tokens=256)
        return json.loads(_extract_json(raw))
    except Exception:
        logger.warning("Analyst JSON parse failed, using heuristic fallback")
        return _heuristic_analysis(stats)


def analyze_state_fast(user: User, checkins: list[CheckIn]) -> dict:
    """Fast heuristic analysis without LLM — instant, used for check-in flow."""
    if not checkins:
        return _default_analysis()

    df = pd.DataFrame(
        [
            {
                "weight": c.weight,
                "sleep_hours": c.sleep_hours,
                "stress": c.stress,
                "mood": c.mood,
            }
            for c in checkins
        ]
    )

    stats = {
        "avg_sleep": round(df["sleep_hours"].mean(), 1) if df["sleep_hours"].notna().any() else 7.0,
        "avg_stress": round(df["stress"].mean(), 1) if df["stress"].notna().any() else 2.0,
        "avg_mood": round(df["mood"].mean(), 1) if df["mood"].notna().any() else 3.0,
        "weight_first": df["weight"].dropna().iloc[0] if df["weight"].notna().any() else None,
        "weight_last": df["weight"].dropna().iloc[-1] if df["weight"].notna().any() else None,
    }
    return _heuristic_analysis(stats)


def _default_analysis() -> dict:
    return {
        "weight_trend": "stable",
        "avg_sleep": 7.0,
        "avg_stress": 2.0,
        "avg_mood": 3.0,
        "risk_level": "low",
        "soft_mode": False,
        "summary": "Недостаточно данных для анализа. Продолжайте отмечать чек-ины!",
    }


def _heuristic_analysis(stats: dict) -> dict:
    """Fallback when LLM output is unparseable."""
    avg_stress = stats.get("avg_stress") or 2.0
    avg_sleep = stats.get("avg_sleep") or 7.0
    avg_mood = stats.get("avg_mood") or 3.0
    soft_mode = avg_stress >= 4 or avg_sleep < 5 or avg_mood <= 2

    w_first = stats.get("weight_first")
    w_last = stats.get("weight_last")
    if w_first and w_last:
        diff = w_last - w_first
        trend = "losing" if diff < -0.3 else ("gaining" if diff > 0.3 else "stable")
    else:
        trend = "stable"

    return {
        "weight_trend": trend,
        "avg_sleep": avg_sleep,
        "avg_stress": avg_stress,
        "avg_mood": avg_mood,
        "risk_level": "high" if soft_mode else ("medium" if trend == "gaining" else "low"),
        "soft_mode": soft_mode,
        "summary": "Анализ выполнен по упрощённым правилам.",
    }


# ---------------------------------------------------------------------------
# Agent 2 — Methodologist (RAG)
# ---------------------------------------------------------------------------

METHODOLOGIST_SYSTEM = (
    "Ты — нутрициолог и специалист по поведенческой терапии. "
    "Отвечаешь кратко, дружелюбно и со ссылками на научные данные из базы знаний. "
    "Если в базе нет ответа, честно скажи об этом. НЕ выдумывай исследования или статистику "
)

METHODOLOGIST_PROMPT = """\
Контекст пользователя: {context}

Релевантные материалы из базы знаний:
---
{sources}
---

Вопрос пользователя: {question}

Дай краткий понятный ответ (3-5 предложений). Если возможно, укажи источник рекомендации.
"""


async def get_recommendation(
    llm: LLM, kb: KnowledgeBase, question: str, context: dict
) -> str:
    """Answer a user question using RAG over the knowledge base."""
    chunks = kb.search(question, n_results=3)
    sources = "\n\n".join(chunks) if chunks else "База знаний пуста."

    prompt = METHODOLOGIST_PROMPT.format(
        context=json.dumps(context, ensure_ascii=False),
        sources=sources,
        question=question,
    )
    return await llm.generate(prompt, system=METHODOLOGIST_SYSTEM, temperature=0.3)


# ---------------------------------------------------------------------------
# Agent 3 — Game Designer
# ---------------------------------------------------------------------------

GAME_DESIGNER_SYSTEM = (
    "Ты — геймдизайнер, который создаёт ежедневные квесты для приложения "
    "по снижению веса. Отвечай ТОЛЬКО валидным JSON-массивом, без пояснений."
)

GAME_DESIGNER_PROMPT = """\
Профиль пользователя:
- Режим: {mode}
- Средний стресс: {stress}/5
- Средний сон: {sleep} ч
- Тренд веса: {trend}
- Уже выполненные категории за последние 3 дня: {recent_categories}

Сгенерируй ровно 3 квеста на сегодня.
Категории: nutrition, activity, mindfulness, sleep.
Если режим «мягкий» — выбирай лёгкие задания (прогулка вместо тренировки, дыхание вместо медитации).

Формат — JSON-массив:
[
  {{"title": "...", "description": "...", "category": "...", "xp": <10|25|50>}},
  ...
]
"""


async def generate_quests(
    llm: LLM, analysis: dict, recent_quests: list[Quest]
) -> list[dict]:
    """Generate 3 daily quests based on current analysis."""
    recent_cats = list({q.category for q in recent_quests if q.completed})

    mode = "мягкий" if analysis.get("soft_mode") else "обычный"
    prompt = GAME_DESIGNER_PROMPT.format(
        mode=mode,
        stress=analysis.get("avg_stress", "?"),
        sleep=analysis.get("avg_sleep", "?"),
        trend=analysis.get("weight_trend", "stable"),
        recent_categories=", ".join(recent_cats) or "нет данных",
    )

    try:
        raw = await llm.generate(
            prompt,
            system=GAME_DESIGNER_SYSTEM,
            temperature=0.5,
            max_tokens=256,
        )
        quests = json.loads(_extract_json(raw))
        if isinstance(quests, list):
            return quests[:5]
        logger.warning(
            "Game designer returned non-list JSON, using defaults. Parsed: %r, raw: %r",
            quests,
            raw,
        )
    except Exception as e:
        logger.warning(
            "Game designer JSON parse failed, returning defaults. Error: %s, raw: %r",
            e,
            raw if "raw" in locals() else "<no raw>",
        )

    return default_quests(analysis.get("soft_mode", False))


def default_quests(soft: bool) -> list[dict]:
    if soft:
        return [
            {"title": "Прогулка 15 минут", "description": "Спокойная ходьба на свежем воздухе", "category": "activity", "xp": 10},
            {"title": "Дыхание 4-7-8", "description": "3 цикла дыхательной техники 4-7-8", "category": "mindfulness", "xp": 10},
            {"title": "Стакан воды перед едой", "description": "Выпейте стакан воды за 15 мин до обеда", "category": "nutrition", "xp": 10},
        ]
    return [
        {"title": "8000 шагов", "description": "Пройдите 8000 шагов за день", "category": "activity", "xp": 25},
        {"title": "Белок в каждом приёме", "description": "Добавьте источник белка в каждый приём пищи", "category": "nutrition", "xp": 25},
        {"title": "Отбой до 23:00", "description": "Лягте спать до 23:00 сегодня", "category": "sleep", "xp": 25},
    ]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_json(text: str) -> str:
    """Try to extract a JSON object or array from LLM output that may contain
    markdown fences or extra text."""
    text = text.strip()
    if "```" in text:
        parts = text.split("```")
        for part in parts:
            part = part.strip()
            if part.startswith("json"):
                part = part[4:].strip()
            if part.startswith(("{", "[")):
                return part
    for start_char, end_char in [("{", "}"), ("[", "]")]:
        start = text.find(start_char)
        end = text.rfind(end_char)
        if start != -1 and end != -1 and end > start:
            return text[start : end + 1]
    return text
