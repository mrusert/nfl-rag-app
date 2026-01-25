"""
NFL Data Chunker - Converts structured data into text chunks for RAG.

This module handles the logic of:
1. Loading raw data files
2. Joining related data (e.g., weekly stats with game schedules)
3. Creating chunks using templates
4. Filtering and deduplication
"""

import json
import hashlib
from pathlib import Path
from typing import Optional, Generator
from dataclasses import dataclass, field

from tqdm import tqdm

from src.config import RAW_DATA_DIR, PROCESSED_DATA_DIR, DEBUG
from src.processing.templates import (
    player_season_chunk,
    player_game_chunk,
    game_summary_chunk,
    player_bio_chunk,
    team_info_chunk,
)


@dataclass
class Chunk:
    """Represents a text chunk with metadata."""
    id: str
    text: str
    metadata: dict
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "text": self.text,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "Chunk":
        return cls(
            id=data["id"],
            text=data["text"],
            metadata=data["metadata"],
        )


def generate_chunk_id(chunk_type: str, *args) -> str:
    """Generate a unique, deterministic ID for a chunk."""
    components = [chunk_type] + [str(a) for a in args if a]
    key = "_".join(components)
    # Use a short hash to keep IDs manageable
    hash_suffix = hashlib.md5(key.encode()).hexdigest()[:8]
    return f"{chunk_type}_{hash_suffix}"


