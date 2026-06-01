"""connectors/odds.py — Récupération des cotes bookmakers.

Utilise The Odds API (the-odds-api.com). Mettre votre clé dans
la variable d'environnement ODDS_API_KEY.
Tombe en mode mock si aucune clé n'est fournie (pour développer hors-ligne).
"""
import os

ODDS_API_KEY = os.getenv("ODDS_API_KEY", "")
BASE = "https://api.the-odds-api.com/v4"
SPORT = "soccer_fifa_world_cup"


def _mock_odds() -> list[dict]:
    return [{
        "external_id": "demo-fra-mar",
        "home": "France", "away": "Maroc",
        "odds": {"win_a": 1.55, "draw": 4.0, "win_b": 6.5},
    }]


def fetch_odds(region: str = "eu", market: str = "h2h") -> list[dict]:
    """Retourne une liste de matchs avec leurs cotes moyennes.
    Format normalisé : {external_id, home, away, odds:{win_a,draw,win_b}}.
    """
    if not ODDS_API_KEY:
        return _mock_odds()

    import httpx
    url = f"{BASE}/sports/{SPORT}/odds"
    params = {"apiKey": ODDS_API_KEY, "regions": region,
              "markets": market, "oddsFormat": "decimal"}
    with httpx.Client(timeout=20) as client:
        resp = client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()

    out = []
    for ev in data:
        home, away = ev.get("home_team"), ev.get("away_team")
        agg = {"win_a": [], "draw": [], "win_b": []}
        for bk in ev.get("bookmakers", []):
            for mkt in bk.get("markets", []):
                if mkt["key"] != "h2h":
                    continue
                for oc in mkt["outcomes"]:
                    if oc["name"] == home: agg["win_a"].append(oc["price"])
                    elif oc["name"] == away: agg["win_b"].append(oc["price"])
                    else: agg["draw"].append(oc["price"])
        avg = lambda xs: round(sum(xs) / len(xs), 2) if xs else None
        out.append({
            "external_id": ev.get("id"),
            "home": home, "away": away,
            "odds": {"win_a": avg(agg["win_a"]),
                     "draw": avg(agg["draw"]),
                     "win_b": avg(agg["win_b"])},
        })
    return out
