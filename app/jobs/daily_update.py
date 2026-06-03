"""jobs/daily_update.py — Mise à jour quotidienne automatique."""
from __future__ import annotations
from datetime import datetime, timedelta

from sqlalchemy import select
from ..db.session import SessionLocal, init_db
from ..db.models import TeamModel, MatchModel, PredictionLog
from ..connectors import odds as odds_conn
from ..connectors import football as fb_conn
from ..connectors import sentiment as sent_conn

from ..core.engine import (Team, elo_expected, update_elo, predict_match)
from ..core.team_ratings import starting_profile


def _get_or_create_team(db, name: str) -> TeamModel:
    t = db.scalar(select(TeamModel).where(TeamModel.name == name))
    if not t:
        elo, attack, defense = starting_profile(name)
        t = TeamModel(name=name, elo=elo, attack=attack, defense=defense)
        db.add(t)
        db.flush()
    return t

def _outcome(home_goals: int, away_goals: int) -> tuple[float, float, str]:
    if home_goals > away_goals:
        return 1.0, 0.0, "win_a"
    if home_goals < away_goals:
        return 0.0, 1.0, "win_b"
    return 0.5, 0.5, "draw"


def ingest_results(db) -> int:
    """Étapes 1 & 2 : résultats de la veille + recalibrage Elo/forme."""
    yesterday = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")
    fixtures = fb_conn.fetch_fixtures(date=yesterday)
    updated = 0
    for fx in fixtures:
        if fx["status"] != "finished" or fx["home_goals"] is None:
            continue
        home = _get_or_create_team(db, fx["home"])
        away = _get_or_create_team(db, fx["away"])

        act_h, act_a, outcome = _outcome(fx["home_goals"], fx["away_goals"])
        exp_h = elo_expected(home.elo, away.elo)
        new_home = update_elo(home.elo, exp_h, act_h)
        new_away = update_elo(away.elo, 1 - exp_h, act_a)
        home.elo, away.elo = new_home, new_away
        home.recent_form = (home.recent_form or [])[-4:] + [act_h]
        away.recent_form = (away.recent_form or [])[-4:] + [act_a]

        m = db.scalar(select(MatchModel).where(
            MatchModel.external_id == fx["external_id"]))
        if m and m.prediction:
            p = m.prediction["probabilites"]
            target = {"win_a": 0, "draw": 0, "win_b": 0}
            target[outcome] = 1
            brier = sum((p[k] - target[k]) ** 2 for k in target) / 3
            db.add(PredictionLog(match_id=m.id, probs=p,
                                 actual_outcome=outcome, brier_score=brier))
        if m:
            m.status = "finished"
            m.home_goals, m.away_goals = fx["home_goals"], fx["away_goals"]
        updated += 1
    db.commit()
    return updated


def _parse_kickoff(value: str | None):
    """Convertit une date ISO de l'API en datetime (ou None)."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def sync_fixtures(db) -> int:
    """Crée/met à jour TOUS les matchs du tournoi en base (même à venir).
    C'est ce qui peuple la liste des matchs visible dans l'app.
    """
    fixtures = fb_conn.fetch_fixtures()  # sans date = tout le tournoi
    synced = 0
    for fx in fixtures:
        home = _get_or_create_team(db, fx["home"])
        away = _get_or_create_team(db, fx["away"])
        m = db.scalar(select(MatchModel).where(
            MatchModel.external_id == fx["external_id"]))
        if not m:
            m = MatchModel(external_id=fx["external_id"],
                           home_team_id=home.id, away_team_id=away.id,
                           neutral=True)
            db.add(m)
        m.home_team_id = home.id
        m.away_team_id = away.id
        m.kickoff = _parse_kickoff(fx.get("kickoff"))
        m.status = fx["status"]
        if fx.get("home_goals") is not None:
            m.home_goals = fx["home_goals"]
            m.away_goals = fx["away_goals"]
        synced += 1
    db.commit()
    return synced


def refresh_sentiment(db) -> None:
    """Étape 3b : met à jour le sentiment de chaque équipe."""
    for team in db.scalars(select(TeamModel)).all():
        team.sentiment_score = sent_conn.team_sentiment(team.name)
    db.commit()


def _team_key(name: str) -> str:
    """Normalise un nom d'équipe pour l'associer de façon robuste
    (minuscules, sans accents/ponctuation/espaces). 'South Africa' -> 'southafrica'."""
    import unicodedata
    if not name:
        return ""
    n = unicodedata.normalize("NFKD", name)
    n = "".join(c for c in n if not unicodedata.combining(c))
    return "".join(c.lower() for c in n if c.isalnum())


def _match_key(home: str, away: str) -> str:
    return _team_key(home) + "|" + _team_key(away)


def repredict_upcoming(db) -> int:
    """Étapes 3a & 4 : rafraîchit cotes et recalcule les pronostics à venir."""
    odds_list = odds_conn.fetch_odds()
    # Association par NOMS d'équipes (les identifiants diffèrent entre sources).
    odds_by_teams = {_match_key(o.get("home"), o.get("away")): o
                     for o in odds_list}

    upcoming = db.scalars(select(MatchModel).where(
        MatchModel.status == "scheduled")).all()
    count = 0
    for m in upcoming:
        if not m.home or not m.away:
            continue
        # injecte le bonus de sentiment dans la forme effective
        def to_engine(tm: TeamModel) -> Team:
            bonus = sent_conn.sentiment_to_form_bonus(tm.sentiment_score or 0)
            form = list(tm.recent_form or [])
            if form:
                form[-1] = min(1.0, max(0.0, form[-1] + bonus))
            return Team(tm.name, tm.elo, tm.attack, tm.defense, form)

        o = odds_by_teams.get(_match_key(m.home.name, m.away.name))
        if o:
            m.odds = o["odds"]
        m.prediction = predict_match(
            to_engine(m.home), to_engine(m.away),
            odds=m.odds, neutral=m.neutral)
        count += 1
    db.commit()
    return count


def run():
    init_db()
    db = SessionLocal()
    try:
        n_res = ingest_results(db)
        n_sync = sync_fixtures(db)
        refresh_sentiment(db)
        n_pred = repredict_upcoming(db)
        print(f"[{datetime.utcnow():%Y-%m-%d %H:%M}] "
              f"MAJ terminée — {n_res} résultats ingérés, "
              f"{n_sync} matchs synchronisés, "
              f"{n_pred} pronostics recalculés.")
    finally:
        db.close()


if __name__ == "__main__":
    run()
