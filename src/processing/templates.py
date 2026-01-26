"""
Text templates for converting NFL data into natural language chunks.

These templates are designed to:
1. Be self-contained (include all context needed to understand the chunk)
2. Use natural language that matches how users ask questions
3. Include relevant metadata for filtering and retrieval
4. Include full team names (not just abbreviations) for better semantic search
"""

from typing import Optional


# =============================================================================
# TEAM NAME MAPPING
# =============================================================================

TEAM_NAMES = {
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
    "JAX": "Jacksonville Jaguars",
    "KC": "Kansas City Chiefs",
    "LA": "Los Angeles Rams",
    "LAC": "Los Angeles Chargers",
    "LAR": "Los Angeles Rams",
    "LV": "Las Vegas Raiders",
    "MIA": "Miami Dolphins",
    "MIN": "Minnesota Vikings",
    "NE": "New England Patriots",
    "NO": "New Orleans Saints",
    "NYG": "New York Giants",
    "NYJ": "New York Jets",
    "OAK": "Oakland Raiders",  # Historical
    "PHI": "Philadelphia Eagles",
    "PIT": "Pittsburgh Steelers",
    "SD": "San Diego Chargers",  # Historical
    "SEA": "Seattle Seahawks",
    "SF": "San Francisco 49ers",
    "STL": "St. Louis Rams",  # Historical
    "TB": "Tampa Bay Buccaneers",
    "TEN": "Tennessee Titans",
    "WAS": "Washington Commanders",
    "WSH": "Washington Commanders",
}


def get_team_name(abbr: str) -> str:
    """Get full team name from abbreviation."""
    if not abbr:
        return "Unknown"
    return TEAM_NAMES.get(abbr.upper(), abbr)


def format_team(abbr: str) -> str:
    """Format team as 'Full Name (ABBR)' for searchability."""
    if not abbr:
        return "Unknown"
    full_name = TEAM_NAMES.get(abbr.upper())
    if full_name:
        return f"{full_name} ({abbr})"
    return abbr


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def format_number(value, decimals: int = 1) -> str:
    """Format a number, handling None values."""
    if value is None or (isinstance(value, float) and value != value):  # NaN check
        return "N/A"
    if isinstance(value, float):
        if decimals == 0:
            return str(int(round(value)))
        return f"{value:.{decimals}f}"
    return str(value)


def format_percentage(value) -> str:
    """Format a value as percentage."""
    if value is None or (isinstance(value, float) and value != value):
        return "N/A"
    return f"{value:.1f}%"


def format_record(wins, losses, ties=0) -> str:
    """Format a win-loss record."""
    if ties and ties > 0:
        return f"{wins}-{losses}-{ties}"
    return f"{wins}-{losses}"


def get_ordinal(n: int) -> str:
    """Convert number to ordinal (1st, 2nd, 3rd, etc.)."""
    if 10 <= n % 100 <= 20:
        suffix = 'th'
    else:
        suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')
    return f"{n}{suffix}"


def describe_temperature(temp_f: float) -> str:
    """Describe temperature in natural language."""
    if temp_f is None:
        return ""
    if temp_f <= 10:
        return f"extremely cold ({temp_f:.0f}°F, freezing conditions)"
    elif temp_f <= 32:
        return f"freezing cold ({temp_f:.0f}°F)"
    elif temp_f <= 45:
        return f"cold ({temp_f:.0f}°F)"
    elif temp_f <= 65:
        return f"cool ({temp_f:.0f}°F)"
    elif temp_f <= 80:
        return f"warm ({temp_f:.0f}°F)"
    elif temp_f <= 90:
        return f"hot ({temp_f:.0f}°F)"
    else:
        return f"extremely hot ({temp_f:.0f}°F)"


