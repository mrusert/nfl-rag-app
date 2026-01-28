"""
NFL Vector Store - ChromaDB integration for storing and querying embeddings.

ChromaDB is used as the vector database because:
1. No external server required (embedded mode)
2. Built-in persistence
3. Supports metadata filtering
4. Good performance for our scale (~30k chunks)
"""

import json
from pathlib import Path
from typing import Optional, Any
from dataclasses import dataclass

import chromadb
from chromadb.config import Settings

from src.config import CHROMA_PERSIST_DIRECTORY, EMBEDDING_MODEL, DEBUG
from src.retrieval.embedder import NFLEmbedder
from src.processing.chunker import Chunk


@dataclass
class SearchResult:
    """Represents a search result from the vector store."""
    chunk_id: str
    text: str
    metadata: dict
    score: float  # Similarity score (higher = more similar)
    
    def __repr__(self):
        return f"SearchResult(id={self.chunk_id}, score={self.score:.3f})"


class NFLVectorStore:
    """
    Vector store for NFL RAG using ChromaDB.
    
    Features:
    - Persistent storage of embeddings
    - Metadata filtering (by team, player, season, etc.)
    - Semantic similarity search
    - Hybrid search (semantic + metadata filters)
    """
    
    COLLECTION_NAME = "nfl_chunks"
    
    def __init__(
        self,
        persist_directory: Optional[str] = None,
        embedding_model: Optional[str] = None,
    ):
        """
        Initialize the vector store.
        
        Args:
            persist_directory: Directory for ChromaDB persistence
            embedding_model: Embedding model name (must match what was used to create embeddings)
        """
        self.persist_directory = persist_directory or CHROMA_PERSIST_DIRECTORY
        self.embedding_model = embedding_model or EMBEDDING_MODEL
        
        # Initialize ChromaDB client with persistence
        self._client = chromadb.PersistentClient(
            path=self.persist_directory,
            settings=Settings(
                anonymized_telemetry=False,
            ),
        )
        
        # Initialize embedder
        self._embedder = NFLEmbedder(model_name=self.embedding_model)
        
        # Collection reference (lazy loaded)
        self._collection = None
        
        if DEBUG:
            print(f"Vector store initialized")
            print(f"  Persist directory: {self.persist_directory}")
            print(f"  Embedding model: {self.embedding_model}")
    
    @property
    def collection(self):
        """Get or create the ChromaDB collection."""
        if self._collection is None:
            self._collection = self._client.get_or_create_collection(
                name=self.COLLECTION_NAME,
                metadata={
                    "description": "NFL RAG chunks with metadata",
                    "embedding_model": self.embedding_model,
                },
            )
        return self._collection
    
    def _sanitize_metadata(self, metadata: dict) -> dict:
        """
        Sanitize metadata for ChromaDB storage.
        
        ChromaDB only supports str, int, float, and bool values.
        """
        sanitized = {}
        
        for key, value in metadata.items():
            if value is None:
                continue  # Skip None values
            elif isinstance(value, bool):
                sanitized[key] = value
            elif isinstance(value, (int, float)):
                # Handle NaN
                if isinstance(value, float) and value != value:
                    continue
                sanitized[key] = value
            elif isinstance(value, str):
                sanitized[key] = value
            else:
                # Convert other types to string
                sanitized[key] = str(value)
        
        return sanitized
    
    def add_chunks(
        self,
        chunks: list[Chunk],
        batch_size: int = 100,
        show_progress: bool = True,
    ) -> int:
        """
        Add chunks to the vector store.
        
        Args:
            chunks: List of Chunk objects to add
            batch_size: Batch size for embedding and insertion
            show_progress: Show progress information
            
        Returns:
            Number of chunks added
        """
        if not chunks:
            return 0
        
        if show_progress:
            print(f"Adding {len(chunks)} chunks to vector store...")
        
        # Process in batches
        total_added = 0
        
        from tqdm import tqdm
        iterator = range(0, len(chunks), batch_size)
        if show_progress:
            iterator = tqdm(iterator, desc="Embedding & storing")
        
        for i in iterator:
            batch = chunks[i:i + batch_size]
            
            # Extract data
            ids = [chunk.id for chunk in batch]
            texts = [chunk.text for chunk in batch]
            metadatas = [self._sanitize_metadata(chunk.metadata) for chunk in batch]
            
            # Generate embeddings
            embeddings = self._embedder.embed_texts(texts, show_progress=False)
            
            # Add to ChromaDB
            self.collection.add(
                ids=ids,
                embeddings=embeddings,
                documents=texts,
                metadatas=metadatas,
            )
            
            total_added += len(batch)
        
        if show_progress:
            print(f"✓ Added {total_added} chunks to vector store")
        
        return total_added
    
    def search(
        self,
        query: str,
        n_results: int = 10,
        where: Optional[dict] = None,
        where_document: Optional[dict] = None,
    ) -> list[SearchResult]:
        """
        Search for similar chunks.
        
        Args:
            query: Search query text
            n_results: Number of results to return
            where: Metadata filter (e.g., {"team": "KC"})
            where_document: Document content filter
            
        Returns:
            List of SearchResult objects
        """
        # Generate query embedding
        query_embedding = self._embedder.embed_text(query)
        
        # Search ChromaDB
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=where,
            where_document=where_document,
            include=["documents", "metadatas", "distances"],
        )
        
        # Convert to SearchResult objects
        search_results = []
        
        if results and results["ids"] and results["ids"][0]:
            ids = results["ids"][0]
            documents = results["documents"][0] if results["documents"] else [None] * len(ids)
            metadatas = results["metadatas"][0] if results["metadatas"] else [{}] * len(ids)
            distances = results["distances"][0] if results["distances"] else [0] * len(ids)
            
            for chunk_id, doc, meta, dist in zip(ids, documents, metadatas, distances):
                # Convert distance to similarity score
                # ChromaDB returns L2 distance by default, convert to similarity
                # For normalized embeddings, L2 distance of 0 = similarity of 1
                similarity = 1 - (dist / 2)  # Approximate conversion
                
                search_results.append(SearchResult(
                    chunk_id=chunk_id,
                    text=doc or "",
                    metadata=meta or {},
                    score=similarity,
                ))
        
        return search_results
    
    def search_by_embedding(
        self,
        embedding: list[float],
        n_results: int = 10,
        where: Optional[dict] = None,
    ) -> list[SearchResult]:
        """
        Search using a pre-computed embedding.
        
        Args:
            embedding: Query embedding vector
            n_results: Number of results to return
            where: Metadata filter
            
        Returns:
            List of SearchResult objects
        """
        results = self.collection.query(
            query_embeddings=[embedding],
            n_results=n_results,
            where=where,
            include=["documents", "metadatas", "distances"],
        )
        
        search_results = []
        
        if results and results["ids"] and results["ids"][0]:
            ids = results["ids"][0]
            documents = results["documents"][0] if results["documents"] else [None] * len(ids)
            metadatas = results["metadatas"][0] if results["metadatas"] else [{}] * len(ids)
            distances = results["distances"][0] if results["distances"] else [0] * len(ids)
            
            for chunk_id, doc, meta, dist in zip(ids, documents, metadatas, distances):
                similarity = 1 - (dist / 2)
                search_results.append(SearchResult(
                    chunk_id=chunk_id,
                    text=doc or "",
                    metadata=meta or {},
                    score=similarity,
                ))
        
        return search_results
    
    def get_by_id(self, chunk_id: str) -> Optional[SearchResult]:
        """
        Get a specific chunk by ID.
        
        Args:
            chunk_id: The chunk ID to retrieve
            
        Returns:
            SearchResult or None if not found
        """
        results = self.collection.get(
            ids=[chunk_id],
            include=["documents", "metadatas"],
        )
        
        if results and results["ids"]:
            return SearchResult(
                chunk_id=results["ids"][0],
                text=results["documents"][0] if results["documents"] else "",
                metadata=results["metadatas"][0] if results["metadatas"] else {},
                score=1.0,  # Perfect match for direct retrieval
            )
        
        return None
    
    def get_by_ids(self, chunk_ids: list[str]) -> list[SearchResult]:
        """
        Get multiple chunks by ID.
        
        Args:
            chunk_ids: List of chunk IDs to retrieve
            
        Returns:
            List of SearchResult objects
        """
        results = self.collection.get(
            ids=chunk_ids,
            include=["documents", "metadatas"],
        )
        
        search_results = []
        
        if results and results["ids"]:
            for i, chunk_id in enumerate(results["ids"]):
                search_results.append(SearchResult(
                    chunk_id=chunk_id,
                    text=results["documents"][i] if results["documents"] else "",
                    metadata=results["metadatas"][i] if results["metadatas"] else {},
                    score=1.0,
                ))
        
        return search_results
    
    def count(self) -> int:
        """Get the total number of chunks in the store."""
        return self.collection.count()
    
    def delete_all(self) -> None:
        """Delete all chunks from the store."""
        # Delete and recreate the collection
        self._client.delete_collection(self.COLLECTION_NAME)
        self._collection = None
        
        if DEBUG:
            print("All chunks deleted from vector store")
    
    def get_stats(self) -> dict:
        """Get statistics about the vector store."""
        count = self.count()
        
        # Sample some metadata to get available fields
        sample = self.collection.peek(limit=10)
        
        metadata_fields = set()
        chunk_types = set()
        
        if sample and sample["metadatas"]:
            for meta in sample["metadatas"]:
                metadata_fields.update(meta.keys())
                if "chunk_type" in meta:
                    chunk_types.add(meta["chunk_type"])
        
        return {
            "total_chunks": count,
            "collection_name": self.COLLECTION_NAME,
            "embedding_model": self.embedding_model,
            "persist_directory": self.persist_directory,
            "metadata_fields": sorted(metadata_fields),
            "chunk_types_sample": sorted(chunk_types),
        }
    
    def list_chunk_types(self) -> dict[str, int]:
        """
        Get counts of each chunk type.
        
        Note: This requires scanning all chunks, may be slow for large collections.
        """
        # Get all metadata
        all_data = self.collection.get(include=["metadatas"])
        
        type_counts = {}
        if all_data and all_data["metadatas"]:
            for meta in all_data["metadatas"]:
                chunk_type = meta.get("chunk_type", "unknown")
                type_counts[chunk_type] = type_counts.get(chunk_type, 0) + 1
        
        return type_counts


