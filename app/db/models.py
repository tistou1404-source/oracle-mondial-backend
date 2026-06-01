"""db/models.py — Schéma de base de données (SQLAlchemy)."""
from __future__ import annotations
from datetime import datetime
from sqlalchemy import (Column, Integer, String, Float, DateTime, ForeignKey,
                        JSON, Boolean)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class TeamModel(Base):
    __tablename__ = "teams"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    elo = Column(Float, default=1500.0)
    attack = Column(Float, default=1.35)
    defense = Column(Float, default=1.10)
    recent_form = Column(JSON, default=list)
    squad = Column(JSON, default=list)
    sentiment_score = Column(Float, default=0.0)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class MatchModel(Base):
    __tablename__ = "matches"
    id = Column(Integer, primary_key=True)
    external_id = Column(String, unique=True, index=True)
    home_team_id = Column(Integer, ForeignKey("teams.id"))
    away_team_id = Column(Integer, ForeignKey("teams.id"))
    kickoff = Column(DateTime)
    neutral = Column(Boolean, default=True)
    status = Column(String, default="scheduled")
    home_goals = Column(Integer, nullable=True)
    away_goals = Column(Integer, nullable=True)
    odds = Column(JSON, nullable=True)
    prediction = Column(JSON, nullable=True)
    home = relationship("TeamModel", foreign_keys=[home_team_id])
    away = relationship("TeamModel", foreign_keys=[away_team_id])


class PredictionLog(Base):
    """Historique des pronostics pour mesurer la performance du modèle."""
    __tablename__ = "prediction_logs"
    id = Column(Integer, primary_key=True)
    match_id = Column(Integer, ForeignKey("matches.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    probs = Column(JSON)
    actual_outcome = Column(String, nullable=True)
    brier_score = Column(Float, nullable=True)