def describe_spread_result(spread_line: float, result: int, home_team: str, away_team: str) -> str:
    """
    Describe whether teams covered the spread.
    
    spread_line: Positive means home favored, negative means away favored
    result: home_score - away_score (positive = home won)
    """
    if spread_line is None or result is None:
        return ""
    
    home_name = format_team(home_team)
    away_name = format_team(away_team)
    
    home_covered = result > spread_line
    away_covered = result < spread_line
    push = result == spread_line
    
    if push:
        return "The game was a push against the spread."
    
    if spread_line < 0:
        # Home team was favored
        fav_spread = abs(spread_line)
        if home_covered:
            return f"{home_name} covered as {fav_spread}-point favorites."
        else:
            return f"{away_name} covered as {fav_spread}-point underdogs."
    else:
        # Away team was favored
        fav_spread = spread_line
        if away_covered:
            return f"{away_name} covered as {fav_spread}-point favorites."
        else:
            return f"{home_name} covered as {fav_spread}-point underdogs."


def describe_over_under_result(total_line: float, actual_total: int) -> str:
    """Describe whether the game went over or under."""
    if total_line is None or actual_total is None:
        return ""
    
    if actual_total > total_line:
        return f"The game went OVER the {total_line} total ({actual_total} points scored)."
    elif actual_total < total_line:
        return f"The game went UNDER the {total_line} total ({actual_total} points scored)."
    else:
        return f"The total was a push at exactly {total_line} points."


def describe_rest_advantage(home_rest: int, away_rest: int, home_team: str, away_team: str) -> str:
    """Describe rest day advantage."""
    if home_rest is None or away_rest is None:
        return ""
    
    home_name = format_team(home_team)
    away_name = format_team(away_team)
    
    diff = home_rest - away_rest
    if diff > 2:
        return f"{home_name} had a significant rest advantage ({home_rest} days vs {away_rest} days)."
    elif diff < -2:
        return f"{away_name} had a significant rest advantage ({away_rest} days vs {home_rest} days)."
    elif diff > 0:
        return f"{home_name} had slightly more rest ({home_rest} vs {away_rest} days)."
    elif diff < 0:
        return f"{away_name} had slightly more rest ({away_rest} vs {home_rest} days)."
    else:
        return f"Both teams had equal rest ({home_rest} days)."


def describe_weather(weather: dict) -> str:
    """Create a natural language weather description."""
    if not weather or not weather.get("weather_fetched"):
        if weather and not weather.get("is_outdoor_game", True):
            return "This game was played indoors in a dome stadium."
        return ""
    
    parts = []
    
    # Temperature with descriptive language
    temp = weather.get("temperature_f")
    feels_like = weather.get("feels_like_f")
    if temp is not None:
        temp_desc = describe_temperature(temp)
        if feels_like is not None and abs(temp - feels_like) > 5:
            parts.append(f"Weather conditions were {temp_desc}, feeling like {feels_like:.0f}°F")
        else:
            parts.append(f"Weather conditions were {temp_desc}")
    
    # Conditions
    conditions = weather.get("conditions")
    if conditions and conditions not in ("Clear sky", "Mainly clear"):
        parts.append(conditions.lower())
    
    # Wind
    wind = weather.get("wind_speed_mph")
    wind_dir = weather.get("wind_direction_cardinal")
    if wind is not None and wind > 10:
        if wind >= 20:
            wind_desc = "strong"
        elif wind >= 15:
            wind_desc = "moderate"
        else:
            wind_desc = "light"
        if wind_dir:
            parts.append(f"{wind_desc} {wind:.0f} mph {wind_dir} wind")
        else:
            parts.append(f"{wind_desc} {wind:.0f} mph wind")
    
    # Precipitation
    precip = weather.get("precipitation_inches", 0) or 0
    snow = weather.get("snowfall_inches", 0) or 0
    if snow > 0:
        parts.append(f"snow ({snow:.1f} inches)")
    elif precip > 0.1:
        parts.append(f"rain ({precip:.2f} inches)")
    elif precip > 0:
        parts.append("light precipitation")
    
    if parts:
        return ". ".join(parts) + "."
    return ""


