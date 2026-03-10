"""Three agent functions: analyst, methodologist, game designer.

Each agent is a plain async function that builds a prompt, calls LLM, and
returns structured data. No complex LangChain graphs — just prompt chains.
"""

from __future__ import annotations

import json
import logging

import pandas as pd

from src.database import CheckIn, Quest, User
from src.llm import LLM
from src.rag import KnowledgeBase

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Agent 1 — Analyst
# ---------------------------------------------------------------------------

ADVICE_SYSTEM = (
    "Ты — дружелюбный коуч по здоровью. На основе данных и заметок пользователя "
    "дай один конкретный, персональный совет на 1-2 предложения. "
    "Без общих фраз — только то, что полезно именно этому человеку прямо сейчас."
)

ADVICE_PROMPT = """\
Метрики за последнюю неделю:
- Тренд веса: {trend}
- Средний сон: {sleep} ч, стресс: {stress}/5, настроение: {mood}/5
- Мягкий режим: {soft_mode}

Заметки пользователя за последние дни:
{notes}

Дай один короткий персональный совет (1-2 предложения).
"""


async def analyze_state(
    llm: LLM, user: User, checkins: list[CheckIn]
) -> dict:
    """Two-phase analysis: deterministic metrics + LLM advice from notes."""
    if not checkins:
        return _default_analysis()

    user_mode = getattr(user, "mode", "active") or "active"
    stats = _compute_stats(user, checkins)
    analysis = _heuristic_analysis(stats, user_mode=user_mode)

    notes = [c.note for c in checkins if c.note]
    if notes:
        try:
            advice = await _generate_advice(llm, analysis, notes)
            analysis["advice"] = advice
        except Exception as e:
            logger.warning("Advice generation failed: %s", e)

    return analysis


async def _generate_advice(llm: LLM, analysis: dict, notes: list[str]) -> str:
    trend_labels = {"losing": "снижается", "stable": "стабильный", "gaining": "растёт"}
    notes_text = "\n".join(f"- {n}" for n in notes[-5:])

    prompt = ADVICE_PROMPT.format(
        trend=trend_labels.get(analysis["weight_trend"], "?"),
        sleep=analysis["avg_sleep"],
        stress=analysis["avg_stress"],
        mood=analysis["avg_mood"],
        soft_mode="да" if analysis["soft_mode"] else "нет",
        notes=notes_text,
    )
    return await llm.generate(prompt, system=ADVICE_SYSTEM, temperature=0.5, max_tokens=128)


def _compute_stats(user: User, checkins: list[CheckIn]) -> dict:
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
    return {
        "current_weight": user.weight,
        "goal_weight": user.goal_weight,
        "days_tracked": len(df),
        "avg_sleep": round(df["sleep_hours"].mean(), 1) if df["sleep_hours"].notna().any() else None,
        "avg_stress": round(df["stress"].mean(), 1) if df["stress"].notna().any() else None,
        "avg_mood": round(df["mood"].mean(), 1) if df["mood"].notna().any() else None,
        "weight_first": df["weight"].dropna().iloc[0] if df["weight"].notna().any() else None,
        "weight_last": df["weight"].dropna().iloc[-1] if df["weight"].notna().any() else None,
    }


def _default_analysis() -> dict:
    return {
        "weight_trend": "stable",
        "avg_sleep": 7.0,
        "avg_stress": 2.0,
        "avg_mood": 3.0,
        "risk_level": "low",
        "soft_mode": False,
        "summary": "Недостаточно данных для полного анализа. Продолжайте отмечать чек-ины!",
    }


def _enforce_rules(result: dict, stats: dict, user_mode: str = "active") -> dict:
    """Override soft_mode, risk_level and summary with deterministic logic."""
    avg_stress = float(result.get("avg_stress") or stats.get("avg_stress") or 2.0)
    avg_sleep = float(result.get("avg_sleep") or stats.get("avg_sleep") or 7.0)
    avg_mood = float(result.get("avg_mood") or stats.get("avg_mood") or 3.0)
    trend = result.get("weight_trend", "stable")
    if trend not in ("losing", "stable", "gaining"):
        trend = "stable"

    soft_mode = avg_stress >= 4 or avg_sleep < 5 or avg_mood <= 2

    if user_mode == "maintenance":
        risk_level = "high" if soft_mode else ("medium" if trend != "stable" else "low")
    else:
        risk_level = "high" if soft_mode else ("medium" if trend == "gaining" else "low")

    return {
        "weight_trend": trend,
        "avg_sleep": avg_sleep,
        "avg_stress": avg_stress,
        "avg_mood": avg_mood,
        "risk_level": risk_level,
        "soft_mode": soft_mode,
        "user_mode": user_mode,
        "summary": _build_summary(trend, avg_sleep, avg_stress, avg_mood, soft_mode, user_mode),
    }


