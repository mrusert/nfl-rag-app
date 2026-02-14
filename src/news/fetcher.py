"""
News Fetcher - Pull NFL news from various sources.

Sources:
- ESPN RSS feeds
- NFL.com RSS feeds
- Reddit API (r/nfl and team subreddits)

Each source returns standardized NewsItem objects.
"""

import json
import re
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Optional, Generator
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from src.config import DATA_DIR


@dataclass
class NewsItem:
    """A news article or post."""
    id: str
    title: str
    content: str
    source: str  # "espn", "nfl", "reddit"
    url: str
    published_at: str
    author: Optional[str] = None
    team: Optional[str] = None  # Team abbreviation if relevant
    tags: list = None

    def __post_init__(self):
        if self.tags is None:
            self.tags = []

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "NewsItem":
        return cls(**data)


class ESPNFetcher:
    """Fetch news from ESPN NFL RSS feeds."""

    BASE_URL = "https://www.espn.com"
    RSS_FEEDS = {
        "nfl": "https://www.espn.com/espn/rss/nfl/news",
        "nfl_analysis": "https://www.espn.com/blog/feed?blog=nflnation",
    }

    # Team-specific feeds (partial list)
    TEAM_FEEDS = {
        "KC": "https://www.espn.com/blog/feed?blog=kansas-city-chiefs",
        "BUF": "https://www.espn.com/blog/feed?blog=buffalo-bills",
        "SF": "https://www.espn.com/blog/feed?blog=san-francisco-49ers",
        "PHI": "https://www.espn.com/blog/feed?blog=philadelphia-eagles",
        "DAL": "https://www.espn.com/blog/feed?blog=dallas-cowboys",
    }

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "NFL-RAG-App/1.0 (Educational Project)"
        })

    def fetch_rss(self, url: str) -> list[NewsItem]:
        """Fetch and parse an RSS feed."""
        items = []

        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, "xml")

            for item in soup.find_all("item"):
                title = item.find("title")
                link = item.find("link")
                description = item.find("description")
                pub_date = item.find("pubDate")
                author = item.find("author") or item.find("dc:creator")

                if title and link:
                    news_item = NewsItem(
                        id=f"espn_{hash(link.text) % 10**8}",
                        title=title.text.strip(),
                        content=description.text.strip() if description else "",
                        source="espn",
                        url=link.text.strip(),
                        published_at=pub_date.text if pub_date else datetime.now().isoformat(),
                        author=author.text if author else None,
                        tags=["espn", "nfl"],
                    )
                    items.append(news_item)

        except Exception as e:
            print(f"Error fetching ESPN RSS {url}: {e}")

        return items

    def fetch_all(self, include_teams: bool = False) -> list[NewsItem]:
        """Fetch from all ESPN feeds."""
        all_items = []

        # Main feeds
        for name, url in self.RSS_FEEDS.items():
            print(f"  Fetching ESPN {name}...")
            items = self.fetch_rss(url)
            all_items.extend(items)
            time.sleep(1)  # Be respectful

        # Team feeds
        if include_teams:
            for team, url in self.TEAM_FEEDS.items():
                print(f"  Fetching ESPN {team}...")
                items = self.fetch_rss(url)
                for item in items:
                    item.team = team
                    item.tags.append(team)
                all_items.extend(items)
                time.sleep(1)

        return all_items


class NFLComFetcher:
    """Fetch news from NFL.com RSS feeds."""

    RSS_FEEDS = {
        "news": "https://www.nfl.com/rss/rsslanding?searchString=home",
        "fantasy": "https://www.nfl.com/rss/rsslanding?searchString=fantasy",
    }

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "NFL-RAG-App/1.0 (Educational Project)"
        })

    def fetch_rss(self, url: str) -> list[NewsItem]:
        """Fetch and parse NFL.com RSS feed."""
        items = []

        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, "xml")

            for item in soup.find_all("item"):
                title = item.find("title")
                link = item.find("link")
                description = item.find("description")
                pub_date = item.find("pubDate")

                if title and link:
                    news_item = NewsItem(
                        id=f"nfl_{hash(link.text) % 10**8}",
                        title=title.text.strip(),
                        content=description.text.strip() if description else "",
                        source="nfl.com",
                        url=link.text.strip(),
                        published_at=pub_date.text if pub_date else datetime.now().isoformat(),
                        tags=["nfl.com", "official"],
                    )
                    items.append(news_item)

        except Exception as e:
            print(f"Error fetching NFL.com RSS {url}: {e}")

        return items

    def fetch_all(self) -> list[NewsItem]:
        """Fetch from all NFL.com feeds."""
        all_items = []

        for name, url in self.RSS_FEEDS.items():
            print(f"  Fetching NFL.com {name}...")
            items = self.fetch_rss(url)
            all_items.extend(items)
            time.sleep(1)

        return all_items