def categorize_temperature(temp_f: float) -> str:
    """Categorize temperature for metadata."""
    if temp_f is None:
        return "unknown"
    if temp_f <= 32:
        return "freezing"
    elif temp_f <= 45:
        return "cold"
    elif temp_f <= 65:
        return "cool"
    elif temp_f <= 80:
        return "warm"
    else:
        return "hot"


# =============================================================================
# CHUNK TEMPLATES
# =============================================================================

def player_season_chunk(player: dict) -> tuple[str, dict]:
    """
    Create a chunk for a player's season statistics.
    
    Returns:
        tuple: (text content, metadata dict)
    """
    name = player.get("player_display_name") or player.get("player_name", "Unknown")
    season = player.get("season", "Unknown")
    position = player.get("position", "Unknown")
    team_abbr = player.get("recent_team", player.get("team", "Unknown"))
    team = format_team(team_abbr)
    
    # Build the text
    lines = [
        f"{name}, {position} for the {team} - {season} NFL Season Statistics"
    ]
    
    # Passing stats
    pass_yards = player.get("passing_yards")
    pass_tds = player.get("passing_tds")
    ints = player.get("interceptions")
    completions = player.get("completions")
    attempts = player.get("attempts")
    
    if pass_yards and pass_yards > 0:
        comp_pct = (completions / attempts * 100) if attempts and attempts > 0 else 0
        lines.append(
            f"Passing: {format_number(pass_yards, 0)} yards, "
            f"{format_number(pass_tds, 0)} touchdowns, {format_number(ints, 0)} interceptions "
            f"({format_number(completions, 0)}/{format_number(attempts, 0)}, {comp_pct:.1f}% completion rate)"
        )
    
    # Rushing stats
    rush_yards = player.get("rushing_yards")
    rush_tds = player.get("rushing_tds")
    carries = player.get("carries")
    
    if rush_yards and (rush_yards > 50 or position == "RB"):
        ypc = (rush_yards / carries) if carries and carries > 0 else 0
        lines.append(
            f"Rushing: {format_number(rush_yards, 0)} yards, "
            f"{format_number(rush_tds, 0)} touchdowns on {format_number(carries, 0)} carries "
            f"({ypc:.1f} yards per carry)"
        )
    
    # Receiving stats
    rec_yards = player.get("receiving_yards")
    rec_tds = player.get("receiving_tds")
    receptions = player.get("receptions")
    targets = player.get("targets")
    
    if rec_yards and (rec_yards > 50 or position in ("WR", "TE")):
        catch_pct = (receptions / targets * 100) if targets and targets > 0 else 0
        lines.append(
            f"Receiving: {format_number(rec_yards, 0)} yards, "
            f"{format_number(rec_tds, 0)} touchdowns on {format_number(receptions, 0)} receptions "
            f"({format_number(targets, 0)} targets, {catch_pct:.1f}% catch rate)"
        )
    
    # Fantasy points
    fantasy_ppr = player.get("fantasy_points_ppr")
    if fantasy_ppr and fantasy_ppr > 0:
        lines.append(f"Fantasy Points (PPR): {format_number(fantasy_ppr, 1)}")
    
    text = "\n".join(lines)
    
    # Metadata for filtering
    metadata = {
        "chunk_type": "player_season",
        "player_name": name,
        "player_id": player.get("player_id", ""),
        "team": team_abbr,
        "team_name": get_team_name(team_abbr),
        "position": position,
        "position_group": player.get("position_group", position),
        "season": int(season) if season != "Unknown" else 0,
        "passing_yards": int(pass_yards) if pass_yards else 0,
        "rushing_yards": int(rush_yards) if rush_yards else 0,
        "receiving_yards": int(rec_yards) if rec_yards else 0,
    }
    
    return text, metadata