def _build_summary(
    trend: str, avg_sleep: float, avg_stress: float, avg_mood: float,
    soft_mode: bool, user_mode: str = "active",
) -> str:
    parts: list[str] = []

    if user_mode == "maintenance":
        if trend == "stable":
            parts.append("Вес стабильный — отличный результат! 🏠")
        elif trend == "gaining":
            parts.append("Вес растёт — обрати внимание на калории.")
        else:
            parts.append("Вес снижается — убедись, что ты ешь достаточно.")
    else:
        trend_labels = {"losing": "снижается", "stable": "стабильный", "gaining": "растёт"}
        parts.append(f"Тренд веса: {trend_labels.get(trend, trend)}.")

    if soft_mode:
        reasons = []
        if avg_stress >= 4:
            reasons.append(f"высокий стресс ({avg_stress}/5)")
        if avg_sleep < 5:
            reasons.append(f"мало сна ({avg_sleep} ч)")
        if avg_mood <= 2:
            reasons.append(f"низкое настроение ({avg_mood}/5)")
        parts.append("Мягкий режим: " + ", ".join(reasons) + ".")
    else:
        good = []
        if avg_sleep >= 7:
            good.append("хороший сон")
        if avg_stress <= 2:
            good.append("низкий стресс")
        if avg_mood >= 4:
            good.append("хорошее настроение")
        if good:
            parts.append("Показатели в норме: " + ", ".join(good) + ".")

    return " ".join(parts)


def _heuristic_analysis(stats: dict, user_mode: str = "active") -> dict:
    """Deterministic analysis from computed stats."""
    w_first = stats.get("weight_first")
    w_last = stats.get("weight_last")
    if w_first and w_last:
        diff = w_last - w_first
        trend = "losing" if diff < -0.3 else ("gaining" if diff > 0.3 else "stable")
    else:
        trend = "stable"

    return _enforce_rules(
        {
            "weight_trend": trend,
            "avg_sleep": stats.get("avg_sleep"),
            "avg_stress": stats.get("avg_stress"),
            "avg_mood": stats.get("avg_mood"),
        },
        stats,
        user_mode=user_mode,
    )


# ---------------------------------------------------------------------------
# Agent 2 — Methodologist (RAG)
# ---------------------------------------------------------------------------

METHODOLOGIST_SYSTEM = (
    "Ты — нутрициолог и специалист по поведенческой терапии. "
    "Отвечаешь кратко, дружелюбно и со ссылками на научные данные из базы знаний. "
    "Если в базе нет ответа, честно скажи об этом. НЕ выдумывай исследования или статистику. "
    "Ты отвечаешь ТОЛЬКО на вопросы о здоровье, питании, сне, стрессе, физической активности "
    "и снижении веса. Если вопрос не по теме, вежливо скажи, что можешь помочь только "
    "с вопросами о здоровье и привычках."
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
    "по здоровому образу жизни. Отвечай ТОЛЬКО валидным JSON-массивом, без пояснений."
)

GAME_DESIGNER_PROMPT = """\
Профиль пользователя:
- Цель: {goal_label}
- Режим: {mode}
- Средний стресс: {stress}/5
- Средний сон: {sleep} ч
- Тренд веса: {trend}
- Уже выполненные категории за последние 3 дня: {recent_categories}
{notes_section}
Сгенерируй ровно 3 квеста на сегодня.
Категории: nutrition, activity, mindfulness, sleep.
Если режим «мягкий» — выбирай лёгкие задания (прогулка вместо тренировки, дыхание вместо медитации).
Если цель — удержание веса, фокусируйся на закреплении привычек: сбалансированное питание, \
регулярная активность, контроль порций, стабильный режим сна. НЕ давай задания на дефицит калорий.
Учитывай заметки пользователя: если он упоминает конкретные продукты, активности или жалобы — \
подстрой квесты под его реальную жизнь.

Формат — JSON-массив:
[
  {{"title": "...", "description": "...", "category": "...", "xp": <10|25|50>}},
  ...
]
"""

_GOAL_LABELS = {
    "maintenance": "удержание веса",
    "active": "изменение веса",
}


async def generate_quests(
    llm: LLM, analysis: dict, recent_quests: list[Quest], notes: list[str] | None = None,
) -> list[dict]:
    """Generate 3 daily quests based on current analysis and user notes."""
    recent_cats = list({q.category for q in recent_quests if q.completed})

    notes_section = ""
    if notes:
        notes_text = "\n".join(f"  - {n}" for n in notes[-5:])
        notes_section = f"\nЗаметки пользователя за последние дни:\n{notes_text}\n"

    user_mode = analysis.get("user_mode", "active")
    mode = "мягкий" if analysis.get("soft_mode") else "обычный"
    prompt = GAME_DESIGNER_PROMPT.format(
        goal_label=_GOAL_LABELS.get(user_mode, "изменение веса"),
        mode=mode,
        stress=analysis.get("avg_stress", "?"),
        sleep=analysis.get("avg_sleep", "?"),
        trend=analysis.get("weight_trend", "stable"),
        recent_categories=", ".join(recent_cats) or "нет данных",
        notes_section=notes_section,
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

    return default_quests(analysis.get("soft_mode", False), user_mode)


def default_quests(soft: bool, user_mode: str = "active") -> list[dict]:
    if soft:
        return [
            {"title": "Прогулка 15 минут", "description": "Спокойная ходьба на свежем воздухе", "category": "activity", "xp": 10},
            {"title": "Дыхание 4-7-8", "description": "3 цикла дыхательной техники 4-7-8", "category": "mindfulness", "xp": 10},
            {"title": "Стакан воды перед едой", "description": "Выпейте стакан воды за 15 мин до обеда", "category": "nutrition", "xp": 10},
        ]
    if user_mode == "maintenance":
        return [
            {"title": "Сбалансированный обед", "description": "Белок + овощи + сложные углеводы в одном приёме", "category": "nutrition", "xp": 25},
            {"title": "30 минут активности", "description": "Любая физическая активность на ваш выбор", "category": "activity", "xp": 25},
            {"title": "Отбой до 23:00", "description": "Стабильный режим сна — ключ к удержанию веса", "category": "sleep", "xp": 25},
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
