"""Health calculations: BMR, TDEE, safe weight-loss timeline."""

from __future__ import annotations

import math

ACTIVITY_MULTIPLIERS = {
    "sedentary": 1.2,
    "light": 1.375,
    "moderate": 1.55,
    "high": 1.725,
}


def calc_bmr(weight: float, height: int, age: int, gender: str) -> float:
    """Mifflin-St Jeor equation. Returns BMR in kcal/day."""
    base = 10 * weight + 6.25 * height - 5 * age
    if gender == "male":
        return base + 5
    return base - 161


def calc_tdee(bmr: float, activity: str) -> float:
    """Total Daily Energy Expenditure."""
    return bmr * ACTIVITY_MULTIPLIERS.get(activity, 1.2)


def safe_weekly_loss(weight: float) -> tuple[float, float]:
    """Returns (min_kg, max_kg) for safe weekly loss: 0.5%-1% of body weight."""
    return round(weight * 0.005, 2), round(weight * 0.01, 2)


def weeks_to_goal(current: float, goal: float, weekly_loss: float) -> int:
    """Estimated weeks to reach goal weight at a given weekly loss rate."""
    if weekly_loss <= 0 or current <= goal:
        return 0
    return math.ceil((current - goal) / weekly_loss)


def build_roadmap(
    weight: float, goal: float, height: int, age: int, gender: str, activity: str
) -> dict:
    """Build a simple roadmap dict shown to the user after onboarding."""
    bmr = calc_bmr(weight, height, age, gender)
    tdee = calc_tdee(bmr, activity)
    min_loss, max_loss = safe_weekly_loss(weight)
    avg_loss = (min_loss + max_loss) / 2
    est_weeks = weeks_to_goal(weight, goal, avg_loss)
    target_calories = round(tdee - 400)

    return {
        "bmr": round(bmr),
        "tdee": round(tdee),
        "safe_loss_per_week": f"{min_loss}–{max_loss} кг",
        "estimated_weeks": est_weeks,
        "target_calories": target_calories,
        "deficit": 400,
    }


def format_roadmap(rm: dict, current: float, goal: float) -> str:
    """Format roadmap dict into a human-readable message."""
    return (
        "🗺 <b>Твоя карта маршрута</b>\n\n"
        f"📊 Текущий вес: <b>{current} кг</b>\n"
        f"🎯 Цель: <b>{goal} кг</b>\n"
        f"🔥 Базовый обмен (BMR): {rm['bmr']} ккал\n"
        f"⚡ Суточный расход (TDEE): {rm['tdee']} ккал\n"
        f"🍽 Целевое потребление: ~{rm['target_calories']} ккал/день "
        f"(дефицит {rm['deficit']} ккал)\n"
        f"📉 Безопасный темп: {rm['safe_loss_per_week']}/нед\n"
        f"🗓 Ориентировочный срок: ~{rm['estimated_weeks']} недель\n\n"
        "Помни: это марафон, а не спринт. Мы будем корректировать план каждую неделю!"
    )
