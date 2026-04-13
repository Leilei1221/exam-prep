from __future__ import annotations
from datetime import date, timedelta
from typing import Optional


# 間隔複習算法：依錯誤次數決定下次複習間隔
REVIEW_INTERVALS = [1, 3, 7, 14, 30]


def calc_next_review(wrong_count: int) -> date:
    """根據錯誤次數計算下次複習日期（間隔複習算法）"""
    idx = min(wrong_count - 1, len(REVIEW_INTERVALS) - 1)
    days = REVIEW_INTERVALS[idx]
    return date.today() + timedelta(days=days)


def calc_accuracy(correct: int, total: int) -> float:
    """計算正確率（0.0~1.0）"""
    if total == 0:
        return 0.0
    return round(correct / total, 4)


def calc_streak(stats_list) -> int:
    """由 DailyStats 列表計算連續學習天數"""
    if not stats_list:
        return 0
    today = date.today()
    streak = 0
    check_date = today
    dates_set = {s.stat_date for s in stats_list if s.questions_done > 0}
    while check_date in dates_set:
        streak += 1
        check_date -= timedelta(days=1)
    return streak


def get_difficulty_label(difficulty: int) -> str:
    labels = {1: '簡單', 2: '中等', 3: '困難'}
    return labels.get(difficulty, '中等')


def get_difficulty_color(difficulty: int) -> str:
    colors = {1: 'success', 2: 'warning', 3: 'danger'}
    return colors.get(difficulty, 'warning')
