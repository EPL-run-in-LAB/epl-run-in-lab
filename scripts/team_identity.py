"""Stable EPL club identities and explicit, reviewable source aliases.

Unknown names are NOT automatically merged. Never strip FC/U21/Women blindly.
"""
EPL_CLUBS = {
    "arsenal": "Arsenal", "aston-villa": "Aston Villa",
    "bournemouth": "Bournemouth", "brentford": "Brentford",
    "brighton": "Brighton", "chelsea": "Chelsea",
    "coventry": "Coventry", "crystal-palace": "Crystal Palace",
    "everton": "Everton", "fulham": "Fulham", "hull": "Hull",
    "leeds": "Leeds", "liverpool": "Liverpool",
    "man-city": "Man City", "man-united": "Man United",
    "newcastle": "Newcastle", "nottingham": "Nottingham",
    "sunderland": "Sunderland", "tottenham": "Tottenham",
    "ipswich": "Ipswich", "west-ham": "West Ham",
}
# Membership is season-specific; club IDs remain stable after relegation.
# Official reference: https://www.premierleague.com/en/news/4365156/new-to-the-premier-league-heres-all-you-need-to-know
SEASON = "2026/27"
ACTIVE_EPL_IDS = frozenset(EPL_CLUBS) - {"west-ham"}
assert len(ACTIVE_EPL_IDS) == 20
ALIASES = {name: club_id for club_id, name in EPL_CLUBS.items()}
ALIASES.update({
    "Manchester City": "man-city", "Manchester City FC": "man-city",
    "Man Utd": "man-united", "Manchester United": "man-united",
    "Manchester United FC": "man-united",
    "Newcastle United": "newcastle",
    "AFC Bournemouth": "bournemouth",
    "Brighton & Hove Albion": "brighton",
    "Brighton and Hove Albion": "brighton",
    "Nottingham Forest": "nottingham",
    "Nottingham Forest FC": "nottingham",
    "Tottenham Hotspur": "tottenham",
    "West Ham United": "west-ham",
    "Leeds United": "leeds", "Coventry City": "coventry",
    "Hull City": "hull", "Sunderland AFC": "sunderland",
    "Ipswich Town": "ipswich", "Ipswich Town FC": "ipswich",
    "Arsenal FC": "arsenal", "Chelsea FC": "chelsea",
    "Liverpool FC": "liverpool", "Fulham FC": "fulham",
    "Everton FC": "everton", "Brentford FC": "brentford",
    "Crystal Palace FC": "crystal-palace",
    "Aston Villa FC": "aston-villa",
})

def resolve(name):
    raw = str(name).strip()
    club_id = ALIASES.get(raw)
    return {
        "raw": raw,
        "clubId": club_id,
        "displayName": EPL_CLUBS[club_id] if club_id else raw,
        "matched": club_id in ACTIVE_EPL_IDS,
        "identified": club_id is not None,
    }
