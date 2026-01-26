"""
NFL Indexer - Orchestrates the embedding and indexing pipeline.

This module handles:
1. Loading processed chunks
2. Generating embeddings
3. Storing in ChromaDB
4. Building the searchable index
"""

import json
from pathlib import Path
from typing import Optional
from datetime import datetime

from tqdm import tqdm

from src.config import PROCESSED_DATA_DIR, CHROMA_PERSIST_DIRECTORY, DEBUG
from src.processing.chunker import Chunk
from src.retrieval.vector_store import NFLVectorStore


class NFLIndexer:
    """
    Orchestrates the indexing pipeline for NFL RAG.
    
    Usage:
        indexer = NFLIndexer()
        indexer.build_index()
    """
    
    def __init__(
        self,
        chunks_file: Optional[str] = None,
        processed_dir: Optional[Path] = None,
        persist_dir: Optional[str] = None,
    ):
        """
        Initialize the indexer.
        
        Args:
            chunks_file: Name of the chunks JSON file
            processed_dir: Directory containing processed chunks
            persist_dir: Directory for ChromaDB persistence
        """
        self.chunks_file = chunks_file or "chunks.json"
        self.processed_dir = processed_dir or PROCESSED_DATA_DIR
        self.persist_dir = persist_dir or CHROMA_PERSIST_DIRECTORY
        
        self._vector_store = None
    
    @property
    def vector_store(self) -> NFLVectorStore:
        """Get or create the vector store."""
        if self._vector_store is None:
            self._vector_store = NFLVectorStore(
                persist_directory=self.persist_dir,
            )
        return self._vector_store
    
    def load_chunks(self) -> list[Chunk]:
        """Load chunks from the processed data file."""
        chunks_path = Path(self.processed_dir) / self.chunks_file
        
        if not chunks_path.exists():
            raise FileNotFoundError(
                f"Chunks file not found: {chunks_path}\n"
                f"Run the processor first: python -m src.processing.processor"
            )
        
        with open(chunks_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        # Deduplicate chunks by ID (keep first occurrence)
        seen_ids = set()
        unique_chunks = []
        duplicates = 0
        
        for item in data:
            chunk = Chunk.from_dict(item)
            if chunk.id not in seen_ids:
                seen_ids.add(chunk.id)
                unique_chunks.append(chunk)
            else:
                duplicates += 1
        
        if duplicates > 0:
            print(f"  Warning: Removed {duplicates} duplicate chunk IDs")
        
        if DEBUG:
            print(f"Loaded {len(unique_chunks)} chunks from {chunks_path}")
        
        return unique_chunks
    
    def build_index(
        self,
        rebuild: bool = False,
        batch_size: int = 100,
    ) -> dict:
        """
        Build the vector index from chunks.
        
        Args:
            rebuild: If True, delete existing index and rebuild
            batch_size: Batch size for embedding and insertion
            
        Returns:
            Dict with indexing statistics
        """
        print("=" * 60)
        print("NFL RAG Indexer")
        print("=" * 60)
        print(f"Chunks file: {self.processed_dir / self.chunks_file}")
        print(f"Vector store: {self.persist_dir}")
        print("=" * 60)
        
        # Check if index already exists
        existing_count = self.vector_store.count()
        
        if existing_count > 0 and not rebuild:
            print(f"\n⚠ Index already exists with {existing_count} chunks")
            print("Use --rebuild to delete and rebuild")
            return {
                "status": "skipped",
                "existing_count": existing_count,
            }
        
        if rebuild and existing_count > 0:
            print(f"\nDeleting existing index ({existing_count} chunks)...")
            self.vector_store.delete_all()
        
        # Load chunks
        print("\n[1/2] Loading chunks...")
        chunks = self.load_chunks()
        print(f"  Loaded {len(chunks)} chunks")
        
        # Count by type
        type_counts = {}
        for chunk in chunks:
            chunk_type = chunk.metadata.get("chunk_type", "unknown")
            type_counts[chunk_type] = type_counts.get(chunk_type, 0) + 1
        
        print("\n  Chunks by type:")
        for chunk_type, count in sorted(type_counts.items()):
            print(f"    {chunk_type}: {count}")
        
        # Index chunks
        print(f"\n[2/2] Indexing chunks (batch_size={batch_size})...")
        start_time = datetime.now()
        
        added = self.vector_store.add_chunks(
            chunks,
            batch_size=batch_size,
            show_progress=True,
        )
        
        elapsed = (datetime.now() - start_time).total_seconds()
        
        # Summary
        print("\n" + "=" * 60)
        print("Indexing Complete!")
        print("=" * 60)
        print(f"Chunks indexed: {added}")
        print(f"Time elapsed: {elapsed:.1f} seconds")
        print(f"Rate: {added / elapsed:.1f} chunks/second")
        
        # Verify
        final_count = self.vector_store.count()
        print(f"\nVector store now contains: {final_count} chunks")
        
        # Save indexing metadata
        metadata = {
            "indexed_at": datetime.now().isoformat(),
            "chunks_file": str(self.processed_dir / self.chunks_file),
            "persist_directory": str(self.persist_dir),
            "total_chunks": added,
            "chunk_type_counts": type_counts,
            "indexing_time_seconds": elapsed,
        }
        
        metadata_file = Path(self.persist_dir) / "indexing_metadata.json"
        with open(metadata_file, "w") as f:
            json.dump(metadata, f, indent=2)
        
        print(f"\nSaved indexing metadata to {metadata_file}")
        
        return {
            "status": "success",
            "chunks_indexed": added,
            "time_seconds": elapsed,
            "type_counts": type_counts,
        }
    
    def verify_index(self) -> dict:
        """
        Verify the index by running test queries.
        
        Returns:
            Dict with verification results
        """
        print("=" * 60)
        print("Verifying Index")
        print("=" * 60)
        
        # Basic stats
        count = self.vector_store.count()
        print(f"Total chunks: {count}")
        
        if count == 0:
            print("⚠ Index is empty!")
            return {"status": "empty"}
        
        # Test queries
        test_queries = [
            ("How did Patrick Mahomes perform in 2023?", None),
            ("Chiefs vs Dolphins playoff game", None),
            ("Cold weather games", {"venue_type": "outdoor"}),
            ("Travis Kelce statistics", {"position": "TE"}),
        ]
        
        results = []
        
        for query, where in test_queries:
            print(f"\nQuery: '{query}'")
            if where:
                print(f"  Filter: {where}")
            
            search_results = self.vector_store.search(
                query=query,
                n_results=3,
                where=where,
            )
            
            if search_results:
                top_result = search_results[0]
                print(f"  ✓ Found {len(search_results)} results")
                print(f"    Top result (score: {top_result.score:.3f}): {top_result.text[:80]}...")
                results.append({"query": query, "found": len(search_results)})
            else:
                print(f"  ✗ No results found")
                results.append({"query": query, "found": 0})
        
        # Summary
        successful = sum(1 for r in results if r["found"] > 0)
        print(f"\n✓ Verification complete: {successful}/{len(test_queries)} queries returned results")
        
        return {
            "status": "verified",
            "total_chunks": count,
            "test_results": results,
            "success_rate": successful / len(test_queries),
        }
    
    def get_index_stats(self) -> dict:
        """Get detailed statistics about the index."""
        return self.vector_store.get_stats()


def main():
    """CLI for the indexer."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Build NFL RAG vector index")
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Delete existing index and rebuild",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify the index with test queries",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Show index statistics",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Batch size for indexing (default: 100)",
    )
    parser.add_argument(
        "--chunks-file",
        type=str,
        default="chunks.json",
        help="Chunks file name (default: chunks.json)",
    )
    
    args = parser.parse_args()
    
    indexer = NFLIndexer(chunks_file=args.chunks_file)
    
    if args.stats:
        stats = indexer.get_index_stats()
        print("Index Statistics")
        print("=" * 60)
        for key, value in stats.items():
            print(f"  {key}: {value}")
        
        # Type counts
        if stats["total_chunks"] > 0:
            print("\nChunk type counts:")
            type_counts = indexer.vector_store.list_chunk_types()
            for chunk_type, count in sorted(type_counts.items()):
                print(f"  {chunk_type}: {count}")
    
    elif args.verify:
        indexer.verify_index()
    
    else:
        indexer.build_index(
            rebuild=args.rebuild,
            batch_size=args.batch_size,
        )


if __name__ == "__main__":
    main()