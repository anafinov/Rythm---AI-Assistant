"""All Telegram handlers in one file: onboarding, check-in, quests, profile, RAG."""

from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, timedelta

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src import agents
from src.database import CheckIn, Quest, User, UserProgress
from src.gamification import add_xp, check_achievements, format_progress
from src.keyboards import (
    activity_keyboard,
    gender_keyboard,
    main_menu,
    quest_actions,
    scale_keyboard,
    skip_weight_keyboard,
)
from src.states import CheckInState, OnboardingState
from src.utils import build_roadmap, format_roadmap

logger = logging.getLogger(__name__)

router = Router()

CRISIS_KEYWORDS = ["бросить", "не могу", "сдаюсь", "плохо", "бесполезно", "устал", "ненавижу"]

CRISIS_REPLY = (
    "Я слышу тебя. То, что ты чувствуешь — нормально, и это не значит, что ты проиграл(а). "
    "Даже сам факт, что ты здесь и пишешь — уже говорит о твоей силе.\n\n"
    "Давай на сегодня упростим задачи до минимума. Иногда лучшее, что можно сделать — "
    "просто не отступать, даже маленькими шагами. 💛\n\n"
    "Хочешь, я переключу тебя на мягкий режим?"
)


# ═══════════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════════

async def get_or_create_user(session: AsyncSession, tg_id: int, username: str | None) -> User:
    result = await session.execute(select(User).where(User.telegram_id == tg_id))
    user = result.scalar_one_or_none()
    if not user:
        user = User(telegram_id=tg_id, username=username)
        session.add(user)
        await session.flush()
        progress = UserProgress(user_id=user.id)
        session.add(progress)
        await session.commit()
    return user


async def get_recent_checkins(session: AsyncSession, user_id: int, days: int = 7) -> list[CheckIn]:
    since = date.today() - timedelta(days=days)
    result = await session.execute(
        select(CheckIn)
        .where(CheckIn.user_id == user_id, CheckIn.date >= since)
        .order_by(CheckIn.date)
    )
    return list(result.scalars().all())


async def get_today_quests(session: AsyncSession, user_id: int) -> list[Quest]:
    result = await session.execute(
        select(Quest).where(Quest.user_id == user_id, Quest.date == date.today())
    )
    return list(result.scalars().all())


async def get_recent_quests(session: AsyncSession, user_id: int, days: int = 3) -> list[Quest]:
    since = date.today() - timedelta(days=days)
    result = await session.execute(
        select(Quest).where(Quest.user_id == user_id, Quest.date >= since)
    )
    return list(result.scalars().all())


async def get_progress(session: AsyncSession, user_id: int) -> UserProgress:
    result = await session.execute(
        select(UserProgress).where(UserProgress.user_id == user_id)
    )
    return result.scalar_one()


# ═══════════════════════════════════════════════════════════════════════════════
# /start
# ═══════════════════════════════════════════════════════════════════════════════

@router.message(Command("start"))
async def cmd_start(message: Message, session: AsyncSession, state: FSMContext):
    user = await get_or_create_user(session, message.from_user.id, message.from_user.username)
    if user.onboarded:
        await message.answer(
            f"С возвращением, <b>{message.from_user.first_name}</b>! 👋\n"
            "Выбери действие:",
            reply_markup=main_menu(),
        )
        return
    await message.answer(
        "👋 Привет! Я <b>Ритм</b> — твой персональный помощник по снижению веса.\n\n"
        "Я помогу тебе:\n"
        "• Поставить реалистичную цель\n"
        "• Получать ежедневные квесты\n"
        "• Отслеживать прогресс и зарабатывать XP\n\n"
        "Давай начнём! Какой у тебя <b>текущий вес</b> (в кг)?",
    )
    await state.set_state(OnboardingState.weight)


# ═══════════════════════════════════════════════════════════════════════════════
# Onboarding FSM
# ═══════════════════════════════════════════════════════════════════════════════

@router.message(OnboardingState.weight)
async def onb_weight(message: Message, state: FSMContext):
    try:
        w = float(message.text.replace(",", "."))
        assert 30 < w < 300
    except (ValueError, AssertionError):
        await message.answer("Введи корректный вес (например, 75.5):")
        return
    await state.update_data(weight=w)
    await message.answer("Отлично! Какой у тебя <b>рост</b> (в см)?")
    await state.set_state(OnboardingState.height)


