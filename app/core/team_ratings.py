"""core/team_ratings.py — Forces de départ (Elo) des sélections du Mondial 2026.

Basé sur le World Football Elo Ratings (eloratings.net, janvier 2026) pour le
top mondial, complété par des estimations raisonnables pour les autres équipes.
Les noms correspondent à ceux fournis par openfootball (en anglais).
"""

ELO_RATINGS = {
    "Spain": 2171, "Argentina": 2113, "France": 2063, "England": 2042,
    "Colombia": 1998, "Brazil": 1979, "Portugal": 1976, "Netherlands": 1959,
    "Croatia": 1933, "Ecuador": 1933, "Norway": 1922, "Germany": 1910,
    "Switzerland": 1897, "Uruguay": 1890, "Japan": 1879, "Senegal": 1869,
    "Belgium": 1849,
    "Morocco": 1860, "USA": 1790, "Mexico": 1800, "Australia": 1720,
    "Egypt": 1700, "Iran": 1760, "South Korea": 1755, "Canada": 1740,
    "Ivory Coast": 1720, "Algeria": 1740, "Austria": 1790, "Sweden": 1770,
    "Scotland": 1740, "Panama": 1640, "Paraguay": 1720, "Tunisia": 1690,
    "Ghana": 1700, "Cape Verde": 1620, "Curaçao": 1560, "Haiti": 1560,
    "New Zealand": 1560, "Saudi Arabia": 1640, "Qatar": 1600, "Jordan": 1620,
    "Uzbekistan": 1620, "Bosnia & Herzegovina": 1720, "DR Congo": 1700,
    "Iraq": 1620, "South Africa": 1680, "Czech Republic": 1780,
}

DEFAULT_ELO = 1700


def starting_elo(team_name: str) -> float:
    return ELO_RATINGS.get(team_name, DEFAULT_ELO)


def starting_profile(team_name: str):
    """Retourne (elo, attack, defense) selon la force."""
    elo = starting_elo(team_name)
    delta = (elo - 1700) / 400.0
    attack = round(max(1.0, 1.35 + delta * 0.45), 2)
    defense = round(min(1.5, max(0.7, 1.10 - delta * 0.30)), 2)
    return elo, attack, defense
