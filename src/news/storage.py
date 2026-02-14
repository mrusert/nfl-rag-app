"""
News Storage - Store and retrieve NFL news using ChromaDB.

News items are stored with embeddings for semantic search,
separate from the main stats vector store.
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Optional

import chromadb
from chromadb.config import Settings

from src.config import PROJECT_ROOT, EMBEDDING_MODEL
from src.news.fetcher import NewsItem, NewsFetcher


NEWS_DB_PATH = PROJECT_ROOT / "news_db"


class NewsStorage:
    """
    ChromaDB-based storage for NFL news.

    Stores news items with embeddings for semantic search.
    Separate from main stats data to keep concerns separated.
    """

    COLLECTION_NAME = "nfl_news"

    def __init__(self, persist_directory: Path = NEWS_DB_PATH):
        """Initialize the news storage."""
        self.persist_directory = persist_directory
        self.persist_directory.mkdir(parents=True, exist_ok=True)

        # Initialize ChromaDB
        self.client = chromadb.PersistentClient(
            path=str(self.persist_directory),
            settings=Settings(anonymized_telemetry=False)
        )

        # Get or create collection
        self.collection = self.client.get_or_create_collection(
            name=self.COLLECTION_NAME,
            metadata={"description": "NFL news and opinions from ESPN, NFL.com, Reddit"}
        )

    def add_items(self, items: list[NewsItem], batch_size: int = 100) -> int:
        """
        Add news items to the collection.

        Returns number of items added (skips duplicates).
        """
        added = 0

        # Process in batches
        for i in range(0, len(items), batch_size):
            batch = items[i:i + batch_size]

            ids = []
            documents = []
            metadatas = []

            for item in batch:
                # Check if already exists
                existing = self.collection.get(ids=[item.id])
                if existing["ids"]:
                    continue

                # Create document text for embedding
                doc_text = f"{item.title}\n\n{item.content}"

                ids.append(item.id)
                documents.append(doc_text)
                metadatas.append({
                    "title": item.title,
                    "source": item.source,
                    "url": item.url,
                    "published_at": item.published_at,
                    "author": item.author or "",
                    "team": item.team or "",
                    "tags": ",".join(item.tags),
                })

            if ids:
                self.collection.add(
                    ids=ids,
                    documents=documents,
                    metadatas=metadatas,
                )
                added += len(ids)

        return added

    def search(
        self,
        query: str,
        n_results: int = 10,
        source: Optional[str] = None,
        team: Optional[str] = None,
    ) -> list[dict]:
        """
        Search news by semantic similarity.

        Args:
            query: Search query
            n_results: Number of results to return
            source: Filter by source ("espn", "nfl.com", "reddit")
            team: Filter by team abbreviation

        Returns:
            List of matching news items with scores
        """
        # Build filter
        where = None
        if source or team:
            conditions = []
            if source:
                conditions.append({"source": source})
            if team:
                conditions.append({"team": team})

            if len(conditions) == 1:
                where = conditions[0]
            else:
                where = {"$and": conditions}

        results = self.collection.query(
            query_texts=[query],
            n_results=n_results,
            where=where,
        )

        # Format results
        items = []
        for i, doc_id in enumerate(results["ids"][0]):
            metadata = results["metadatas"][0][i]
            distance = results["distances"][0][i] if results.get("distances") else None

            items.append({
                "id": doc_id,
                "title": metadata.get("title", ""),
                "source": metadata.get("source", ""),
                "url": metadata.get("url", ""),
                "published_at": metadata.get("published_at", ""),
                "team": metadata.get("team", ""),
                "score": 1 - distance if distance else None,  # Convert distance to similarity
                "preview": results["documents"][0][i][:200] + "..." if results["documents"] else "",
            })

        return items

    def get_recent(self, limit: int = 20, source: Optional[str] = None) -> list[dict]:
        """Get most recent news items."""
        where = {"source": source} if source else None

        # Get all items (ChromaDB doesn't have great sorting, so we fetch and sort)
        results = self.collection.get(
            where=where,
            limit=limit * 3,  # Fetch extra to account for sorting
        )

        items = []
        for i, doc_id in enumerate(results["ids"]):
            metadata = results["metadatas"][i]
            items.append({
                "id": doc_id,
                "title": metadata.get("title", ""),
                "source": metadata.get("source", ""),
                "url": metadata.get("url", ""),
                "published_at": metadata.get("published_at", ""),
                "team": metadata.get("team", ""),
            })

        # Sort by published date
        items.sort(key=lambda x: x["published_at"], reverse=True)

        return items[:limit]

    def count(self) -> int:
        """Get total number of news items."""
        return self.collection.count()

    def stats(self) -> dict:
        """Get statistics about stored news."""
        total = self.count()

        # Count by source
        by_source = {}
        for source in ["espn", "nfl.com", "reddit"]:
            results = self.collection.get(where={"source": source})
            by_source[source] = len(results["ids"])

        return {
            "total": total,
            "by_source": by_source,
        }

    def clear(self):
        """Clear all news items."""
        self.client.delete_collection(self.COLLECTION_NAME)
        self.collection = self.client.get_or_create_collection(
            name=self.COLLECTION_NAME,
            metadata={"description": "NFL news and opinions from ESPN, NFL.com, Reddit"}
        )


def fetch_and_store_news(
    sources: list[str] = None,
    include_team_content: bool = True,
) -> dict:
    """
    Convenience function to fetch news and store it.

    Returns stats about what was fetched/stored.
    """
    fetcher = NewsFetcher()
    storage = NewsStorage()

    print("Fetching news...")
    items = fetcher.fetch_all(sources=sources, include_team_content=include_team_content)

    print(f"Storing {len(items)} items...")
    added = storage.add_items(items)

    stats = storage.stats()

    return {
        "fetched": len(items),
        "added": added,
        "total_stored": stats["total"],
        "by_source": stats["by_source"],
    }


# CLI
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="NFL News Storage")
    parser.add_argument("--fetch", action="store_true", help="Fetch and store news")
    parser.add_argument("--search", type=str, help="Search query")
    parser.add_argument("--recent", action="store_true", help="Show recent news")
    parser.add_argument("--stats", action="store_true", help="Show statistics")
    parser.add_argument("--source", type=str, help="Filter by source")
    parser.add_argument("--team", type=str, help="Filter by team")
    parser.add_argument("--clear", action="store_true", help="Clear all news")

    args = parser.parse_args()

    storage = NewsStorage()

    if args.fetch:
        result = fetch_and_store_news()
        print("\nFetch Results:")
        print(f"  Fetched: {result['fetched']}")
        print(f"  Added: {result['added']}")
        print(f"  Total stored: {result['total_stored']}")
        print(f"  By source: {result['by_source']}")

    elif args.search:
        results = storage.search(args.search, source=args.source, team=args.team)
        print(f"\nSearch results for '{args.search}':")
        for item in results:
            print(f"\n[{item['source']}] {item['title'][:60]}...")
            print(f"  Score: {item['score']:.3f}" if item['score'] else "")
            print(f"  URL: {item['url']}")

    elif args.recent:
        items = storage.get_recent(source=args.source)
        print("\nRecent news:")
        for item in items:
            print(f"\n[{item['source']}] {item['title'][:60]}...")
            print(f"  {item['published_at']}")

    elif args.stats:
        stats = storage.stats()
        print("\nNews Storage Stats:")
        print(f"  Total: {stats['total']}")
        print(f"  By source: {stats['by_source']}")

    elif args.clear:
        storage.clear()
        print("News storage cleared.")

    else:
        parser.print_help()
