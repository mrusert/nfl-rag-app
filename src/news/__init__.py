"""
NFL News & Opinions Module.

Fetches and processes NFL news from various sources:
- ESPN
- NFL.com
- Reddit (r/nfl, team subreddits)

News is stored in ChromaDB for semantic search and can be
accessed via the agent's news_search tool.
"""

from src.news.fetcher import NewsFetcher
from src.news.storage import NewsStorage

__all__ = ["NewsFetcher", "NewsStorage"]