@router.message(OnboardingState.height)
async def onb_height(message: Message, state: FSMContext):
    try:
        h = int(message.text)
        assert 100 < h < 250
    except (ValueError, AssertionError):
        await message.answer("Введи корректный рост (например, 175):")
        return
    await state.update_data(height=h)
    await message.answer("Сколько тебе <b>лет</b>?")
    await state.set_state(OnboardingState.age)


@router.message(OnboardingState.age)
async def onb_age(message: Message, state: FSMContext):
    try:
        a = int(message.text)
        assert 12 < a < 100
    except (ValueError, AssertionError):
        await message.answer("Введи корректный возраст (например, 25):")
        return
    await state.update_data(age=a)
    await message.answer("Укажи свой <b>пол</b>:", reply_markup=gender_keyboard())
    await state.set_state(OnboardingState.gender)


@router.callback_query(OnboardingState.gender, F.data.startswith("gender_"))
async def onb_gender(callback: CallbackQuery, state: FSMContext):
    gender = callback.data.split("_")[1]
    await state.update_data(gender=gender)
    await callback.message.edit_text(
        "Какой у тебя <b>уровень физической активности</b>?",
        reply_markup=activity_keyboard(),
    )
    await state.set_state(OnboardingState.activity)


@router.callback_query(OnboardingState.activity, F.data.startswith("act_"))
async def onb_activity(callback: CallbackQuery, state: FSMContext):
    activity = callback.data.split("_", 1)[1]
    await state.update_data(activity=activity)
    await callback.message.edit_text(
        "Какой <b>вес</b> ты хочешь достичь (в кг)?",
    )
    await state.set_state(OnboardingState.goal_weight)


@router.message(OnboardingState.goal_weight)
async def onb_goal(message: Message, state: FSMContext, session: AsyncSession):
    try:
        gw = float(message.text.replace(",", "."))
        assert 30 < gw < 300
    except (ValueError, AssertionError):
        await message.answer("Введи корректный целевой вес (например, 65):")
        return

    data = await state.get_data()
    user = await get_or_create_user(session, message.from_user.id, message.from_user.username)
    user.weight = data["weight"]
    user.height = data["height"]
    user.age = data["age"]
    user.gender = data["gender"]
    user.activity = data["activity"]
    user.goal_weight = gw
    user.onboarded = True
    await session.commit()

    roadmap = build_roadmap(
        weight=data["weight"],
        goal=gw,
        height=data["height"],
        age=data["age"],
        gender=data["gender"],
        activity=data["activity"],
    )
    await message.answer(format_roadmap(roadmap, data["weight"], gw))
    await message.answer("Готово! Теперь выбери действие:", reply_markup=main_menu())
    await state.clear()


# ═══════════════════════════════════════════════════════════════════════════════
# Check-in flow
# ═══════════════════════════════════════════════════════════════════════════════

@router.callback_query(F.data == "checkin")
async def start_checkin(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "📋 <b>Ежедневный чек-ин</b>\n\n"
        "Введи текущий <b>вес</b> (в кг) или нажми «Пропустить»:",
        reply_markup=skip_weight_keyboard(),
    )
    await state.set_state(CheckInState.weight)


@router.message(CheckInState.weight)
async def ci_weight(message: Message, state: FSMContext):
    try:
        w = float(message.text.replace(",", "."))
        assert 30 < w < 300
    except (ValueError, AssertionError):
        await message.answer("Введи корректный вес или нажми «Пропустить»:",
                             reply_markup=skip_weight_keyboard())
        return
    await state.update_data(ci_weight=w)
    await message.answer("Сколько часов ты <b>спал(а)</b> сегодня? (число, например 7.5)")
    await state.set_state(CheckInState.sleep)


@router.callback_query(CheckInState.weight, F.data == "checkin_skip_weight")
async def ci_skip_weight(callback: CallbackQuery, state: FSMContext):
    await state.update_data(ci_weight=None)
    await callback.message.edit_text(
        "Сколько часов ты <b>спал(а)</b> сегодня? (число, например 7.5)"
    )
    await state.set_state(CheckInState.sleep)


