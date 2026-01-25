"""
NFL Stadium coordinates and metadata.

This module provides a comprehensive lookup table for NFL stadiums,
including coordinates, roof type, and name variations over time.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class Stadium:
    """Stadium information including location and characteristics."""
    name: str
    city: str
    state: str
    latitude: float
    longitude: float
    roof: str  # "outdoors", "dome", "retractable"
    surface: str  # "grass", "turf"
    team: str  # Primary team (for reference)
    opened: int  # Year opened
    closed: Optional[int] = None  # Year closed (if applicable)
    aliases: tuple = ()  # Alternative names


# Comprehensive stadium database
# Includes current stadiums and historical venues back to 2000
STADIUMS: dict[str, Stadium] = {
    # =========================================================================
    # CURRENT STADIUMS (as of 2024)
    # =========================================================================
    
    # AFC EAST
    "Gillette Stadium": Stadium(
        name="Gillette Stadium",
        city="Foxborough",
        state="MA",
        latitude=42.0909,
        longitude=-71.2643,
        roof="outdoors",
        surface="turf",
        team="New England Patriots",
        opened=2002,
        aliases=("CMGI Field",)
    ),
    "Hard Rock Stadium": Stadium(
        name="Hard Rock Stadium",
        city="Miami Gardens",
        state="FL",
        latitude=25.9580,
        longitude=-80.2389,
        roof="outdoors",  # Has canopy but open air over field
        surface="grass",
        team="Miami Dolphins",
        opened=1987,
        aliases=(
            "Joe Robbie Stadium",
            "Pro Player Park",
            "Pro Player Stadium",
            "Dolphins Stadium",
            "Dolphin Stadium",
            "Land Shark Stadium",
            "Sun Life Stadium",
        )
    ),
    "Highmark Stadium": Stadium(
        name="Highmark Stadium",
        city="Orchard Park",
        state="NY",
        latitude=42.7738,
        longitude=-78.7870,
        roof="outdoors",
        surface="turf",
        team="Buffalo Bills",
        opened=1973,
        aliases=(
            "Rich Stadium",
            "Ralph Wilson Stadium",
            "Bills Stadium",
            "New Era Field",
        )
    ),
    "MetLife Stadium": Stadium(
        name="MetLife Stadium",
        city="East Rutherford",
        state="NJ",
        latitude=40.8128,
        longitude=-74.0742,
        roof="outdoors",
        surface="turf",
        team="New York Giants / New York Jets",
        opened=2010,
        aliases=("New Meadowlands Stadium",)
    ),
    
    # AFC NORTH
    "M&T Bank Stadium": Stadium(
        name="M&T Bank Stadium",
        city="Baltimore",
        state="MD",
        latitude=39.2780,
        longitude=-76.6227,
        roof="outdoors",
        surface="grass",
        team="Baltimore Ravens",
        opened=1998,
        aliases=(
            "Ravens Stadium",
            "PSINet Stadium",
        )
    ),
    "Paycor Stadium": Stadium(
        name="Paycor Stadium",
        city="Cincinnati",
        state="OH",
        latitude=39.0955,
        longitude=-84.5161,
        roof="outdoors",
        surface="turf",
        team="Cincinnati Bengals",
        opened=2000,
        aliases=(
            "Paul Brown Stadium",
        )
    ),
    "Cleveland Browns Stadium": Stadium(
        name="Cleveland Browns Stadium",
        city="Cleveland",
        state="OH",
        latitude=41.5061,
        longitude=-81.6995,
        roof="outdoors",
        surface="grass",
        team="Cleveland Browns",
        opened=1999,
        aliases=(
            "FirstEnergy Stadium",
            "Huntington Bank Field",
        )
    ),
    "Acrisure Stadium": Stadium(
        name="Acrisure Stadium",
        city="Pittsburgh",
        state="PA",
        latitude=40.4468,
        longitude=-80.0158,
        roof="outdoors",
        surface="grass",
        team="Pittsburgh Steelers",
        opened=2001,
        aliases=(
            "Heinz Field",
        )
    ),
    
    # AFC SOUTH
    "NRG Stadium": Stadium(
        name="NRG Stadium",
        city="Houston",
        state="TX",
        latitude=29.6847,
        longitude=-95.4107,
        roof="retractable",
        surface="turf",
        team="Houston Texans",
        opened=2002,
        aliases=(
            "Reliant Stadium",
        )
    ),
    "Lucas Oil Stadium": Stadium(
        name="Lucas Oil Stadium",
        city="Indianapolis",
        state="IN",
        latitude=39.7601,
        longitude=-86.1639,
        roof="retractable",
        surface="turf",
        team="Indianapolis Colts",
        opened=2008,
    ),
    "EverBank Stadium": Stadium(
        name="EverBank Stadium",
        city="Jacksonville",
        state="FL",
        latitude=30.3239,
        longitude=-81.6373,
        roof="outdoors",
        surface="grass",
        team="Jacksonville Jaguars",
        opened=1995,
        aliases=(
            "Jacksonville Municipal Stadium",
            "Alltel Stadium",
            "EverBank Field",
            "TIAA Bank Field",
            "TIAA Bank Stadium",
        )
    ),
    "Nissan Stadium": Stadium(
        name="Nissan Stadium",
        city="Nashville",
        state="TN",
        latitude=36.1665,
        longitude=-86.7713,
        roof="outdoors",
        surface="turf",
        team="Tennessee Titans",
        opened=1999,
        aliases=(
            "Adelphia Coliseum",
            "The Coliseum",
            "LP Field",
        )
    ),
    
    # AFC WEST
    "Empower Field at Mile High": Stadium(
        name="Empower Field at Mile High",
        city="Denver",
        state="CO",
        latitude=39.7439,
        longitude=-105.0201,
        roof="outdoors",
        surface="grass",
        team="Denver Broncos",
        opened=2001,
        aliases=(
            "Invesco Field at Mile High",
            "Sports Authority Field at Mile High",
            "Broncos Stadium at Mile High",
            "Mile High Stadium",  # Note: original Mile High was different
        )
    ),
    "GEHA Field at Arrowhead Stadium": Stadium(
        name="GEHA Field at Arrowhead Stadium",
        city="Kansas City",
        state="MO",
        latitude=39.0489,
        longitude=-94.4839,
        roof="outdoors",
        surface="grass",
        team="Kansas City Chiefs",
        opened=1972,
        aliases=(
            "Arrowhead Stadium",
        )
    ),
    "Allegiant Stadium": Stadium(
        name="Allegiant Stadium",
        city="Las Vegas",
        state="NV",
        latitude=36.0909,
        longitude=-115.1833,
        roof="dome",
        surface="grass",  # Real grass, retractable field tray
        team="Las Vegas Raiders",
        opened=2020,
    ),
    "SoFi Stadium": Stadium(
        name="SoFi Stadium",
        city="Inglewood",
        state="CA",
        latitude=33.9535,
        longitude=-118.3392,
        roof="dome",  # Fixed roof with open ends
        surface="turf",
        team="Los Angeles Chargers / Los Angeles Rams",
        opened=2020,
    ),
    
    # NFC EAST
    "AT&T Stadium": Stadium(
        name="AT&T Stadium",
        city="Arlington",
        state="TX",
        latitude=32.7473,
        longitude=-97.0945,
        roof="retractable",
        surface="turf",
        team="Dallas Cowboys",
        opened=2009,
        aliases=(
            "Cowboys Stadium",
        )
    ),
    "Lincoln Financial Field": Stadium(
        name="Lincoln Financial Field",
        city="Philadelphia",
        state="PA",
        latitude=39.9008,
        longitude=-75.1675,
        roof="outdoors",
        surface="grass",
        team="Philadelphia Eagles",
        opened=2003,
        aliases=(
            "The Linc",
        )
    ),
    "MetLife Stadium (Giants)": Stadium(
        name="MetLife Stadium",
        city="East Rutherford",
        state="NJ",
        latitude=40.8128,
        longitude=-74.0742,
        roof="outdoors",
        surface="turf",
        team="New York Giants",
        opened=2010,
        aliases=("New Meadowlands Stadium",)
    ),
    "Northwest Stadium": Stadium(
        name="Northwest Stadium",
        city="Landover",
        state="MD",
        latitude=38.9076,
        longitude=-76.8645,
        roof="outdoors",
        surface="grass",
        team="Washington Commanders",
        opened=1997,
        aliases=(
            "FedExField",
            "FedEx Field",
            "Jack Kent Cooke Stadium",
            "Commanders Field",
        )
    ),
    
    # NFC NORTH
    "Soldier Field": Stadium(
        name="Soldier Field",
        city="Chicago",
        state="IL",
        latitude=41.8623,
        longitude=-87.6167,
        roof="outdoors",
        surface="grass",
        team="Chicago Bears",
        opened=1924,  # Renovated 2003
    ),
    "Ford Field": Stadium(
        name="Ford Field",
        city="Detroit",
        state="MI",
        latitude=42.3400,
        longitude=-83.0456,
        roof="dome",
        surface="turf",
        team="Detroit Lions",
        opened=2002,
    ),
    "Lambeau Field": Stadium(
        name="Lambeau Field",
        city="Green Bay",
        state="WI",
        latitude=44.5013,
        longitude=-88.0622,
        roof="outdoors",
        surface="grass",  # Heated grass + turf hybrid
        team="Green Bay Packers",
        opened=1957,
        aliases=(
            "City Stadium",
        )
    ),
    "U.S. Bank Stadium": Stadium(
        name="U.S. Bank Stadium",
        city="Minneapolis",
        state="MN",
        latitude=44.9737,
        longitude=-93.2575,
        roof="dome",  # Fixed ETFE roof
        surface="turf",
        team="Minnesota Vikings",
        opened=2016,
    ),
    
    # NFC SOUTH
    "Bank of America Stadium": Stadium(
        name="Bank of America Stadium",
        city="Charlotte",
        state="NC",
        latitude=35.2258,
        longitude=-80.8528,
        roof="outdoors",
        surface="grass",
        team="Carolina Panthers",
        opened=1996,
        aliases=(
            "Ericsson Stadium",
            "Carolinas Stadium",
        )
    ),
    "Mercedes-Benz Stadium": Stadium(
        name="Mercedes-Benz Stadium",
        city="Atlanta",
        state="GA",
        latitude=33.7554,
        longitude=-84.4010,
        roof="retractable",
        surface="turf",
        team="Atlanta Falcons",
        opened=2017,
    ),
    "Caesars Superdome": Stadium(
        name="Caesars Superdome",
        city="New Orleans",
        state="LA",
        latitude=29.9511,
        longitude=-90.0812,
        roof="dome",
        surface="turf",
        team="New Orleans Saints",
        opened=1975,
        aliases=(
            "Louisiana Superdome",
            "Mercedes-Benz Superdome",
            "Superdome",
        )
    ),
    "Raymond James Stadium": Stadium(
        name="Raymond James Stadium",
        city="Tampa",
        state="FL",
        latitude=27.9759,
        longitude=-82.5033,
        roof="outdoors",
        surface="grass",
        team="Tampa Bay Buccaneers",
        opened=1998,
    ),
    
    # NFC WEST
    "State Farm Stadium": Stadium(
        name="State Farm Stadium",
        city="Glendale",
        state="AZ",
        latitude=33.5276,
        longitude=-112.2626,
        roof="retractable",
        surface="grass",  # Retractable natural grass field
        team="Arizona Cardinals",
        opened=2006,
        aliases=(
            "University of Phoenix Stadium",
            "Cardinals Stadium",
        )
    ),
    "Levi's Stadium": Stadium(
        name="Levi's Stadium",
        city="Santa Clara",
        state="CA",
        latitude=37.4033,
        longitude=-121.9694,
        roof="outdoors",
        surface="grass",
        team="San Francisco 49ers",
        opened=2014,
    ),
    "Lumen Field": Stadium(
        name="Lumen Field",
        city="Seattle",
        state="WA",
        latitude=47.5952,
        longitude=-122.3316,
        roof="outdoors",  # Partial roof over stands
        surface="turf",
        team="Seattle Seahawks",
        opened=2002,
        aliases=(
            "Seahawks Stadium",
            "Qwest Field",
            "CenturyLink Field",
        )
    ),
    
    # =========================================================================
    # HISTORICAL STADIUMS (no longer in use for NFL)
    # =========================================================================
    
    "RCA Dome": Stadium(
        name="RCA Dome",
        city="Indianapolis",
        state="IN",
        latitude=39.7638,
        longitude=-86.1555,
        roof="dome",
        surface="turf",
        team="Indianapolis Colts",
        opened=1984,
        closed=2008,
        aliases=(
            "Hoosier Dome",
        )
    ),
    "Pontiac Silverdome": Stadium(
        name="Pontiac Silverdome",
        city="Pontiac",
        state="MI",
        latitude=42.6456,
        longitude=-83.2553,
        roof="dome",
        surface="turf",
        team="Detroit Lions",
        opened=1975,
        closed=2001,
    ),
    "Giants Stadium": Stadium(
        name="Giants Stadium",
        city="East Rutherford",
        state="NJ",
        latitude=40.8135,
        longitude=-74.0745,
        roof="outdoors",
        surface="turf",
        team="New York Giants / New York Jets",
        opened=1976,
        closed=2009,
    ),
    "Texas Stadium": Stadium(
        name="Texas Stadium",
        city="Irving",
        state="TX",
        latitude=32.8404,
        longitude=-96.9088,
        roof="dome",  # Partial dome with hole
        surface="turf",
        team="Dallas Cowboys",
        opened=1971,
        closed=2008,
    ),
    "Georgia Dome": Stadium(
        name="Georgia Dome",
        city="Atlanta",
        state="GA",
        latitude=33.7577,
        longitude=-84.4008,
        roof="dome",
        surface="turf",
        team="Atlanta Falcons",
        opened=1992,
        closed=2016,
    ),
    "Hubert H. Humphrey Metrodome": Stadium(
        name="Hubert H. Humphrey Metrodome",
        city="Minneapolis",
        state="MN",
        latitude=44.9739,
        longitude=-93.2581,
        roof="dome",
        surface="turf",
        team="Minnesota Vikings",
        opened=1982,
        closed=2013,
        aliases=(
            "Metrodome",
            "Mall of America Field",
        )
    ),
    "Oakland-Alameda County Coliseum": Stadium(
        name="Oakland-Alameda County Coliseum",
        city="Oakland",
        state="CA",
        latitude=37.7516,
        longitude=-122.2005,
        roof="outdoors",
        surface="grass",
        team="Oakland Raiders",
        opened=1966,
        closed=2019,
        aliases=(
            "Oakland Coliseum",
            "McAfee Coliseum",
            "O.co Coliseum",
            "Overstock.com Coliseum",
            "RingCentral Coliseum",
            "Network Associates Coliseum",
        )
    ),
    "Qualcomm Stadium": Stadium(
        name="Qualcomm Stadium",
        city="San Diego",
        state="CA",
        latitude=32.7831,
        longitude=-117.1196,
        roof="outdoors",
        surface="grass",
        team="San Diego Chargers",
        opened=1967,
        closed=2016,
        aliases=(
            "San Diego Stadium",
            "Jack Murphy Stadium",
            "SDCCU Stadium",
        )
    ),
    "Edward Jones Dome": Stadium(
        name="Edward Jones Dome",
        city="St. Louis",
        state="MO",
        latitude=38.6328,
        longitude=-90.1885,
        roof="dome",
        surface="turf",
        team="St. Louis Rams",
        opened=1995,
        closed=2015,
        aliases=(
            "Trans World Dome",
            "The Dome at America's Center",
        )
    ),
    "Candlestick Park": Stadium(
        name="Candlestick Park",
        city="San Francisco",
        state="CA",
        latitude=37.7133,
        longitude=-122.3863,
        roof="outdoors",
        surface="grass",
        team="San Francisco 49ers",
        opened=1960,
        closed=2013,
        aliases=(
            "3Com Park",
            "Monster Park",
        )
    ),
    "Sun Devil Stadium": Stadium(
        name="Sun Devil Stadium",
        city="Tempe",
        state="AZ",
        latitude=33.4265,
        longitude=-111.9325,
        roof="outdoors",
        surface="grass",
        team="Arizona Cardinals",
        opened=1958,
        closed=2005,
        aliases=(
            "Frank Kush Field",
        )
    ),
    "TCF Bank Stadium": Stadium(
        name="TCF Bank Stadium",
        city="Minneapolis",
        state="MN",
        latitude=44.9765,
        longitude=-93.2246,
        roof="outdoors",
        surface="turf",
        team="Minnesota Vikings",  # Temporary 2014-2015
        opened=2009,
        closed=2015,  # Vikings left, still used by U of M
        aliases=(
            "Huntington Bank Stadium",
        )
    ),
    "Los Angeles Memorial Coliseum": Stadium(
        name="Los Angeles Memorial Coliseum",
        city="Los Angeles",
        state="CA",
        latitude=34.0141,
        longitude=-118.2879,
        roof="outdoors",
        surface="grass",
        team="Los Angeles Rams",
        opened=1923,
        closed=2019,  # Rams left for SoFi
        aliases=(
            "LA Coliseum",
            "United Airlines Field at the Los Angeles Memorial Coliseum",
        )
    ),
    "StubHub Center": Stadium(
        name="StubHub Center",
        city="Carson",
        state="CA",
        latitude=33.8644,
        longitude=-118.2611,
        roof="outdoors",
        surface="grass",
        team="Los Angeles Chargers",  # Temporary 2017-2019
        opened=2003,
        closed=2019,  # Chargers left for SoFi
        aliases=(
            "Dignity Health Sports Park",
            "Home Depot Center",
        )
    ),
    
    # =========================================================================
    # NEUTRAL SITE / SPECIAL VENUES
    # =========================================================================
    
    "Wembley Stadium": Stadium(
        name="Wembley Stadium",
        city="London",
        state="UK",
        latitude=51.5560,
        longitude=-0.2795,
        roof="outdoors",  # Partial roof
        surface="grass",
        team="NFL International",
        opened=2007,
    ),
    "Tottenham Hotspur Stadium": Stadium(
        name="Tottenham Hotspur Stadium",
        city="London",
        state="UK",
        latitude=51.6043,
        longitude=-0.0663,
        roof="outdoors",
        surface="turf",  # Artificial for NFL
        team="NFL International",
        opened=2019,
    ),
    "Estadio Azteca": Stadium(
        name="Estadio Azteca",
        city="Mexico City",
        state="Mexico",
        latitude=19.3029,
        longitude=-99.1505,
        roof="outdoors",
        surface="grass",
        team="NFL International",
        opened=1966,
        aliases=(
            "Azteca Stadium",
        )
    ),
    "Allianz Arena": Stadium(
        name="Allianz Arena",
        city="Munich",
        state="Germany",
        latitude=48.2188,
        longitude=11.6247,
        roof="dome",  # ETFE cushion roof
        surface="grass",
        team="NFL International",
        opened=2005,
    ),
    "Deutsche Bank Park": Stadium(
        name="Deutsche Bank Park",
        city="Frankfurt",
        state="Germany",
        latitude=50.0686,
        longitude=8.6454,
        roof="outdoors",
        surface="grass",
        team="NFL International",
        opened=2005,
        aliases=(
            "Waldstadion",
            "Commerzbank-Arena",
        )
    ),
    "Tom Benson Hall of Fame Stadium": Stadium(
        name="Tom Benson Hall of Fame Stadium",
        city="Canton",
        state="OH",
        latitude=40.8209,
        longitude=-81.3984,
        roof="outdoors",
        surface="grass",
        team="Hall of Fame Game",
        opened=1939,
        aliases=(
            "Fawcett Stadium",
        )
    ),
}


def _build_lookup_index() -> dict[str, Stadium]:
    """Build an index mapping all stadium name variations to Stadium objects."""
    index = {}
    
    for name, stadium in STADIUMS.items():
        # Primary name
        index[name.lower()] = stadium
        
        # Aliases
        for alias in stadium.aliases:
            index[alias.lower()] = stadium
    
    return index


# Pre-built lookup index
_STADIUM_INDEX = _build_lookup_index()


def get_stadium(name: str) -> Optional[Stadium]:
    """
    Look up a stadium by name.
    
    Args:
        name: Stadium name (case-insensitive, matches aliases too)
        
    Returns:
        Stadium object if found, None otherwise
    """
    if not name:
        return None
    return _STADIUM_INDEX.get(name.lower())


def get_stadium_coordinates(name: str) -> Optional[tuple[float, float]]:
    """
    Get coordinates for a stadium.
    
    Args:
        name: Stadium name
        
    Returns:
        Tuple of (latitude, longitude) if found, None otherwise
    """
    stadium = get_stadium(name)
    if stadium:
        return (stadium.latitude, stadium.longitude)
    return None


def is_outdoor_stadium(name: str) -> bool:
    """
    Check if a stadium is outdoors (weather-relevant).
    
    Args:
        name: Stadium name
        
    Returns:
        True if stadium is outdoors or has retractable roof, False for domes
    """
    stadium = get_stadium(name)
    if not stadium:
        return False
    return stadium.roof in ("outdoors", "retractable")


def find_stadium_by_team(team_abbr: str, year: int) -> Optional[Stadium]:
    """
    Find the stadium used by a team in a given year.
    
    Args:
        team_abbr: Team abbreviation (e.g., "KC", "NE")
        year: Season year
        
    Returns:
        Stadium object if found
    """
    # Team abbreviation to name mapping
    team_map = {
        "ARI": "Arizona Cardinals",
        "ATL": "Atlanta Falcons",
        "BAL": "Baltimore Ravens",
        "BUF": "Buffalo Bills",
        "CAR": "Carolina Panthers",
        "CHI": "Chicago Bears",
        "CIN": "Cincinnati Bengals",
        "CLE": "Cleveland Browns",
        "DAL": "Dallas Cowboys",
        "DEN": "Denver Broncos",
        "DET": "Detroit Lions",
        "GB": "Green Bay Packers",
        "HOU": "Houston Texans",
        "IND": "Indianapolis Colts",
        "JAC": "Jacksonville Jaguars",
        "JAX": "Jacksonville Jaguars",
        "KC": "Kansas City Chiefs",
        "LA": "Los Angeles Rams",
        "LAC": "Los Angeles Chargers",
        "LAR": "Los Angeles Rams",
        "LV": "Las Vegas Raiders",
        "LVR": "Las Vegas Raiders",
        "MIA": "Miami Dolphins",
        "MIN": "Minnesota Vikings",
        "NE": "New England Patriots",
        "NO": "New Orleans Saints",
        "NYG": "New York Giants",
        "NYJ": "New York Jets",
        "OAK": "Oakland Raiders",
        "PHI": "Philadelphia Eagles",
        "PIT": "Pittsburgh Steelers",
        "SD": "San Diego Chargers",
        "SEA": "Seattle Seahawks",
        "SF": "San Francisco 49ers",
        "STL": "St. Louis Rams",
        "TB": "Tampa Bay Buccaneers",
        "TEN": "Tennessee Titans",
        "WAS": "Washington Commanders",
        "WSH": "Washington Commanders",
    }
    
    team_name = team_map.get(team_abbr.upper())
    if not team_name:
        return None
    
    # Find stadium that was active for this team in the given year
    for stadium in STADIUMS.values():
        if team_name in stadium.team:
            opened = stadium.opened
            closed = stadium.closed or 9999
            if opened <= year <= closed:
                return stadium
    
    return None


def list_outdoor_stadiums() -> list[Stadium]:
    """Get all outdoor stadiums (current and historical)."""
    return [s for s in STADIUMS.values() if s.roof in ("outdoors", "retractable")]


def list_current_stadiums() -> list[Stadium]:
    """Get all currently active NFL stadiums."""
    return [s for s in STADIUMS.values() if s.closed is None]


# Quick test when run directly
if __name__ == "__main__":
    print("Stadium Lookup Test")
    print("=" * 50)
    
    # Test various lookups
    test_names = [
        "Arrowhead Stadium",
        "GEHA Field at Arrowhead Stadium",
        "Gillette Stadium",
        "Hard Rock Stadium",
        "Sun Life Stadium",  # Old name for Hard Rock
        "Lambeau Field",
        "Unknown Stadium",
    ]
    
    for name in test_names:
        stadium = get_stadium(name)
        if stadium:
            print(f"✓ {name}")
            print(f"  → {stadium.name} ({stadium.city}, {stadium.state})")
            print(f"  → Coords: {stadium.latitude}, {stadium.longitude}")
            print(f"  → Roof: {stadium.roof}")
        else:
            print(f"✗ {name} - NOT FOUND")
        print()
    
    # Stats
    print("=" * 50)
    print(f"Total stadiums in database: {len(STADIUMS)}")
    print(f"Current stadiums: {len(list_current_stadiums())}")
    print(f"Outdoor/retractable stadiums: {len(list_outdoor_stadiums())}")