class RedditFetcher:
    """Fetch posts from NFL-related subreddits using Reddit's JSON API."""

    BASE_URL = "https://www.reddit.com"

    SUBREDDITS = {
        "nfl": "r/nfl",
        "fantasy": "r/fantasyfootball",
        # Team subreddits
        "chiefs": "r/KansasCityChiefs",
        "bills": "r/buffalobills",
        "49ers": "r/49ers",
        "eagles": "r/eagles",
        "cowboys": "r/cowboys",
    }

    TEAM_MAPPING = {
        "chiefs": "KC",
        "bills": "BUF",
        "49ers": "SF",
        "eagles": "PHI",
        "cowboys": "DAL",
    }

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "NFL-RAG-App/1.0 (Educational Project; Contact: github.com/your-repo)"
        })

    def fetch_subreddit(self, subreddit: str, limit: int = 25, sort: str = "hot") -> list[NewsItem]:
        """Fetch posts from a subreddit using JSON API."""
        items = []
        url = f"{self.BASE_URL}/{subreddit}/{sort}.json?limit={limit}"

        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()

            data = response.json()

            for post in data.get("data", {}).get("children", []):
                post_data = post.get("data", {})

                # Skip stickied posts and very short posts
                if post_data.get("stickied"):
                    continue

                title = post_data.get("title", "")
                selftext = post_data.get("selftext", "")
                permalink = post_data.get("permalink", "")
                author = post_data.get("author", "")
                created = post_data.get("created_utc", 0)
                score = post_data.get("score", 0)

                # Skip low-quality posts
                if score < 10:
                    continue

                content = selftext if selftext else title

                news_item = NewsItem(
                    id=f"reddit_{post_data.get('id', '')}",
                    title=title,
                    content=content[:2000],  # Limit content length
                    source="reddit",
                    url=f"https://reddit.com{permalink}",
                    published_at=datetime.fromtimestamp(created).isoformat() if created else datetime.now().isoformat(),
                    author=f"u/{author}" if author else None,
                    tags=["reddit", subreddit.replace("r/", "")],
                )

                items.append(news_item)

        except Exception as e:
            print(f"Error fetching Reddit {subreddit}: {e}")

        return items

    def fetch_all(self, include_team_subs: bool = True) -> list[NewsItem]:
        """Fetch from all configured subreddits."""
        all_items = []

        for name, subreddit in self.SUBREDDITS.items():
            # Skip team subs if not requested
            if name in self.TEAM_MAPPING and not include_team_subs:
                continue

            print(f"  Fetching Reddit {subreddit}...")
            items = self.fetch_subreddit(subreddit)

            # Add team tag if applicable
            if name in self.TEAM_MAPPING:
                team = self.TEAM_MAPPING[name]
                for item in items:
                    item.team = team
                    item.tags.append(team)

            all_items.extend(items)
            time.sleep(2)  # Reddit rate limiting

        return all_items


class NewsFetcher:
    """
    Combined news fetcher for all sources.

    Usage:
        fetcher = NewsFetcher()
        news = fetcher.fetch_all()
    """

    def __init__(self):
        self.espn = ESPNFetcher()
        self.nfl = NFLComFetcher()
        self.reddit = RedditFetcher()

    def fetch_all(
        self,
        sources: list[str] = None,
        include_team_content: bool = True,
    ) -> list[NewsItem]:
        """
        Fetch news from all sources.

        Args:
            sources: List of sources to fetch from ["espn", "nfl", "reddit"]
                    None means all sources
            include_team_content: Include team-specific feeds/subreddits
        """
        if sources is None:
            sources = ["espn", "nfl", "reddit"]

        all_items = []

        if "espn" in sources:
            print("Fetching ESPN...")
            all_items.extend(self.espn.fetch_all(include_teams=include_team_content))

        if "nfl" in sources:
            print("Fetching NFL.com...")
            all_items.extend(self.nfl.fetch_all())

        if "reddit" in sources:
            print("Fetching Reddit...")
            all_items.extend(self.reddit.fetch_all(include_team_subs=include_team_content))

        # Deduplicate by URL
        seen_urls = set()
        unique_items = []
        for item in all_items:
            if item.url not in seen_urls:
                seen_urls.add(item.url)
                unique_items.append(item)

        print(f"\nFetched {len(unique_items)} unique news items")
        return unique_items

    def fetch_by_team(self, team: str) -> list[NewsItem]:
        """Fetch news related to a specific team."""
        all_items = self.fetch_all(include_team_content=True)
        return [item for item in all_items if item.team == team or team.lower() in str(item.tags).lower()]


# CLI for testing
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="NFL News Fetcher")
    parser.add_argument("--source", choices=["espn", "nfl", "reddit", "all"], default="all")
    parser.add_argument("--team", type=str, help="Filter by team abbreviation")
    parser.add_argument("--save", type=str, help="Save to JSON file")

    args = parser.parse_args()

    fetcher = NewsFetcher()

    if args.team:
        items = fetcher.fetch_by_team(args.team)
    else:
        sources = None if args.source == "all" else [args.source]
        items = fetcher.fetch_all(sources=sources)

    print(f"\nFetched {len(items)} items")

    # Show sample
    for item in items[:5]:
        print(f"\n[{item.source}] {item.title[:60]}...")
        print(f"  URL: {item.url}")
        print(f"  Tags: {item.tags}")

    if args.save:
        with open(args.save, "w") as f:
            json.dump([item.to_dict() for item in items], f, indent=2)
        print(f"\nSaved to {args.save}")