@router.message(CheckInState.sleep)
async def ci_sleep(message: Message, state: FSMContext):
    try:
        s = float(message.text.replace(",", "."))
        assert 0 <= s <= 24
    except (ValueError, AssertionError):
        await message.answer("Введи количество часов сна (например, 7):")
        return
    await state.update_data(ci_sleep=s)
    await message.answer(
        "Оцени уровень <b>стресса</b> за сегодня (1 — спокойно, 5 — очень напряжённо):",
        reply_markup=scale_keyboard("stress"),
    )
    await state.set_state(CheckInState.stress)


@router.callback_query(CheckInState.stress, F.data.startswith("stress_"))
async def ci_stress(callback: CallbackQuery, state: FSMContext):
    val = int(callback.data.split("_")[1])
    await state.update_data(ci_stress=val)
    await callback.message.edit_text(
        "Оцени своё <b>настроение</b> (1 — плохое, 5 — отличное):",
        reply_markup=scale_keyboard("mood"),
    )
    await state.set_state(CheckInState.mood)


@router.callback_query(CheckInState.mood, F.data.startswith("mood_"))
async def ci_mood(callback: CallbackQuery, state: FSMContext, session: AsyncSession, llm, kb):
    await callback.answer()
    val = int(callback.data.split("_")[1])
    data = await state.get_data()
    await state.clear()

    user = await get_or_create_user(session, callback.from_user.id, callback.from_user.username)

    if data.get("ci_weight"):
        user.weight = data["ci_weight"]

    checkin = CheckIn(
        user_id=user.id,
        weight=data.get("ci_weight"),
        sleep_hours=data.get("ci_sleep"),
        stress=data.get("ci_stress"),
        mood=val,
    )
    session.add(checkin)

    progress = await get_progress(session, user.id)
    today = date.today()
    if progress.last_checkin_date == today - timedelta(days=1):
        progress.streak_days += 1
    elif progress.last_checkin_date != today:
        progress.streak_days = 1
    progress.last_checkin_date = today

    await session.commit()

    await callback.message.edit_text("⏳ Анализирую данные…")

    try:
        recent = await get_recent_checkins(session, user.id)
        analysis = await asyncio.wait_for(
            agents.analyze_state(llm, user, recent), timeout=120,
        )

        recent_quests = await get_recent_quests(session, user.id)
        quest_dicts = await asyncio.wait_for(
            agents.generate_quests(llm, analysis, recent_quests), timeout=120,
        )

        for qd in quest_dicts:
            quest = Quest(
                user_id=user.id,
                title=qd.get("title", "Квест"),
                description=qd.get("description"),
                category=qd.get("category", "activity"),
                xp_reward=qd.get("xp", 10),
            )
            session.add(quest)
        await session.commit()

        summary = analysis.get("summary", "")
        mode_tag = " 🌿 <i>Мягкий режим активирован</i>" if analysis.get("soft_mode") else ""

        lines = [f"📊 <b>Результат чек-ина</b>{mode_tag}\n", summary, "\n⚔️ <b>Квесты на сегодня:</b>"]

        today_quests = await get_today_quests(session, user.id)
        for q in today_quests:
            if not q.completed:
                lines.append(f"\n• <b>{q.title}</b> ({q.category}) — {q.xp_reward} XP")
                if q.description:
                    lines.append(f"  <i>{q.description}</i>")

        await callback.message.answer(
            "\n".join(lines),
            reply_markup=main_menu(),
        )

    except Exception as e:
        logger.error("Check-in processing failed: %s", e, exc_info=True)
        await callback.message.answer(
            "✅ Чек-ин сохранён!\n\n"
            "Не удалось сгенерировать квесты — попробуй позже через меню.",
            reply_markup=main_menu(),
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Quests
# ═══════════════════════════════════════════════════════════════════════════════

@router.callback_query(F.data == "quests")
async def show_quests(callback: CallbackQuery, session: AsyncSession):
    user = await get_or_create_user(session, callback.from_user.id, callback.from_user.username)
    today_quests = await get_today_quests(session, user.id)
    if not today_quests:
        await callback.message.edit_text(
            "У тебя пока нет квестов на сегодня.\nСделай чек-ин, чтобы получить квесты!",
            reply_markup=main_menu(),
        )
        return

    for q in today_quests:
        status = "✅" if q.completed else "⏳"
        text = f"{status} <b>{q.title}</b> — {q.xp_reward} XP\n"
        if q.description:
            text += f"<i>{q.description}</i>\n"
        markup = None if q.completed else quest_actions(q.id)
        await callback.message.answer(text, reply_markup=markup)

    await callback.answer()


@router.callback_query(F.data.startswith("quest_done_"))
async def complete_quest(callback: CallbackQuery, session: AsyncSession):
    quest_id = int(callback.data.split("_")[-1])
    result = await session.execute(select(Quest).where(Quest.id == quest_id))
    quest = result.scalar_one_or_none()
    if not quest or quest.completed:
        await callback.answer("Квест уже выполнен или не найден.")
        return

    quest.completed = True
    quest.completed_at = datetime.utcnow()

    progress = await get_progress(session, quest.user_id)
    xp_msg = add_xp(progress, quest.xp_reward)
    achievement_msgs = check_achievements(progress, session)

    await session.commit()

    lines = [f"✅ Квест <b>«{quest.title}»</b> выполнен!", xp_msg]
    if achievement_msgs:
        lines.extend(achievement_msgs)

    await callback.message.edit_text("\n".join(lines))
    await callback.answer("Отлично!")


@router.callback_query(F.data.startswith("quest_skip_"))
async def skip_quest(callback: CallbackQuery, session: AsyncSession):
    quest_id = int(callback.data.split("_")[-1])
    result = await session.execute(select(Quest).where(Quest.id == quest_id))
    quest = result.scalar_one_or_none()
    if quest and not quest.completed:
        quest.completed = False
        await session.commit()
    await callback.message.edit_text(f"⏭ Квест «{quest.title}» пропущен.")
    await callback.answer()


@router.callback_query(F.data.startswith("quest_info_"))
async def quest_info(callback: CallbackQuery, session: AsyncSession, llm, kb):
    await callback.answer()
    quest_id = int(callback.data.split("_")[-1])
    result = await session.execute(select(Quest).where(Quest.id == quest_id))
    quest = result.scalar_one_or_none()
    if not quest:
        return

    await callback.message.answer("🔍 Ищу информацию…")
    question = f"Почему полезен квест: {quest.title}? Категория: {quest.category}"
    user = await get_or_create_user(session, callback.from_user.id, callback.from_user.username)
    context = {"weight": user.weight, "goal": user.goal_weight}
    answer = await agents.get_recommendation(llm, kb, question, context)
    await callback.message.answer(f"📚 <b>Зачем это нужно:</b>\n\n{answer}")


# ═══════════════════════════════════════════════════════════════════════════════
# Profile
# ═══════════════════════════════════════════════════════════════════════════════

@router.callback_query(F.data == "profile")
async def show_profile(callback: CallbackQuery, session: AsyncSession):
    user = await get_or_create_user(session, callback.from_user.id, callback.from_user.username)
    progress = await get_progress(session, user.id)
    text = format_progress(user, progress)
    await callback.message.edit_text(text, reply_markup=main_menu())


# ═══════════════════════════════════════════════════════════════════════════════
# Free-text: RAG questions & crisis detection
# ═══════════════════════════════════════════════════════════════════════════════

@router.callback_query(F.data == "ask")
async def ask_prompt(callback: CallbackQuery):
    await callback.message.edit_text(
        "Задай любой вопрос о питании, сне, стрессе или тренировках, "
        "и я найду ответ в базе знаний."
    )
    await callback.answer()


@router.message(~F.text.startswith("/"))
async def free_text(message: Message, session: AsyncSession, llm, kb, state: FSMContext):
    current_state = await state.get_state()
    if current_state is not None:
        return

    text_lower = message.text.lower()

    if any(kw in text_lower for kw in CRISIS_KEYWORDS):
        await message.answer(CRISIS_REPLY, reply_markup=main_menu())
        return

    user = await get_or_create_user(session, message.from_user.id, message.from_user.username)
    context = {
        "weight": user.weight,
        "goal": user.goal_weight,
        "gender": user.gender,
    }

    await message.answer("🔍 Ищу в базе знаний…")
    answer = await agents.get_recommendation(llm, kb, message.text, context)
    await message.answer(answer, reply_markup=main_menu())
