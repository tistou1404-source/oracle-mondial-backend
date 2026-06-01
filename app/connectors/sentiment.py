"""connectors/sentiment.py — Analyse extra-sportive (médias + réseaux sociaux).

Agrège des articles (NewsAPI) et des posts sur une équipe, puis calcule un
score de sentiment moyen entre -1 (très négatif) et +1.
Ce score module ensuite légèrement la forme de l'équipe dans le moteur.
"""
import os

NEWS_API_KEY = os.getenv("NEWS_API_KEY", "")

POS = {"victoire", "forme", "favori", "confiance", "retour", "buteur",
       "win", "strong", "confident", "fit", "boost"}
NEG = {"blessure", "blessé", "forfait", "crise", "tension", "suspension",
       "injury", "doubt", "crisis", "banned", "out"}


def _lexicon_score(text: str) -> float:
    words = text.lower().split()
    pos = sum(w in POS for w in words)
    neg = sum(w in NEG for w in words)
    if pos + neg == 0:
        return 0.0
    return (pos - neg) / (pos + neg)


def fetch_news(team: str, limit: int = 20) -> list[str]:
    """Titres + descriptions d'articles récents sur l'équipe."""
    if not NEWS_API_KEY:
        return [f"{team} en pleine confiance avant le tournoi",
                f"Doute sur une blessure dans le groupe {team}"]
    import httpx
    url = "https://newsapi.org/v2/everything"
    params = {"q": team, "language": "fr", "sortBy": "publishedAt",
              "pageSize": limit, "apiKey": NEWS_API_KEY}
    with httpx.Client(timeout=20) as c:
        r = c.get(url, params=params)
        r.raise_for_status()
        arts = r.json().get("articles", [])
    return [f"{a.get('title','')} {a.get('description','')}" for a in arts]


def team_sentiment(team: str) -> float:
    """Score de sentiment agrégé pour une équipe, dans [-1, +1]."""
    texts = fetch_news(team)
    if not texts:
        return 0.0
    scores = [_lexicon_score(t) for t in texts]
    return round(sum(scores) / len(scores), 3)


def sentiment_to_form_bonus(score: float) -> float:
    """Convertit le sentiment en petit ajustement de forme (max ±0.1)."""
    return max(-0.1, min(0.1, score * 0.1))
