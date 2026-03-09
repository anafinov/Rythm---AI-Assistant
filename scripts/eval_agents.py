"""Simple evaluation script: run each agent on 10 test cases.

Usage:
    python scripts/eval_agents.py

Outputs JSON with inputs, outputs and latency per run, so you can compare
baseline vs future improvements.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.agents import analyze_state, generate_quests, get_recommendation
from src.config import Settings
from src.database import CheckIn, Quest, User
from src.llm import LLM
from src.rag import KnowledgeBase


@dataclass
class AnalystCase:
    id: str
    description: str
    user_weight: float
    user_goal_weight: float
    days: int
    weight_start: float
    weight_end: float
    avg_sleep: float
    avg_stress: int
    avg_mood: int


ANALYST_CASES: list[AnalystCase] = [
    AnalystCase(
        id="analyst_1",
        description="Стабильный вес, хороший сон и низкий стресс",
        user_weight=80,
        user_goal_weight=72,
        days=7,
        weight_start=80,
        weight_end=80,
        avg_sleep=7.5,
        avg_stress=2,
        avg_mood=4,
    ),
    AnalystCase(
        id="analyst_2",
        description="Плавное снижение веса, нормальный сон",
        user_weight=82,
        user_goal_weight=75,
        days=10,
        weight_start=84,
        weight_end=82,
        avg_sleep=7.0,
        avg_stress=2,
        avg_mood=3,
    ),
    AnalystCase(
        id="analyst_3",
        description="Набор веса, мало сна, высокий стресс",
        user_weight=90,
        user_goal_weight=80,
        days=10,
        weight_start=88,
        weight_end=90,
        avg_sleep=4.5,
        avg_stress=5,
        avg_mood=2,
    ),
    AnalystCase(
        id="analyst_4",
        description="Снижение веса, но сильный стресс",
        user_weight=78,
        user_goal_weight=70,
        days=14,
        weight_start=80,
        weight_end=78,
        avg_sleep=6.0,
        avg_stress=4,
        avg_mood=2,
    ),
    AnalystCase(
        id="analyst_5",
        description="Мало данных (3 дня), нормальные показатели",
        user_weight=65,
        user_goal_weight=60,
        days=3,
        weight_start=65,
        weight_end=65,
        avg_sleep=7.0,
        avg_stress=2,
        avg_mood=3,
    ),
    AnalystCase(
        id="analyst_6",
        description="Хронический недосып, но вес стабильный",
        user_weight=70,
        user_goal_weight=65,
        days=7,
        weight_start=70,
        weight_end=70,
        avg_sleep=4.0,
        avg_stress=3,
        avg_mood=2,
    ),
    AnalystCase(
        id="analyst_7",
        description="Резкое снижение веса за неделю",
        user_weight=75,
        user_goal_weight=70,
        days=7,
        weight_start=80,
        weight_end=75,
        avg_sleep=7.0,
        avg_stress=3,
        avg_mood=3,
    ),
    AnalystCase(
        id="analyst_8",
        description="Резкий набор веса, хороший сон",
        user_weight=85,
        user_goal_weight=78,
        days=7,
        weight_start=80,
        weight_end=85,
        avg_sleep=8.0,
        avg_stress=2,
        avg_mood=4,
    ),
    AnalystCase(
        id="analyst_9",
        description="Очень плохое настроение при нормальном сне",
        user_weight=68,
        user_goal_weight=62,
        days=5,
        weight_start=68,
        weight_end=68,
        avg_sleep=7.0,
        avg_stress=3,
        avg_mood=1,
    ),
    AnalystCase(
        id="analyst_10",
        description="Нет сна и высокий стресс, вес растёт",
        user_weight=95,
        user_goal_weight=85,
        days=7,
        weight_start=92,
        weight_end=95,
        avg_sleep=3.5,
        avg_stress=5,
        avg_mood=1,
    ),
]


METHOD_QUESTIONS: list[str] = [
    "Почему важно высыпаться, если я хочу худеть?",
    "Сколько белка мне нужно есть каждый день при снижении веса?",
    "Почему после стресса хочется сладкого и как с этим справиться?",
    "Что делать, если вес стоит на месте уже две недели?",
    "Полезно ли голодать один день в неделю?",
    "Как перестать срываться вечером и объедаться?",
    "Какая минимальная физическая активность даст эффект для здоровья?",
    "Можно ли есть поздно вечером, если я укладываюсь в калории?",
    "Как сон влияет на уровень кортизола и аппетит?",
    "Почему важно следить не только за весом, но и за окружением и привычками?",
]


GAME_ANALYSIS_CASES: list[dict[str, Any]] = [
    {
        "id": "game_1",
        "analysis": {
            "weight_trend": "stable",
            "avg_sleep": 7.0,
            "avg_stress": 2.0,
            "avg_mood": 4.0,
            "risk_level": "low",
            "soft_mode": False,
        },
        "recent_categories": [],
    },
    {
        "id": "game_2",
        "analysis": {
            "weight_trend": "losing",
            "avg_sleep": 7.5,
            "avg_stress": 2.0,
            "avg_mood": 4.0,
            "risk_level": "low",
            "soft_mode": False,
        },
        "recent_categories": ["activity", "nutrition"],
    },
    {
        "id": "game_3",
        "analysis": {
            "weight_trend": "gaining",
            "avg_sleep": 5.0,
            "avg_stress": 4.0,
            "avg_mood": 2.0,
            "risk_level": "high",
            "soft_mode": True,
        },
        "recent_categories": ["activity"],
    },
    {
        "id": "game_4",
        "analysis": {
            "weight_trend": "stable",
            "avg_sleep": 4.5,
            "avg_stress": 5.0,
            "avg_mood": 2.0,
            "risk_level": "high",
            "soft_mode": True,
        },
        "recent_categories": ["mindfulness"],
    },
    {
        "id": "game_5",
        "analysis": {
            "weight_trend": "losing",
            "avg_sleep": 6.0,
            "avg_stress": 3.0,
            "avg_mood": 3.0,
            "risk_level": "medium",
            "soft_mode": False,
        },
        "recent_categories": ["sleep", "nutrition"],
    },
    {
        "id": "game_6",
        "analysis": {
            "weight_trend": "gaining",
            "avg_sleep": 8.0,
            "avg_stress": 2.0,
            "avg_mood": 4.0,
            "risk_level": "medium",
            "soft_mode": False,
        },
        "recent_categories": ["activity", "sleep", "nutrition"],
    },
    {
        "id": "game_7",
        "analysis": {
            "weight_trend": "stable",
            "avg_sleep": 5.5,
            "avg_stress": 4.0,
            "avg_mood": 3.0,
            "risk_level": "high",
            "soft_mode": True,
        },
        "recent_categories": [],
    },
    {
        "id": "game_8",
        "analysis": {
            "weight_trend": "losing",
            "avg_sleep": 7.0,
            "avg_stress": 1.0,
            "avg_mood": 5.0,
            "risk_level": "low",
            "soft_mode": False,
        },
        "recent_categories": ["activity", "mindfulness"],
    },
    {
        "id": "game_9",
        "analysis": {
            "weight_trend": "gaining",
            "avg_sleep": 6.0,
            "avg_stress": 5.0,
            "avg_mood": 2.0,
            "risk_level": "high",
            "soft_mode": True,
        },
        "recent_categories": ["nutrition"],
    },
    {
        "id": "game_10",
        "analysis": {
            "weight_trend": "stable",
            "avg_sleep": 7.0,
            "avg_stress": 3.0,
            "avg_mood": 3.0,
            "risk_level": "medium",
            "soft_mode": False,
        },
        "recent_categories": ["activity", "sleep", "mindfulness", "nutrition"],
    },
]


async def eval_analyst(llm: LLM) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    today = date.today()
    for case in ANALYST_CASES:
        user = User(
            id=1,
            telegram_id=123456,
            username="eval_user",
            weight=case.user_weight,
            goal_weight=case.user_goal_weight,
            height=None,
            age=None,
            gender=None,
            activity=None,
            onboarded=True,
        )
        checkins: list[CheckIn] = []
        if case.days > 0:
            step = (case.weight_end - case.weight_start) / max(case.days - 1, 1)
            for i in range(case.days):
                d = today - timedelta(days=case.days - 1 - i)
                w = case.weight_start + step * i
                checkins.append(
                    CheckIn(
                        id=0,
                        user_id=user.id,
                        date=d,
                        weight=round(w, 1),
                        sleep_hours=case.avg_sleep,
                        stress=case.avg_stress,
                        mood=case.avg_mood,
                    )
                )

        t0 = time.time()
        analysis = await analyze_state(llm, user, checkins)
        elapsed = time.time() - t0

        results.append(
            {
                "case": asdict(case),
                "analysis": analysis,
                "elapsed_sec": elapsed,
            }
        )
    return results


async def eval_methodologist(llm: LLM, kb: KnowledgeBase) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    # One generic user context for all questions
    context = {
        "weight": 82.0,
        "goal_weight": 74.0,
        "gender": "female",
        "age": 32,
        "activity": "moderate",
    }
    for i, question in enumerate(METHOD_QUESTIONS, start=1):
        t0 = time.time()
        answer = await get_recommendation(llm, kb, question, context)
        elapsed = time.time() - t0
        results.append(
            {
                "id": f"method_{i}",
                "question": question,
                "context": context,
                "answer": answer,
                "elapsed_sec": elapsed,
            }
        )
    return results


async def eval_game_designer(llm: LLM) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    today = date.today()
    for case in GAME_ANALYSIS_CASES:
        recent_quests: list[Quest] = []
        for idx, cat in enumerate(case["recent_categories"], start=1):
            recent_quests.append(
                Quest(
                    id=idx,
                    user_id=1,
                    date=today - timedelta(days=idx),
                    title=f"Old quest {idx}",
                    description=None,
                    category=cat,
                    xp_reward=10,
                    completed=True,
                    completed_at=None,
                )
            )
        t0 = time.time()
        quests = await generate_quests(llm, case["analysis"], recent_quests)
        elapsed = time.time() - t0
        results.append(
            {
                "id": case["id"],
                "analysis": case["analysis"],
                "recent_categories": case["recent_categories"],
                "quests": quests,
                "elapsed_sec": elapsed,
            }
        )
    return results


async def main() -> None:
    settings = Settings()
    llm = LLM(
        model_path=settings.model_path,
        n_ctx=settings.model_n_ctx,
        n_threads=settings.model_n_threads,
        n_gpu_layers=settings.model_n_gpu_layers,
    )
    kb = KnowledgeBase(persist_dir=settings.kb_dir)

    analyst_results, method_results, game_results = await asyncio.gather(
        eval_analyst(llm),
        eval_methodologist(llm, kb),
        eval_game_designer(llm),
    )

    output = {
        "analyst": analyst_results,
        "methodologist": method_results,
        "game_designer": game_results,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())