def build_metadata_filter(
    chunk_type: Optional[str] = None,
    team: Optional[str] = None,
    player_name: Optional[str] = None,
    season: Optional[int] = None,
    position: Optional[str] = None,
    venue_type: Optional[str] = None,
    temperature_category: Optional[str] = None,
    was_favorite: Optional[bool] = None,
    was_underdog: Optional[bool] = None,
    is_playoff: Optional[bool] = None,
    opponent: Optional[str] = None,
    game_type: Optional[Any] = None,  # Can be string or dict like {"$ne": "REG"}
    **kwargs,
) -> Optional[dict]:
    """
    Build a ChromaDB metadata filter from common parameters.
    
    Args:
        chunk_type: Filter by chunk type (player_season, player_game, etc.)
        team: Filter by team abbreviation
        player_name: Filter by player name (exact match)
        season: Filter by season year
        position: Filter by position
        venue_type: Filter by venue type (outdoor, dome)
        temperature_category: Filter by temperature category
        was_favorite: Filter by favorite status
        was_underdog: Filter by underdog status
        is_playoff: Filter by playoff game
        opponent: Filter by opponent team
        game_type: Filter by game type (REG, POST, WC, DIV, CON, SB) or dict like {"$ne": "REG"}
        **kwargs: Additional filters
        
    Returns:
        ChromaDB where filter dict, or None if no filters
    """
    conditions = []
    
    if chunk_type:
        conditions.append({"chunk_type": chunk_type})
    if team:
        conditions.append({"team": team})
    if player_name:
        conditions.append({"player_name": player_name})
    if season:
        conditions.append({"season": season})
    if position:
        conditions.append({"position": position})
    if venue_type:
        conditions.append({"venue_type": venue_type})
    if temperature_category:
        conditions.append({"temperature_category": temperature_category})
    if was_favorite is not None:
        conditions.append({"was_favorite": was_favorite})
    if was_underdog is not None:
        conditions.append({"was_underdog": was_underdog})
    if is_playoff is not None:
        conditions.append({"is_playoff": is_playoff})
    if opponent:
        conditions.append({"opponent": opponent})
    if game_type is not None:
        if isinstance(game_type, dict):
            # Complex filter like {"$ne": "REG"}
            conditions.append({"game_type": game_type})
        else:
            conditions.append({"game_type": game_type})
    
    # Add any additional filters
    for key, value in kwargs.items():
        if value is not None:
            conditions.append({key: value})
    
    if not conditions:
        return None
    
    if len(conditions) == 1:
        return conditions[0]
    
    return {"$and": conditions}


