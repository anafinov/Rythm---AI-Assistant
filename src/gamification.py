"""XP, levels, streaks, and achievements."""

from __future__ import annotations

from src.database import User, UserProgress

STREAK_BONUS_THRESHOLD = 7
STREAK_MULTIPLIER = 1.5


def calc_level(xp: int) -> int:
    """Level = 1 + total_xp // 100."""
    return 1 + xp // 100


def add_xp(progress: UserProgress, base_xp: int) -> tuple[str, int, int]:
    """Add XP to user progress, apply streak bonus, recalculate level.
    Returns (message, old_xp, old_level) for achievement checks."""
    old_xp = progress.xp
    old_level = progress.level

    multiplier = STREAK_MULTIPLIER if progress.streak_days >= STREAK_BONUS_THRESHOLD else 1.0
    earned = int(base_xp * multiplier)
    progress.xp += earned
    progress.level = calc_level(progress.xp)

    bonus_note = f" (x{multiplier} streak bonus!)" if multiplier > 1 else ""
    msg = f"+{earned} XP{bonus_note}"

    if progress.level > old_level:
        msg += f"\n🎉 <b>Уровень {progress.level}!</b> Поздравляю!"

    return msg, old_xp, old_level


def check_achievements(progress: UserProgress, old_xp: int, old_level: int) -> list[str]:
    """Return list of achievement messages earned by crossing thresholds."""
    msgs = []

    if old_xp < 10 <= progress.xp:
        msgs.append("🏆 Ачивка: <b>Первый шаг</b> — ты начал путь!")
    if progress.streak_days == 7:
        msgs.append("🏆 Ачивка: <b>Неделя силы</b> — 7 дней подряд!")
    if progress.streak_days == 30:
        msgs.append("🏆 Ачивка: <b>Несокрушимый</b> — 30 дней подряд!")
    if old_level < 5 <= progress.level:
        msgs.append("🏆 Ачивка: <b>Уровень 5</b> — ты прокачиваешься!")

    return msgs


def format_progress(user: User, progress: UserProgress) -> str:
    """Format profile card."""
    next_level_xp = progress.level * 100
    xp_to_next = next_level_xp - progress.xp

    weight_info = ""
    if user.weight and user.goal_weight:
        diff = user.weight - user.goal_weight
        if diff > 0:
            weight_info = f"⚖️ До цели: {diff:.1f} кг\n"
        else:
            weight_info = "🎯 Цель достигнута!\n"

    return (
        "👤 <b>Твой профиль</b>\n\n"
        f"📊 Уровень: <b>{progress.level}</b>\n"
        f"✨ XP: {progress.xp} (до след. уровня: {xp_to_next})\n"
        f"🔥 Streak: {progress.streak_days} дней\n"
        f"{weight_info}"
    )
