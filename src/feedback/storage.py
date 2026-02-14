"""
Feedback storage - Persists feedback data for analysis and improvement.

Stores:
- Questions asked
- Responses from the app
- User ratings and corrections
- Tool calls made

Can be used to:
- Identify common failures
- Generate golden test cases
- Track improvement over time
"""

import json
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, asdict, field
from typing import Optional, Literal
from enum import Enum

from src.config import DATA_DIR


FEEDBACK_DIR = DATA_DIR / "feedback"
FEEDBACK_FILE = FEEDBACK_DIR / "feedback_log.json"


class Rating(str, Enum):
    """Feedback ratings."""
    CORRECT = "correct"
    INCORRECT = "incorrect"
    PARTIAL = "partial"
    NEEDS_IMPROVEMENT = "needs_improvement"


@dataclass
class FeedbackEntry:
    """A single feedback entry."""
    id: str
    timestamp: str
    question: str
    response: str
    mode: Literal["agent", "rag"]
    rating: Optional[str] = None
    correct_answer: Optional[str] = None
    notes: Optional[str] = None
    tool_calls: list = field(default_factory=list)
    response_time_ms: float = 0.0
    exported_to_test: bool = False

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "FeedbackEntry":
        return cls(**data)


class FeedbackStorage:
    """
    Manages feedback storage and retrieval.

    Feedback is stored as JSON for easy inspection and editing.
    """

    def __init__(self, feedback_file: Path = FEEDBACK_FILE):
        self.feedback_file = feedback_file
        self.feedback_file.parent.mkdir(parents=True, exist_ok=True)

        # Load existing feedback
        self.entries: list[FeedbackEntry] = []
        self._load()

    def _load(self):
        """Load feedback from file."""
        if self.feedback_file.exists():
            with open(self.feedback_file, "r") as f:
                data = json.load(f)
                self.entries = [FeedbackEntry.from_dict(e) for e in data]

    def _save(self):
        """Save feedback to file."""
        with open(self.feedback_file, "w") as f:
            json.dump([e.to_dict() for e in self.entries], f, indent=2)

    def _generate_id(self) -> str:
        """Generate unique ID for entry."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        count = len([e for e in self.entries if e.id.startswith(timestamp)])
        return f"{timestamp}_{count:03d}"

    def add(
        self,
        question: str,
        response: str,
        mode: str,
        tool_calls: list = None,
        response_time_ms: float = 0.0,
    ) -> FeedbackEntry:
        """Add a new feedback entry (without rating yet)."""
        entry = FeedbackEntry(
            id=self._generate_id(),
            timestamp=datetime.now().isoformat(),
            question=question,
            response=response,
            mode=mode,
            tool_calls=tool_calls or [],
            response_time_ms=response_time_ms,
        )
        self.entries.append(entry)
        self._save()
        return entry

    def rate(
        self,
        entry_id: str,
        rating: str,
        correct_answer: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> Optional[FeedbackEntry]:
        """Rate an existing entry."""
        for entry in self.entries:
            if entry.id == entry_id:
                entry.rating = rating
                entry.correct_answer = correct_answer
                entry.notes = notes
                self._save()
                return entry
        return None

    def get(self, entry_id: str) -> Optional[FeedbackEntry]:
        """Get entry by ID."""
        for entry in self.entries:
            if entry.id == entry_id:
                return entry
        return None

    def get_unrated(self) -> list[FeedbackEntry]:
        """Get all unrated entries."""
        return [e for e in self.entries if e.rating is None]

    def get_by_rating(self, rating: str) -> list[FeedbackEntry]:
        """Get entries with specific rating."""
        return [e for e in self.entries if e.rating == rating]

    def get_incorrect(self) -> list[FeedbackEntry]:
        """Get all incorrect/partial entries."""
        return [e for e in self.entries if e.rating in ("incorrect", "partial")]

    def get_exportable(self) -> list[FeedbackEntry]:
        """Get entries that can be exported as test cases."""
        return [
            e for e in self.entries
            if e.rating == "correct" and e.correct_answer and not e.exported_to_test
        ]

    def mark_exported(self, entry_id: str):
        """Mark entry as exported to test."""
        for entry in self.entries:
            if entry.id == entry_id:
                entry.exported_to_test = True
                self._save()
                break

    def stats(self) -> dict:
        """Get feedback statistics."""
        total = len(self.entries)
        by_rating = {}
        for entry in self.entries:
            rating = entry.rating or "unrated"
            by_rating[rating] = by_rating.get(rating, 0) + 1

        by_mode = {}
        for entry in self.entries:
            by_mode[entry.mode] = by_mode.get(entry.mode, 0) + 1

        return {
            "total": total,
            "by_rating": by_rating,
            "by_mode": by_mode,
            "exportable": len(self.get_exportable()),
        }

    def search(self, query: str) -> list[FeedbackEntry]:
        """Search entries by question text."""
        query_lower = query.lower()
        return [
            e for e in self.entries
            if query_lower in e.question.lower() or query_lower in e.response.lower()
        ]

    def recent(self, limit: int = 10) -> list[FeedbackEntry]:
        """Get most recent entries."""
        return sorted(self.entries, key=lambda e: e.timestamp, reverse=True)[:limit]


# CLI for viewing feedback
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Feedback Storage Manager")
    parser.add_argument("--stats", action="store_true", help="Show statistics")
    parser.add_argument("--recent", type=int, default=0, help="Show N recent entries")
    parser.add_argument("--unrated", action="store_true", help="Show unrated entries")
    parser.add_argument("--incorrect", action="store_true", help="Show incorrect entries")
    parser.add_argument("--search", type=str, help="Search entries")

    args = parser.parse_args()

    storage = FeedbackStorage()

    if args.stats:
        stats = storage.stats()
        print("Feedback Statistics")
        print("=" * 40)
        print(f"Total entries: {stats['total']}")
        print(f"\nBy rating:")
        for rating, count in stats['by_rating'].items():
            print(f"  {rating}: {count}")
        print(f"\nBy mode:")
        for mode, count in stats['by_mode'].items():
            print(f"  {mode}: {count}")
        print(f"\nExportable to tests: {stats['exportable']}")

    elif args.recent:
        entries = storage.recent(args.recent)
        for e in entries:
            print(f"\n[{e.id}] {e.mode.upper()} - {e.rating or 'unrated'}")
            print(f"Q: {e.question[:80]}...")
            print(f"A: {e.response[:100]}...")

    elif args.unrated:
        entries = storage.get_unrated()
        print(f"Found {len(entries)} unrated entries:")
        for e in entries:
            print(f"  [{e.id}] {e.question[:60]}...")

    elif args.incorrect:
        entries = storage.get_incorrect()
        print(f"Found {len(entries)} incorrect entries:")
        for e in entries:
            print(f"\n[{e.id}] {e.question}")
            print(f"  Got: {e.response[:80]}...")
            if e.correct_answer:
                print(f"  Expected: {e.correct_answer[:80]}...")

    elif args.search:
        entries = storage.search(args.search)
        print(f"Found {len(entries)} matching entries:")
        for e in entries:
            print(f"  [{e.id}] {e.question[:60]}...")

    else:
        parser.print_help()
