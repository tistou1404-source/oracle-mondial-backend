"""connectors/football.py — Données du Mondial 2026 via openfootball (gratuit).

Source : https://github.com/openfootball/worldcup.json
Données du domaine public, AUCUNE clé API requise, calendrier complet
des matchs (phase de groupes + phases finales).
"""
import os

WORLDCUP_URL = ("https://raw.githubusercontent.com/openfootball/"
                "worldcup.json/master/2026/worldcup.json")

FOOTBALL_API_KEY = os.getenv("FOOTBALL_API_KEY", "")  # gardé pour compatibilité


def _slug(s: str) -> str:
    return "".join(c.lower() if c.isalnum() else "-" for c in s).strip("-")


def _is_real_team(name: str) -> bool:
    """Écarte les placeholders (ex: 'UEFA Path D winner', '2A', 'W74')."""
    if not name:
        return False
    low = name.lower()
    if any(m in low for m in ("winner", "path", "/", "ic ")):
        return False
    if len(name) <= 4 and any(ch.isdigit() for ch in name):
        return False
    return True


def _mock_fixtures() -> list[dict]:
    return [{
        "external_id": "demo-fra-mar",
        "home": "France", "away": "Maroc",
        "kickoff": "2026-06-15T19:00:00Z",
        "status": "scheduled", "home_goals": None, "away_goals": None,
    }]


def _parse_score(match: dict):
    score = match.get("score") or {}
    ft = score.get("ft")
    if isinstance(ft, list) and len(ft) == 2:
        return ft[0], ft[1]
    return None, None


def fetch_fixtures(date: str | None = None) -> list[dict]:
    """Matchs du Mondial 2026 depuis openfootball.
    - sans date : tout le calendrier (vraies équipes connues)
    - avec date (YYYY-MM-DD) : matchs de ce jour
    """
    import httpx
    try:
        with httpx.Client(timeout=20, follow_redirects=True) as c:
            r = c.get(WORLDCUP_URL)
            r.raise_for_status()
            data = r.json()
    except Exception:
        return _mock_fixtures()

    out = []
    for m in data.get("matches", []):
        home, away = m.get("team1", ""), m.get("team2", "")
        if not _is_real_team(home) or not _is_real_team(away):
            continue
        m_date = m.get("date")
        if date and m_date != date:
            continue
        hg, ag = _parse_score(m)
        status = "finished" if hg is not None else "scheduled"
        time_part = (m.get("time") or "00:00").split(" ")[0]
        kickoff = f"{m_date}T{time_part}:00Z" if m_date else None
        out.append({
            "external_id": f"wc2026-{m_date}-{_slug(home)}-{_slug(away)}",
            "home": home, "away": away,
            "kickoff": kickoff,
            "status": status,
            "home_goals": hg, "away_goals": ag,
        })
    return out


def fetch_squad(team_id: int) -> list[dict]:
    """Effectifs non fournis par openfootball (le moteur n'en a pas besoin)."""
    return []