class NFLChunker:
    """
    Converts NFL data into text chunks suitable for embedding.
    
    Chunk Types:
    - player_season: Aggregated season statistics for a player
    - player_game: Individual game performance with context
    - game_summary: Complete game information with betting/weather
    - player_bio: Player biographical information
    - team_info: Team information
    """
    
    def __init__(
        self,
        data_dir: Optional[Path] = None,
        min_passing_yards: int = 100,
        min_rushing_yards: int = 20,
        min_receiving_yards: int = 20,
        include_game_context: bool = True,
    ):
        """
        Initialize the chunker.
        
        Args:
            data_dir: Directory containing raw data files
            min_passing_yards: Minimum passing yards to include a player-game chunk
            min_rushing_yards: Minimum rushing yards to include
            min_receiving_yards: Minimum receiving yards to include
            include_game_context: Whether to enrich player-game chunks with schedule data
        """
        self.data_dir = data_dir or RAW_DATA_DIR
        self.min_passing_yards = min_passing_yards
        self.min_rushing_yards = min_rushing_yards
        self.min_receiving_yards = min_receiving_yards
        self.include_game_context = include_game_context
        
        # Cache for loaded data
        self._data_cache = {}
    
    def _load_data(self, filename: str) -> list[dict]:
        """Load a JSON data file."""
        if filename in self._data_cache:
            return self._data_cache[filename]
        
        filepath = self.data_dir / filename
        if not filepath.exists():
            if DEBUG:
                print(f"Warning: Data file not found: {filepath}")
            return []
        
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        self._data_cache[filename] = data
        return data
    
    def _build_game_lookup(self) -> dict[str, dict]:
        """Build a lookup table of games by game_id and team+week."""
        schedules = self._load_data("schedules.json")
        
        lookup = {}
        for game in schedules:
            game_id = game.get("game_id", "")
            if game_id:
                lookup[game_id] = game
            
            # Also index by team+season+week for joining with weekly stats
            season = game.get("season")
            week = game.get("week")
            home = game.get("home_team")
            away = game.get("away_team")
            
            if season and week:
                if home:
                    lookup[f"{home}_{season}_{week}"] = game
                if away:
                    lookup[f"{away}_{season}_{week}"] = game
        
        return lookup
    
    def _should_include_player_game(self, player: dict) -> bool:
        """Determine if a player-game has enough stats to be worth chunking."""
        pass_yards = player.get("passing_yards") or 0
        rush_yards = player.get("rushing_yards") or 0
        rec_yards = player.get("receiving_yards") or 0
        
        return (
            pass_yards >= self.min_passing_yards or
            rush_yards >= self.min_rushing_yards or
            rec_yards >= self.min_receiving_yards
        )
    
    def chunk_player_seasons(self) -> Generator[Chunk, None, None]:
        """Generate chunks for player season statistics."""
        data = self._load_data("seasonal_offense.json")
        
        if DEBUG:
            print(f"Chunking {len(data)} player-season records...")
        
        for player in data:
            # Skip players with minimal stats
            total_yards = (
                (player.get("passing_yards") or 0) +
                (player.get("rushing_yards") or 0) +
                (player.get("receiving_yards") or 0)
            )
            if total_yards < 50:
                continue
            
            text, metadata = player_season_chunk(player)
            
            chunk_id = generate_chunk_id(
                "player_season",
                player.get("player_id"),
                player.get("season"),
            )
            
            yield Chunk(id=chunk_id, text=text, metadata=metadata)
    
    def chunk_player_games(self) -> Generator[Chunk, None, None]:
        """Generate chunks for player individual game performances."""
        weekly_data = self._load_data("weekly_offense.json")
        
        if not weekly_data:
            if DEBUG:
                print("No weekly data found, skipping player-game chunks")
            return
        
        # Build game lookup for context enrichment
        game_lookup = {}
        if self.include_game_context:
            game_lookup = self._build_game_lookup()
        
        if DEBUG:
            print(f"Chunking {len(weekly_data)} player-game records...")
        
        for player in weekly_data:
            # Filter by minimum stats
            if not self._should_include_player_game(player):
                continue
            
            # Find matching game for context
            game = None
            if self.include_game_context:
                team = player.get("recent_team", player.get("team"))
                season = player.get("season")
                week = player.get("week")
                
                if team and season and week:
                    lookup_key = f"{team}_{season}_{week}"
                    game = game_lookup.get(lookup_key)
            
            text, metadata = player_game_chunk(player, game)
            
            chunk_id = generate_chunk_id(
                "player_game",
                player.get("player_id"),
                player.get("season"),
                player.get("week"),
            )
            
            yield Chunk(id=chunk_id, text=text, metadata=metadata)
    
    def chunk_games(self) -> Generator[Chunk, None, None]:
        """Generate chunks for game summaries."""
        schedules = self._load_data("schedules.json")
        
        if DEBUG:
            print(f"Chunking {len(schedules)} game records...")
        
        for game in schedules:
            # Skip games that haven't been played yet
            if game.get("home_score") is None:
                continue
            
            text, metadata = game_summary_chunk(game)
            
            chunk_id = generate_chunk_id(
                "game_summary",
                game.get("game_id"),
            )
            
            yield Chunk(id=chunk_id, text=text, metadata=metadata)
    
    def chunk_player_bios(self) -> Generator[Chunk, None, None]:
        """Generate chunks for player biographical information."""
        rosters = self._load_data("rosters.json")
        
        if DEBUG:
            print(f"Chunking {len(rosters)} roster records...")
        
        # Track seen players to avoid duplicates across seasons
        seen_players = set()
        
        for player in rosters:
            player_id = player.get("player_id", player.get("gsis_id", ""))
            
            # Skip if we've already processed this player
            if player_id in seen_players:
                continue
            seen_players.add(player_id)
            
            # Skip players without basic info
            name = player.get("player_name", player.get("full_name"))
            if not name:
                continue
            
            text, metadata = player_bio_chunk(player)
            
            chunk_id = generate_chunk_id(
                "player_bio",
                player_id,
            )
            
            yield Chunk(id=chunk_id, text=text, metadata=metadata)
    
    def chunk_teams(self) -> Generator[Chunk, None, None]:
        """Generate chunks for team information."""
        teams = self._load_data("teams.json")
        
        if DEBUG:
            print(f"Chunking {len(teams)} team records...")
        
        for team in teams:
            abbr = team.get("team_abbr")
            if not abbr:
                continue
            
            text, metadata = team_info_chunk(team)
            
            chunk_id = generate_chunk_id(
                "team_info",
                abbr,
            )
            
            yield Chunk(id=chunk_id, text=text, metadata=metadata)
    
    def chunk_all(
        self,
        include_player_seasons: bool = True,
        include_player_games: bool = True,
        include_games: bool = True,
        include_player_bios: bool = True,
        include_teams: bool = True,
        progress: bool = True,
    ) -> list[Chunk]:
        """
        Generate all chunk types.
        
        Args:
            include_*: Flags to control which chunk types to generate
            progress: Show progress information
            
        Returns:
            List of all generated chunks
        """
        all_chunks = []
        
        if include_teams:
            if progress:
                print("\n[1/5] Chunking team info...")
            chunks = list(self.chunk_teams())
            all_chunks.extend(chunks)
            if progress:
                print(f"  Created {len(chunks)} team chunks")
        
        if include_player_bios:
            if progress:
                print("\n[2/5] Chunking player bios...")
            chunks = list(self.chunk_player_bios())
            all_chunks.extend(chunks)
            if progress:
                print(f"  Created {len(chunks)} player bio chunks")
        
        if include_player_seasons:
            if progress:
                print("\n[3/5] Chunking player seasons...")
            chunks = list(self.chunk_player_seasons())
            all_chunks.extend(chunks)
            if progress:
                print(f"  Created {len(chunks)} player season chunks")
        
        if include_games:
            if progress:
                print("\n[4/5] Chunking game summaries...")
            chunks = list(self.chunk_games())
            all_chunks.extend(chunks)
            if progress:
                print(f"  Created {len(chunks)} game summary chunks")
        
        if include_player_games:
            if progress:
                print("\n[5/5] Chunking player games...")
            chunks = list(self.chunk_player_games())
            all_chunks.extend(chunks)
            if progress:
                print(f"  Created {len(chunks)} player game chunks")
        
        if progress:
            print(f"\nTotal chunks created: {len(all_chunks)}")
        
        return all_chunks
    
    def save_chunks(self, chunks: list[Chunk], filename: str = "chunks.json"):
        """Save chunks to a JSON file."""
        output_dir = PROCESSED_DATA_DIR
        output_dir.mkdir(parents=True, exist_ok=True)
        
        output_file = output_dir / filename
        
        data = [chunk.to_dict() for chunk in chunks]
        
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
        
        print(f"Saved {len(chunks)} chunks to {output_file}")
        return output_file
    
    def load_chunks(self, filename: str = "chunks.json") -> list[Chunk]:
        """Load chunks from a JSON file."""
        input_file = PROCESSED_DATA_DIR / filename
        
        if not input_file.exists():
            raise FileNotFoundError(f"Chunks file not found: {input_file}")
        
        with open(input_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        return [Chunk.from_dict(item) for item in data]
    
    def get_chunk_stats(self, chunks: list[Chunk]) -> dict:
        """Get statistics about the generated chunks."""
        stats = {
            "total_chunks": len(chunks),
            "by_type": {},
            "avg_text_length": 0,
            "total_text_length": 0,
        }
        
        for chunk in chunks:
            chunk_type = chunk.metadata.get("chunk_type", "unknown")
            stats["by_type"][chunk_type] = stats["by_type"].get(chunk_type, 0) + 1
            stats["total_text_length"] += len(chunk.text)
        
        if chunks:
            stats["avg_text_length"] = stats["total_text_length"] // len(chunks)
        
        return stats


# CLI for testing
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Chunk NFL data for RAG")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help="Directory containing raw data files",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="chunks.json",
        help="Output filename for chunks",
    )
    parser.add_argument(
        "--no-game-context",
        action="store_true",
        help="Don't enrich player-game chunks with schedule data",
    )
    parser.add_argument(
        "--sample",
        type=int,
        default=0,
        help="Only process a sample of chunks (for testing)",
    )
    
    args = parser.parse_args()
    
    chunker = NFLChunker(
        data_dir=args.data_dir,
        include_game_context=not args.no_game_context,
    )
    
    print("=" * 60)
    print("NFL Data Chunker")
    print("=" * 60)
    
    chunks = chunker.chunk_all()
    
    if args.sample > 0:
        chunks = chunks[:args.sample]
        print(f"\nLimited to {args.sample} chunks for testing")
    
    # Print stats
    stats = chunker.get_chunk_stats(chunks)
    print("\n" + "=" * 60)
    print("Chunk Statistics")
    print("=" * 60)
    print(f"Total chunks: {stats['total_chunks']}")
    print(f"Average text length: {stats['avg_text_length']} chars")
    print("\nBy type:")
    for chunk_type, count in sorted(stats["by_type"].items()):
        print(f"  {chunk_type}: {count}")
    
    # Save
    chunker.save_chunks(chunks, args.output)
    
    # Show sample chunks
    print("\n" + "=" * 60)
    print("Sample Chunks")
    print("=" * 60)
    
    for chunk_type in stats["by_type"].keys():
        sample = next((c for c in chunks if c.metadata.get("chunk_type") == chunk_type), None)
        if sample:
            print(f"\n--- {chunk_type.upper()} ---")
            print(sample.text[:500] + "..." if len(sample.text) > 500 else sample.text)
            print(f"\nMetadata: {list(sample.metadata.keys())}")