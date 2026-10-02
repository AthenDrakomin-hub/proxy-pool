"""代理性能评分引擎 + 存活时间预估"""
from typing import Dict


def calculate_score(latency: float, success_rate: float,
                    success_count: int, fail_count: int) -> Dict:
    """
    综合性能评分
    维度：延迟(40%) + 成功率(30%) + 稳定性(30%)
    返回: {score, grade, latency_score, rate_score, stability_score}
    """
    latency = latency or 999.0

    # === 延迟分 (0-100) ===
    if latency < 0.5:
        latency_score = 100
    elif latency < 1:
        latency_score = 92
    elif latency < 2:
        latency_score = 80
    elif latency < 3:
        latency_score = 65
    elif latency < 5:
        latency_score = 48
    elif latency < 8:
        latency_score = 30
    else:
        latency_score = 12

    # === 成功率分 (0-100) ===
    rate_score = success_rate * 100

    # === 稳定性分 (0-100) ===
    total = success_count + fail_count
    if total == 0:
        stability_score = 50
    elif fail_count == 0:
        stability_score = min(70 + success_count * 3, 100)
    else:
        stability_score = (success_count / total) * 80 + 20

    # === 综合评分 ===
    total_score = latency_score * 0.40 + rate_score * 0.30 + stability_score * 0.30

    # === 等级 ===
    if total_score >= 88:
        grade = "S"
    elif total_score >= 75:
        grade = "A"
    elif total_score >= 60:
        grade = "B"
    elif total_score >= 45:
        grade = "C"
    else:
        grade = "D"

    return {
        "score": round(total_score, 1),
        "grade": grade,
        "latency_score": round(latency_score, 1),
        "rate_score": round(rate_score, 1),
        "stability_score": round(stability_score, 1),
    }


def estimate_ttl(score: float, latency: float) -> int:
    """
    预估代理剩余存活时间（秒）
    基于性能评分：高分代理通常更稳定，存活更久
    """
    base = 300
    score_bonus = (score / 10) * 45
    if latency < 2:
        latency_bonus = 60
    elif latency < 5:
        latency_bonus = 30
    else:
        latency_bonus = 0
    ttl = int(base + score_bonus + latency_bonus)
    return min(ttl, 1800)


def grade_color(grade: str) -> str:
    """等级对应颜色"""
    return {
        "S": "#fbbf24",
        "A": "#4ade80",
        "B": "#60a5fa",
        "C": "#fb923c",
        "D": "#f87171",
    }.get(grade, "#888")
