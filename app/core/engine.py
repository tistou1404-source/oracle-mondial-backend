"""core/engine.py — Moteur de pronostic Elo + Poisson + value bets."""
from __future__ import annotations
import math
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Team:
    name: str
    elo: float = 1500.0
    attack: float = 1.35
    defense: float = 1.10
    recent_form: list[float] = field(default_factory=list)

    def form_factor(self) -> float:
        if not self.recent_form:
            return 1.0
        last = self.recent_form[-5:]
        return 1.0 + (sum(last) / len(last) - 0.5) * 0.25


def poisson_pmf(k: int, lam: float) -> float:
    return (lam ** k) * math.exp(-lam) / math.factorial(k)


def elo_expected(elo_a: float, elo_b: float, home_adv: float = 0.0) -> float:
    return 1.0 / (1.0 + 10 ** (-((elo_a + home_adv) - elo_b) / 400.0))


def update_elo(elo: float, expected: float, actual: float, k: float = 30.0) -> float:
    """actual: 1=victoire, 0.5=nul, 0=défaite."""
    return elo + k * (actual - expected)


def expected_goals(a: Team, b: Team, elo_prob_a: float) -> tuple[float, float]:
    base_a = a.attack * b.defense / 1.10
    base_b = b.attack * a.defense / 1.10
    tilt = (elo_prob_a - 0.5) * 1.6
    lam_a = max(0.15, base_a * (1 + tilt) * a.form_factor())
    lam_b = max(0.15, base_b * (1 - tilt) * b.form_factor())
    return lam_a, lam_b


def score_matrix(lam_a: float, lam_b: float, max_goals: int = 8):
    return [[poisson_pmf(i, lam_a) * poisson_pmf(j, lam_b)
             for j in range(max_goals + 1)] for i in range(max_goals + 1)]


def outcome_probabilities(matrix) -> dict[str, float]:
    win_a = draw = win_b = 0.0
    for i, row in enumerate(matrix):
        for j, p in enumerate(row):
            if i > j: win_a += p
            elif i == j: draw += p
            else: win_b += p
    t = win_a + draw + win_b
    return {"win_a": win_a / t, "draw": draw / t, "win_b": win_b / t}


def top_scores(matrix, n: int = 5):
    flat = [(f"{i}-{j}", p) for i, row in enumerate(matrix) for j, p in enumerate(row)]
    flat.sort(key=lambda x: x[1], reverse=True)
    return flat[:n]


def detect_value_bets(probs, odds: dict[str, float], margin: float = 0.03):
    labels = {"win_a": "Victoire 1", "draw": "Nul", "win_b": "Victoire 2"}
    out = []
    for key, label in labels.items():
        if key not in odds or odds[key] <= 1:
            continue
        p_imp = 1.0 / odds[key]
        edge = probs[key] - p_imp
        out.append({
            "issue": label, "proba_modele": round(probs[key], 3),
            "cote": odds[key], "proba_implicite": round(p_imp, 3),
            "edge": round(edge, 3), "rendement_espere": round(probs[key] * odds[key] - 1, 3),
            "value_bet": edge > margin,
        })
    return out


def predict_match(a: Team, b: Team, odds: Optional[dict] = None, neutral: bool = True) -> dict:
    home = 0.0 if neutral else 65.0
    p_a = elo_expected(a.elo, b.elo, home)
    lam_a, lam_b = expected_goals(a, b, p_a)
    matrix = score_matrix(lam_a, lam_b)
    probs = outcome_probabilities(matrix)
    res = {
        "match": f"{a.name} vs {b.name}",
        "buts_attendus": {a.name: round(lam_a, 2), b.name: round(lam_b, 2)},
        "probabilites": {k: round(v, 3) for k, v in probs.items()},
        "scores_probables": top_scores(matrix, 5),
    }
    if odds:
        res["value_bets"] = detect_value_bets(probs, odds)
    return res