def player_game_chunk(player: dict, game: Optional[dict] = None) -> tuple[str, dict]:
    """
    Create a chunk for a player's single game performance.
    
    Args:
        player: Player weekly stats dict
        game: Optional game/schedule dict with weather, betting, etc.
    
    Returns:
        tuple: (text content, metadata dict)
    """
    name = player.get("player_display_name") or player.get("player_name", "Unknown")
    season = player.get("season", "Unknown")
    week = player.get("week", "Unknown")
    position = player.get("position", "Unknown")
    team_abbr = player.get("recent_team", player.get("team", "Unknown"))
    team = format_team(team_abbr)
    opponent_abbr = player.get("opponent_team", "Unknown")
    opponent = format_team(opponent_abbr)
    
    # Determine home/away
    is_home = None
    if game:
        is_home = (team_abbr == game.get("home_team"))
    
    location_str = ""
    if is_home is True:
        location_str = f"vs {opponent} at home"
    elif is_home is False:
        location_str = f"at {opponent} (away game)"
    else:
        location_str = f"vs {opponent}"
    
    # Build header
    week_type = "Week"
    game_type_str = ""
    if game:
        game_type = game.get("game_type", "REG")
        if game_type == "POST":
            week_type = "Playoff"
            game_type_str = " (Playoff Game)"
        elif game_type == "WC":
            week_type = "Wild Card Round"
            game_type_str = " (Wild Card Playoff)"
        elif game_type == "DIV":
            week_type = "Divisional Round"
            game_type_str = " (Divisional Playoff)"
        elif game_type == "CON":
            week_type = "Conference Championship"
            game_type_str = " (Conference Championship)"
        elif game_type == "SB":
            week_type = "Super Bowl"
            game_type_str = " (Super Bowl)"
    
    lines = [
        f"{name}, {position} for the {team} - {season} {week_type} {week} {location_str}{game_type_str}"
    ]
    
    # Game context from schedule data
    if game:
        gameday = game.get("gameday", "")
        if gameday:
            lines.append(f"Game Date: {gameday}")
        
        # Rest days
        home_rest = game.get("home_rest")
        away_rest = game.get("away_rest")
        if home_rest and away_rest:
            if is_home:
                lines.append(f"Rest: {home_rest} days (opponent had {away_rest} days)")
            else:
                lines.append(f"Rest: {away_rest} days (opponent had {home_rest} days)")
        
        # Betting context
        spread = game.get("spread_line")
        if spread is not None:
            if spread < 0:
                # Home favored
                if is_home:
                    lines.append(f"The {team} were favored by {abs(spread)} points")
                else:
                    lines.append(f"The {team} were {abs(spread)}-point underdogs")
            else:
                # Away favored
                if is_home:
                    lines.append(f"The {team} were {spread}-point underdogs")
                else:
                    lines.append(f"The {team} were favored by {spread} points")
        
        # Weather
        weather = game.get("weather", {})
        weather_desc = describe_weather(weather)
        if weather_desc:
            lines.append(weather_desc)
        
        # Game result
        home_score = game.get("home_score")
        away_score = game.get("away_score")
        if home_score is not None and away_score is not None:
            if is_home:
                team_score, opp_score = home_score, away_score
            else:
                team_score, opp_score = away_score, home_score
            
            if team_score > opp_score:
                result_str = f"The {team} won {team_score}-{opp_score}"
            elif team_score < opp_score:
                result_str = f"The {team} lost {opp_score}-{team_score}"
            else:
                result_str = f"The game ended in a {team_score}-{opp_score} tie"
            lines.append(f"Result: {result_str}")
    
    lines.append("")  # Blank line before stats
    
    # Player stats
    pass_yards = player.get("passing_yards")
    pass_tds = player.get("passing_tds")
    ints = player.get("interceptions")
    completions = player.get("completions")
    attempts = player.get("attempts")
    
    if pass_yards and pass_yards > 0:
        lines.append(
            f"Passing: {format_number(pass_yards, 0)} yards, "
            f"{format_number(pass_tds, 0)} touchdowns, {format_number(ints, 0)} interceptions "
            f"({format_number(completions, 0)}/{format_number(attempts, 0)} completions)"
        )
    
    rush_yards = player.get("rushing_yards")
    rush_tds = player.get("rushing_tds")
    carries = player.get("carries")
    
    if rush_yards and rush_yards > 0:
        lines.append(
            f"Rushing: {format_number(rush_yards, 0)} yards, "
            f"{format_number(rush_tds, 0)} touchdowns on {format_number(carries, 0)} carries"
        )
    
    rec_yards = player.get("receiving_yards")
    rec_tds = player.get("receiving_tds")
    receptions = player.get("receptions")
    targets = player.get("targets")
    
    if rec_yards and rec_yards > 0:
        lines.append(
            f"Receiving: {format_number(rec_yards, 0)} yards, "
            f"{format_number(rec_tds, 0)} touchdowns on {format_number(receptions, 0)} catches "
            f"({format_number(targets, 0)} targets)"
        )
    
    # Fantasy
    fantasy_ppr = player.get("fantasy_points_ppr")
    if fantasy_ppr and fantasy_ppr > 0:
        lines.append(f"Fantasy Points (PPR): {format_number(fantasy_ppr, 1)}")
    
    text = "\n".join(lines)
    
    # Build metadata
    metadata = {
        "chunk_type": "player_game",
        "player_name": name,
        "player_id": player.get("player_id", ""),
        "team": team_abbr,
        "team_name": get_team_name(team_abbr),
        "opponent": opponent_abbr,
        "opponent_name": get_team_name(opponent_abbr),
        "position": position,
        "season": int(season) if season != "Unknown" else 0,
        "week": int(week) if week != "Unknown" else 0,
        "is_home": is_home,
    }
    
    # Add game-level metadata
    if game:
        metadata["game_id"] = game.get("game_id", "")
        metadata["game_type"] = game.get("game_type", "REG")
        
        weather = game.get("weather", {})
        if weather.get("is_outdoor_game", True):
            metadata["venue_type"] = "outdoor"
            temp = weather.get("temperature_f")
            if temp is not None:
                metadata["temperature_category"] = categorize_temperature(temp)
                metadata["temperature_f"] = temp
            wind = weather.get("wind_speed_mph")
            if wind is not None:
                metadata["wind_mph"] = wind
        else:
            metadata["venue_type"] = "dome"
        
        # Betting metadata
        spread = game.get("spread_line")
        if spread is not None:
            if is_home:
                metadata["team_spread"] = -spread  # From team's perspective
            else:
                metadata["team_spread"] = spread
            metadata["was_favorite"] = metadata["team_spread"] < 0
            metadata["was_underdog"] = metadata["team_spread"] > 0
    
    return text, metadata


