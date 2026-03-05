"""Tests for utils.py calculations."""

from src.utils import calc_bmr, calc_tdee, safe_weekly_loss, weeks_to_goal, build_roadmap


def test_bmr_male():
    bmr = calc_bmr(weight=80, height=180, age=25, gender="male")
    # 10*80 + 6.25*180 - 5*25 + 5 = 800 + 1125 - 125 + 5 = 1805
    assert bmr == 1805.0


def test_bmr_female():
    bmr = calc_bmr(weight=65, height=165, age=30, gender="female")
    # 10*65 + 6.25*165 - 5*30 - 161 = 650 + 1031.25 - 150 - 161 = 1370.25
    assert bmr == 1370.25


def test_tdee():
    tdee = calc_tdee(bmr=1800, activity="moderate")
    assert tdee == 1800 * 1.55


def test_safe_weekly_loss():
    lo, hi = safe_weekly_loss(80)
    assert lo == 0.40
    assert hi == 0.80


def test_weeks_to_goal():
    weeks = weeks_to_goal(current=80, goal=70, weekly_loss=0.5)
    assert weeks == 20


def test_weeks_to_goal_already_there():
    weeks = weeks_to_goal(current=70, goal=70, weekly_loss=0.5)
    assert weeks == 0


def test_build_roadmap_keys():
    rm = build_roadmap(80, 70, 180, 25, "male", "moderate")
    assert "bmr" in rm
    assert "tdee" in rm
    assert "estimated_weeks" in rm
    assert "target_calories" in rm
    assert rm["bmr"] > 0
    assert rm["estimated_weeks"] > 0
