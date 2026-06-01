"""connectors/football.py — Données sportives : matchs, résultats, effectifs.

Utilise API-Football (api-football.com via RapidAPI ou direct).
Clé dans FOOTBALL_API_KEY. Mode mock si absente.
"""
import os

FOOTBALL_API_KEY = os.getenv("FOOTBALL_API_KEY", "")
BASE = "https://v3.football.api-sports.io"
WC_LEAGUE_ID = 1
SEASON = 2026


def _headers():
    return {"x-apisports-key": FOOTBALL_API_KEY}


def _mock_fixtures() -> list[dict]:
    return [{
        "external_id": "demo-fra-mar",
        "home": "France", "away": "Maroc",
        "kickoff": "2026-06-15T19:00:00Z",
        "status": "scheduled", "home_goals": None, "away_goals": None,
    }]


def fetch_fixtures(date: str | None = None) -> list[dict]:
    """Matchs du Mondial (optionnellement filtrés par date YYYY-MM-DD)."""
    if not FOOTBALL_API_KEY:
        return _mock_fixtures()
    import httpx
    params = {"league": WC_LEAGUE_ID, "season": SEASON}
    if date:
        params["date"] = date
    with httpx.Client(timeout=20) as c:
        r = c.get(f"{BASE}/fixtures", headers=_headers(), params=params)
        r.raise_for_status()
        data = r.json().get("response", [])
    out = []
    for f in data:
        fx, goals, teams = f["fixture"], f["goals"], f["teams"]
        out.append({
            "external_id": str(fx["id"]),
            "home": teams["home"]["name"], "away": teams["away"]["name"],
            "kickoff": fx["date"],
            "status": "finished" if fx["status"]["short"] == "FT" else "scheduled",
            "home_goals": goals["home"], "away_goals": goals["away"],
        })
    return out


def fetch_squad(team_id: int) -> list[dict]:
    """Effectif d'une équipe."""
    if not FOOTBALL_API_KEY:
        return []
    import httpx
    with httpx.Client(timeout=20) as c:
        r = c.get(f"{BASE}/players/squads", headers=_headers(),
                  params={"team": team_id})
        r.raise_for_status()
        resp = r.json().get("response", [])
    if not resp:
        return []
    return [{"name": p["name"], "position": p["position"], "age": p["age"]}
            for p in resp[0].get("players", [])]