def game_summary_chunk(game: dict) -> tuple[str, dict]:
    """
    Create a comprehensive game summary chunk.
    
    Returns:
        tuple: (text content, metadata dict)
    """
    season = game.get("season", "Unknown")
    week = game.get("week", "Unknown")
    game_type = game.get("game_type", "REG")
    
    home_abbr = game.get("home_team", "Unknown")
    away_abbr = game.get("away_team", "Unknown")
    home_team = format_team(home_abbr)
    away_team = format_team(away_abbr)
    home_score = game.get("home_score")
    away_score = game.get("away_score")
    
    # Format game type
    if game_type == "SB":
        week_str = "Super Bowl"
    elif game_type == "CON":
        week_str = "Conference Championship"
    elif game_type == "DIV":
        week_str = "Divisional Playoff Round"
    elif game_type == "WC":
        week_str = "Wild Card Playoff Round"
    elif game_type == "POST":
        week_str = f"Playoff Week {week}"
    else:
        week_str = f"Week {week}"
    
    # Header
    lines = [f"{season} NFL {week_str}: {away_team} at {home_team}"]
    
    # Date and venue
    gameday = game.get("gameday", "")
    stadium = game.get("stadium", "")
    if gameday:
        venue_info = f"Game Date: {gameday}"
        if stadium:
            venue_info += f" at {stadium}"
        lines.append(venue_info)
    
    # Coaches
    home_coach = game.get("home_coach")
    away_coach = game.get("away_coach")
    if home_coach and away_coach:
        lines.append(f"Head Coaches: {away_coach} ({away_team}) vs {home_coach} ({home_team})")
    
    # Rest days
    home_rest = game.get("home_rest")
    away_rest = game.get("away_rest")
    rest_desc = describe_rest_advantage(home_rest, away_rest, home_abbr, away_abbr)
    if rest_desc:
        lines.append(rest_desc)
    
    # Weather
    weather = game.get("weather", {})
    weather_desc = describe_weather(weather)
    if weather_desc:
        lines.append(weather_desc)
    
    # Betting lines
    spread = game.get("spread_line")
    total_line = game.get("total_line")
    
    if spread is not None:
        if spread < 0:
            lines.append(f"Betting Line: {home_team} favored by {abs(spread)} points")
        elif spread > 0:
            lines.append(f"Betting Line: {away_team} favored by {spread} points")
        else:
            lines.append("Betting Line: Pick'em (no spread)")
    
    if total_line is not None:
        lines.append(f"Over/Under Total: {total_line} points")
    
    # Final score
    if home_score is not None and away_score is not None:
        lines.append("")
        
        if home_score > away_score:
            lines.append(f"Final Score: {home_team} {home_score}, {away_team} {away_score}")
            lines.append(f"The {home_team} won by {home_score - away_score} points at home")
        elif away_score > home_score:
            lines.append(f"Final Score: {away_team} {away_score}, {home_team} {home_score}")
            lines.append(f"The {away_team} won by {away_score - home_score} points on the road")
        else:
            lines.append(f"Final Score: {away_team} {away_score}, {home_team} {home_score} (TIE)")
        
        # Overtime
        if game.get("overtime"):
            lines.append("This game went to overtime.")
        
        # Spread result
        result = game.get("result")  # home_score - away_score
        if spread is not None and result is not None:
            spread_result = describe_spread_result(spread, result, home_abbr, away_abbr)
            if spread_result:
                lines.append(spread_result)
        
        # Over/under result
        actual_total = home_score + away_score
        if total_line is not None:
            ou_result = describe_over_under_result(total_line, actual_total)
            if ou_result:
                lines.append(ou_result)
    
    # Divisional game
    if game.get("div_game"):
        lines.append("This was a divisional rivalry game.")
    
    text = "\n".join(lines)
    
    # Metadata
    metadata = {
        "chunk_type": "game_summary",
        "game_id": game.get("game_id", ""),
        "season": int(season) if season != "Unknown" else 0,
        "week": int(week) if week != "Unknown" else 0,
        "game_type": game_type,
        "home_team": home_abbr,
        "away_team": away_abbr,
        "home_team_name": get_team_name(home_abbr),
        "away_team_name": get_team_name(away_abbr),
        "home_coach": home_coach or "",
        "away_coach": away_coach or "",
        "stadium": stadium,
        "is_divisional": bool(game.get("div_game")),
        "is_playoff": game_type in ("POST", "WC", "DIV", "CON", "SB"),
    }
    
    # Score metadata
    if home_score is not None and away_score is not None:
        metadata["home_score"] = home_score
        metadata["away_score"] = away_score
        metadata["total_points"] = home_score + away_score
        metadata["winner"] = home_abbr if home_score > away_score else (away_abbr if away_score > home_score else "TIE")
        metadata["winner_name"] = get_team_name(metadata["winner"]) if metadata["winner"] != "TIE" else "TIE"
        metadata["went_to_overtime"] = bool(game.get("overtime"))
    
    # Betting metadata
    if spread is not None:
        metadata["spread_line"] = spread
        metadata["home_was_favorite"] = spread < 0
        
        result = game.get("result")
        if result is not None:
            metadata["home_covered"] = result > spread
            metadata["away_covered"] = result < spread
    
    if total_line is not None:
        metadata["total_line"] = total_line
        if home_score is not None and away_score is not None:
            actual = home_score + away_score
            metadata["went_over"] = actual > total_line
            metadata["went_under"] = actual < total_line
    
    # Weather metadata
    weather = game.get("weather", {})
    if weather.get("is_outdoor_game", True):
        metadata["venue_type"] = "outdoor"
        temp = weather.get("temperature_f")
        if temp is not None:
            metadata["temperature_category"] = categorize_temperature(temp)
            metadata["temperature_f"] = temp
    else:
        metadata["venue_type"] = "dome"
    
    return text, metadata


