"""main.py — Serveur FastAPI : expose le moteur + déclenche la MAJ quotidienne."""
from __future__ import annotations
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session
from apscheduler.schedulers.background import BackgroundScheduler

from .db.session import get_db, init_db, SessionLocal
from .db.models import TeamModel, MatchModel, PredictionLog
from .core.engine import Team, predict_match
from .jobs.daily_update import run as run_daily

scheduler = BackgroundScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    scheduler.add_job(run_daily, "cron", hour=6, minute=0, id="daily_update")
    scheduler.start()
    yield
    scheduler.shutdown()


app = FastAPI(title="Oracle Mondial 2026", version="1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])


class TeamIn(BaseModel):
    name: str
    elo: float = 1500
    attack: float = 1.35
    defense: float = 1.10
    recent_form: list[float] = []


class MatchPredictIn(BaseModel):
    home: TeamIn
    away: TeamIn
    odds: dict[str, float] | None = None
    neutral: bool = True


@app.get("/health")
def health():
    return {"status": "ok", "time": datetime.utcnow().isoformat()}


@app.post("/predict")
def predict(body: MatchPredictIn):
    """Pronostic à la volée (sans persistance)."""
    a = Team(body.home.name, body.home.elo, body.home.attack,
             body.home.defense, body.home.recent_form)
    b = Team(body.away.name, body.away.elo, body.away.attack,
             body.away.defense, body.away.recent_form)
    return predict_match(a, b, odds=body.odds, neutral=body.neutral)


@app.get("/teams")
def list_teams(db: Session = Depends(get_db)):
    return db.scalars(select(TeamModel)).all()


@app.get("/matches")
def list_matches(status: str | None = None, db: Session = Depends(get_db)):
    q = select(MatchModel)
    if status:
        q = q.where(MatchModel.status == status)
    return db.scalars(q).all()


@app.get("/matches/{match_id}/prediction")
def match_prediction(match_id: int, db: Session = Depends(get_db)):
    m = db.get(MatchModel, match_id)
    if not m:
        raise HTTPException(404, "Match introuvable")
    if not m.prediction:
        raise HTTPException(404, "Pas encore de pronostic calculé")
    return m.prediction
@app.post("/admin/run-update")
def trigger_update():
    """Déclenche manuellement la mise à jour quotidienne (utile pour tester)."""
    run_daily()
    return {"status": "update terminée", "time": datetime.utcnow().isoformat()}

@app.post("/admin/reset")
def admin_reset(db: Session = Depends(get_db)):
    """Vide équipes, matchs et logs. À lancer une fois après avoir changé les
    forces de départ, puis relancer /admin/run-update pour tout recréer."""
    db.query(PredictionLog).delete()
    db.query(MatchModel).delete()
    db.query(TeamModel).delete()
    db.commit()
    return {"status": "base vidée", "time": datetime.utcnow().isoformat()}


@app.get("/stats/model-performance")
def model_perf(db: Session = Depends(get_db)):
    """Qualité moyenne des pronostics (score de Brier, plus bas = meilleur)."""
    logs = db.scalars(select(PredictionLog).where(
        PredictionLog.brier_score.isnot(None))).all()
    if not logs:
        return {"n": 0, "brier_moyen": None}
    avg = sum(l.brier_score for l in logs) / len(logs)
    return {"n": len(logs), "brier_moyen": round(avg, 4)}
