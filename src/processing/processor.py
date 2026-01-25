"""
NFL Data Processor - Orchestrates the complete data processing pipeline.

This module provides a high-level interface for:
1. Loading raw data
2. Creating chunks
3. Generating embeddings (in next step)
4. Storing in vector database (in next step)
"""

import json
from pathlib import Path
from typing import Optional
from datetime import datetime

from src.config import RAW_DATA_DIR, PROCESSED_DATA_DIR, DEBUG
from src.processing.chunker import NFLChunker, Chunk


class NFLDataProcessor:
    """
    High-level orchestrator for NFL data processing.
    
    Usage:
        processor = NFLDataProcessor()
        processor.process_all()
    """
    
    def __init__(
        self,
        raw_data_dir: Optional[Path] = None,
        processed_data_dir: Optional[Path] = None,
    ):
        """
        Initialize the processor.
        
        Args:
            raw_data_dir: Directory containing raw JSON data files
            processed_data_dir: Directory for processed output
        """
        self.raw_data_dir = raw_data_dir or RAW_DATA_DIR
        self.processed_data_dir = processed_data_dir or PROCESSED_DATA_DIR
        
        # Ensure directories exist
        self.raw_data_dir.mkdir(parents=True, exist_ok=True)
        self.processed_data_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize chunker
        self.chunker = NFLChunker(data_dir=self.raw_data_dir)
    
    def check_raw_data(self) -> dict:
        """
        Check what raw data files are available.
        
        Returns:
            Dict with file info and record counts
        """
        expected_files = [
            "seasonal_offense.json",
            "weekly_offense.json",
            "rosters.json",
            "schedules.json",
            "teams.json",
        ]
        
        status = {}
        
        for filename in expected_files:
            filepath = self.raw_data_dir / filename
            if filepath.exists():
                with open(filepath, "r") as f:
                    data = json.load(f)
                status[filename] = {
                    "exists": True,
                    "records": len(data),
                    "size_kb": filepath.stat().st_size // 1024,
                }
            else:
                status[filename] = {
                    "exists": False,
                    "records": 0,
                    "size_kb": 0,
                }
        
        return status
    
    def process_all(
        self,
        output_filename: str = "chunks.json",
        include_player_seasons: bool = True,
        include_player_games: bool = True,
        include_games: bool = True,
        include_player_bios: bool = True,
        include_teams: bool = True,
    ) -> list[Chunk]:
        """
        Run the complete processing pipeline.
        
        Args:
            output_filename: Name for the output chunks file
            include_*: Flags to control which chunk types to generate
            
        Returns:
            List of generated chunks
        """
        print("=" * 60)
        print("NFL Data Processor")
        print("=" * 60)
        print(f"Raw data directory: {self.raw_data_dir}")
        print(f"Output directory: {self.processed_data_dir}")
        print("=" * 60)
        
        # Check raw data
        print("\nChecking raw data files...")
        status = self.check_raw_data()
        
        all_exist = True
        for filename, info in status.items():
            if info["exists"]:
                print(f"  ✓ {filename}: {info['records']} records ({info['size_kb']} KB)")
            else:
                print(f"  ✗ {filename}: NOT FOUND")
                all_exist = False
        
        if not all_exist:
            print("\n⚠ Some data files are missing!")
            print("Run the data loader first:")
            print("  python -m src.ingestion.scraper --start-year 2020 --end-year 2024")
            return []
        
        # Generate chunks
        print("\n" + "=" * 60)
        print("Generating Chunks")
        print("=" * 60)
        
        chunks = self.chunker.chunk_all(
            include_player_seasons=include_player_seasons,
            include_player_games=include_player_games,
            include_games=include_games,
            include_player_bios=include_player_bios,
            include_teams=include_teams,
        )
        
        # Get statistics
        stats = self.chunker.get_chunk_stats(chunks)
        
        # Save chunks
        print("\n" + "=" * 60)
        print("Saving Chunks")
        print("=" * 60)
        
        output_path = self.chunker.save_chunks(chunks, output_filename)
        
        # Save processing metadata
        metadata = {
            "processed_at": datetime.now().isoformat(),
            "raw_data_dir": str(self.raw_data_dir),
            "output_file": str(output_path),
            "chunk_stats": stats,
            "settings": {
                "include_player_seasons": include_player_seasons,
                "include_player_games": include_player_games,
                "include_games": include_games,
                "include_player_bios": include_player_bios,
                "include_teams": include_teams,
            }
        }
        
        metadata_file = self.processed_data_dir / "processing_metadata.json"
        with open(metadata_file, "w") as f:
            json.dump(metadata, f, indent=2)
        
        print(f"Saved processing metadata to {metadata_file}")
        
        # Summary
        print("\n" + "=" * 60)
        print("Processing Complete!")
        print("=" * 60)
        print(f"Total chunks: {stats['total_chunks']}")
        print(f"Average text length: {stats['avg_text_length']} characters")
        print("\nChunks by type:")
        for chunk_type, count in sorted(stats["by_type"].items()):
            pct = count / stats["total_chunks"] * 100
            print(f"  {chunk_type}: {count} ({pct:.1f}%)")
        
        return chunks
    
    def load_processed_chunks(self, filename: str = "chunks.json") -> list[Chunk]:
        """Load previously processed chunks."""
        return self.chunker.load_chunks(filename)
    
    def get_sample_chunks(
        self,
        chunks: list[Chunk],
        n_per_type: int = 2,
    ) -> dict[str, list[Chunk]]:
        """
        Get sample chunks of each type for inspection.
        
        Args:
            chunks: List of chunks
            n_per_type: Number of samples per chunk type
            
        Returns:
            Dict mapping chunk type to sample chunks
        """
        samples = {}
        
        for chunk in chunks:
            chunk_type = chunk.metadata.get("chunk_type", "unknown")
            if chunk_type not in samples:
                samples[chunk_type] = []
            
            if len(samples[chunk_type]) < n_per_type:
                samples[chunk_type].append(chunk)
        
        return samples
    
    def search_chunks(
        self,
        chunks: list[Chunk],
        **filters,
    ) -> list[Chunk]:
        """
        Filter chunks by metadata.
        
        Args:
            chunks: List of chunks to filter
            **filters: Metadata field=value pairs to filter by
            
        Returns:
            Filtered list of chunks
        """
        results = []
        
        for chunk in chunks:
            match = True
            for key, value in filters.items():
                chunk_value = chunk.metadata.get(key)
                
                # Handle different comparison types
                if isinstance(value, (list, tuple)):
                    if chunk_value not in value:
                        match = False
                        break
                elif callable(value):
                    if not value(chunk_value):
                        match = False
                        break
                else:
                    if chunk_value != value:
                        match = False
                        break
            
            if match:
                results.append(chunk)
        
        return results


def main():
    """CLI for the processor."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Process NFL data for RAG")
    parser.add_argument(
        "--raw-dir",
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
        "--no-player-games",
        action="store_true",
        help="Skip player game chunks (large)",
    )
    parser.add_argument(
        "--show-samples",
        action="store_true",
        help="Show sample chunks after processing",
    )
    
    args = parser.parse_args()
    
    processor = NFLDataProcessor(raw_data_dir=args.raw_dir)
    
    chunks = processor.process_all(
        output_filename=args.output,
        include_player_games=not args.no_player_games,
    )
    
    if args.show_samples and chunks:
        print("\n" + "=" * 60)
        print("Sample Chunks")
        print("=" * 60)
        
        samples = processor.get_sample_chunks(chunks, n_per_type=1)
        
        for chunk_type, type_samples in samples.items():
            for sample in type_samples:
                print(f"\n{'='*60}")
                print(f"TYPE: {chunk_type}")
                print("=" * 60)
                print(sample.text)
                print(f"\nMETADATA KEYS: {list(sample.metadata.keys())}")


if __name__ == "__main__":
    main()