def player_bio_chunk(player: dict) -> tuple[str, dict]:
    """
    Create a player biography/info chunk from roster data.
    
    Returns:
        tuple: (text content, metadata dict)
    """
    name = player.get("player_name", player.get("full_name", "Unknown"))
    position = player.get("position", "Unknown")
    team_abbr = player.get("team", "Unknown")
    team = format_team(team_abbr)
    
    lines = [f"{name} - NFL Player Profile"]
    
    # Basic info
    lines.append(f"Position: {position}")
    lines.append(f"Team: {team}")
    
    # Jersey number
    jersey = player.get("jersey_number")
    if jersey:
        lines.append(f"Jersey Number: #{jersey}")
    
    # Physical attributes
    height = player.get("height")
    weight = player.get("weight")
    if height and weight:
        lines.append(f"Height/Weight: {height}, {weight} lbs")
    elif height:
        lines.append(f"Height: {height}")
    elif weight:
        lines.append(f"Weight: {weight} lbs")
    
    # Age and experience
    age = player.get("age")
    years_exp = player.get("years_exp")
    if age:
        lines.append(f"Age: {age}")
    if years_exp is not None:
        if years_exp == 0:
            lines.append("Experience: Rookie")
        else:
            lines.append(f"Experience: {years_exp} years in the NFL")
    
    # College
    college = player.get("college")
    if college:
        lines.append(f"College: {college}")
    
    # Draft info
    draft_year = player.get("draft_year") or player.get("entry_year")
    draft_round = player.get("draft_round")
    draft_pick = player.get("draft_pick") or player.get("draft_number")
    
    if draft_year and draft_round and draft_pick:
        lines.append(f"NFL Draft: {draft_year}, Round {draft_round}, Pick {draft_pick}")
    elif draft_year:
        lines.append(f"Entered NFL: {draft_year}")
    
    # Status
    status = player.get("status")
    if status and status not in ("ACT", "Active"):
        lines.append(f"Status: {status}")
    
    text = "\n".join(lines)
    
    metadata = {
        "chunk_type": "player_bio",
        "player_name": name,
        "player_id": player.get("player_id", player.get("gsis_id", "")),
        "team": team_abbr,
        "team_name": get_team_name(team_abbr),
        "position": position,
        "college": college or "",
        "draft_year": draft_year,
    }
    
    return text, metadata


def team_info_chunk(team: dict) -> tuple[str, dict]:
    """
    Create a team information chunk.
    
    Returns:
        tuple: (text content, metadata dict)
    """
    name = team.get("team_name", "Unknown")
    abbr = team.get("team_abbr", "")
    
    lines = [f"{name} ({abbr}) - NFL Team Profile"]
    
    # Conference and division
    conf = team.get("team_conf")
    div = team.get("team_division")
    if conf and div:
        lines.append(f"Conference: {conf}")
        lines.append(f"Division: {div}")
    
    # Location
    city = team.get("team_city") or team.get("team_location")
    if city:
        lines.append(f"City: {city}")
    
    # Stadium
    stadium = team.get("team_stadium")
    if stadium:
        lines.append(f"Home Stadium: {stadium}")
    
    # Nicknames/aliases
    nick = team.get("team_nick")
    if nick and nick != name:
        lines.append(f"Nickname: {nick}")
    
    text = "\n".join(lines)
    
    metadata = {
        "chunk_type": "team_info",
        "team_abbr": abbr,
        "team_name": name,
        "conference": conf or "",
        "division": div or "",
    }
    
    return text, metadata