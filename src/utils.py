"""Health calculations: BMR, TDEE, safe weight change timeline."""

from __future__ import annotations

import math

ACTIVITY_MULTIPLIERS = {
    "sedentary": 1.2,
    "light": 1.375,
    "moderate": 1.55,
    "high": 1.725,
}

SAFE_SURPLUS = 300
SAFE_DEFICIT = 400
SAFE_GAIN_PER_WEEK = (0.25, 0.5)


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


def weeks_to_goal(current: float, goal: float, weekly_rate: float) -> int:
    """Estimated weeks to reach goal weight at a given weekly rate."""
    if weekly_rate <= 0:
        return 0
    diff = abs(current - goal)
    if diff == 0:
        return 0
    return math.ceil(diff / weekly_rate)


def build_roadmap(
    weight: float, goal: float, height: int, age: int, gender: str, activity: str,
    mode: str = "active",
) -> dict:
    """Build a roadmap dict. Supports loss, gain, and maintenance modes."""
    bmr = calc_bmr(weight, height, age, gender)
    tdee = calc_tdee(bmr, activity)

    if mode == "maintenance":
        return {
            "bmr": round(bmr),
            "tdee": round(tdee),
            "mode": "maintenance",
            "target_calories": round(tdee),
        }

    gaining = goal > weight

    if gaining:
        target_calories = round(tdee + SAFE_SURPLUS)
        min_rate, max_rate = SAFE_GAIN_PER_WEEK
        avg_rate = (min_rate + max_rate) / 2
        est_weeks = weeks_to_goal(weight, goal, avg_rate)
        return {
            "bmr": round(bmr),
            "tdee": round(tdee),
            "mode": "gain",
            "safe_rate_per_week": f"{min_rate}–{max_rate} кг",
            "estimated_weeks": est_weeks,
            "target_calories": target_calories,
            "surplus": SAFE_SURPLUS,
        }
    else:
        min_loss, max_loss = safe_weekly_loss(weight)
        avg_loss = (min_loss + max_loss) / 2
        est_weeks = weeks_to_goal(weight, goal, avg_loss)
        target_calories = round(tdee - SAFE_DEFICIT)
        return {
            "bmr": round(bmr),
            "tdee": round(tdee),
            "mode": "loss",
            "safe_rate_per_week": f"{min_loss}–{max_loss} кг",
            "estimated_weeks": est_weeks,
            "target_calories": target_calories,
            "deficit": SAFE_DEFICIT,
        }


def format_roadmap(rm: dict, current: float, goal: float) -> str:
    """Format roadmap dict into a human-readable message."""
    mode = rm.get("mode", "loss")

    if mode == "maintenance":
        return (
            "🏠 <b>Режим удержания веса</b>\n\n"
            f"📊 Текущий вес: <b>{current} кг</b>\n"
            f"🔥 Базовый обмен (BMR): {rm['bmr']} ккал\n"
            f"⚡ Суточный расход (TDEE): {rm['tdee']} ккал\n"
            f"🍽 Целевое потребление: ~{rm['target_calories']} ккал/день (баланс)\n\n"
            "Главная задача — стабильность. Ешь по потребности, "
            "поддерживай активность и следи за привычками!"
        )

    header = (
        "🗺 <b>Твоя карта маршрута</b>\n\n"
        f"📊 Текущий вес: <b>{current} кг</b>\n"
        f"🎯 Цель: <b>{goal} кг</b>\n"
        f"🔥 Базовый обмен (BMR): {rm['bmr']} ккал\n"
        f"⚡ Суточный расход (TDEE): {rm['tdee']} ккал\n"
    )

    if mode == "gain":
        body = (
            f"🍽 Целевое потребление: ~{rm['target_calories']} ккал/день "
            f"(профицит {rm['surplus']} ккал)\n"
            f"📈 Безопасный темп набора: {rm['safe_rate_per_week']}/нед\n"
            f"🗓 Ориентировочный срок: ~{rm['estimated_weeks']} недель\n\n"
            "Для здорового набора веса важно есть в профицит калорий "
            "и заниматься силовыми тренировками, чтобы набирать мышечную массу, а не жир."
        )
    else:
        body = (
            f"🍽 Целевое потребление: ~{rm['target_calories']} ккал/день "
            f"(дефицит {rm['deficit']} ккал)\n"
            f"📉 Безопасный темп: {rm['safe_rate_per_week']}/нед\n"
            f"🗓 Ориентировочный срок: ~{rm['estimated_weeks']} недель\n\n"
            "Помни: это марафон, а не спринт. Мы будем корректировать план каждую неделю!"
        )

    return header + body