# CLI for testing
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="NFL Vector Store operations")
    parser.add_argument("--stats", action="store_true", help="Show store statistics")
    parser.add_argument("--search", type=str, help="Search query")
    parser.add_argument("--team", type=str, help="Filter by team")
    parser.add_argument("--player", type=str, help="Filter by player name")
    parser.add_argument("--type", type=str, help="Filter by chunk type")
    parser.add_argument("-n", type=int, default=5, help="Number of results")
    
    args = parser.parse_args()
    
    store = NFLVectorStore()
    
    if args.stats:
        print("Vector Store Statistics")
        print("=" * 60)
        stats = store.get_stats()
        for key, value in stats.items():
            print(f"  {key}: {value}")
        
        if stats["total_chunks"] > 0:
            print("\nChunk type counts:")
            type_counts = store.list_chunk_types()
            for chunk_type, count in sorted(type_counts.items()):
                print(f"  {chunk_type}: {count}")
    
    elif args.search:
        print(f"Searching: '{args.search}'")
        print("=" * 60)
        
        # Build filter
        where = build_metadata_filter(
            chunk_type=args.type,
            team=args.team,
            player_name=args.player,
        )
        
        if where:
            print(f"Filter: {where}")
        
        results = store.search(
            query=args.search,
            n_results=args.n,
            where=where,
        )
        
        if results:
            for i, result in enumerate(results, 1):
                print(f"\n--- Result {i} (score: {result.score:.3f}) ---")
                print(f"Type: {result.metadata.get('chunk_type', 'unknown')}")
                print(f"Text: {result.text[:300]}...")
        else:
            print("No results found")
    
    else:
        parser.print_help()