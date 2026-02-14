"""
Feedback Runner - Interactive testing mode for the NFL app.

Provides a CLI for:
- Asking questions and getting responses
- Rating responses (correct/incorrect/partial)
- Providing correct answers for incorrect responses
- Adding notes about issues

Usage:
    python -m src.feedback.runner --interactive
"""

import argparse
from typing import Optional

from src.agent.agent import NFLStatsAgent
from src.feedback.storage import FeedbackStorage, Rating


class FeedbackRunner:
    """
    Interactive feedback testing system.

    Allows users to test the app and rate responses,
    building a library of feedback for improvement.
    """

    def __init__(self):
        self.storage = FeedbackStorage()
        self.agent = NFLStatsAgent()

    def ask(self, question: str, verbose: bool = False) -> dict:
        """
        Ask a question and return the response.

        Returns dict with question, response, entry_id for rating.
        """
        response = self.agent.run(question, verbose=verbose)

        entry = self.storage.add(
            question=question,
            response=response.answer,
            mode="agent",
            tool_calls=[tc["tool"] for tc in response.tool_calls],
            response_time_ms=response.total_time_ms,
        )

        return {
            "entry_id": entry.id,
            "question": question,
            "answer": response.answer,
            "tools_used": [tc["tool"] for tc in response.tool_calls],
            "time_ms": response.total_time_ms,
        }

    def rate(
        self,
        entry_id: str,
        rating: str,
        correct_answer: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> bool:
        """Rate a response."""
        entry = self.storage.rate(entry_id, rating, correct_answer, notes)
        return entry is not None

    def interactive(self, verbose: bool = False):
        """Run interactive feedback mode."""
        print("\n" + "=" * 60)
        print("NFL Stats - Feedback Mode")
        print("=" * 60)
        print("\nThis mode lets you test the app and rate responses.")
        print("Your feedback helps improve accuracy!")
        print("\nCommands:")
        print("  Type a question to test")
        print("  'stats' - Show feedback statistics")
        print("  'recent' - Show recent feedback")
        print("  'quit' - Exit\n")

        if not self.agent.is_available():
            print("Warning: LLM not available. Make sure Ollama is running.")
            print("Start with: ollama serve\n")

        while True:
            try:
                user_input = input("Question: ").strip()
            except (KeyboardInterrupt, EOFError):
                print("\nGoodbye!")
                break

            if not user_input:
                continue

            if user_input.lower() in ("quit", "exit", "q"):
                print("Goodbye!")
                break

            if user_input.lower() == "stats":
                self._show_stats()
                continue

            if user_input.lower() == "recent":
                self._show_recent()
                continue

            # Ask the question
            print("\nThinking...")
            try:
                result = self.ask(user_input, verbose=verbose)
            except Exception as e:
                print(f"Error: {e}")
                continue

            # Show response
            print("\n" + "-" * 60)
            print(f"Answer: {result['answer']}")
            print("-" * 60)
            print(f"Tools: {result['tools_used']}")
            print(f"Time: {result['time_ms']:.0f}ms")
            print(f"Entry ID: {result['entry_id']}")

            # Get rating
            self._get_rating(result["entry_id"])

    def _get_rating(self, entry_id: str):
        """Prompt user for rating."""
        print("\nRate this response:")
        print("  [c] Correct")
        print("  [i] Incorrect")
        print("  [p] Partially correct")
        print("  [s] Skip (don't rate)")

        while True:
            choice = input("Rating: ").strip().lower()

            if choice == "s":
                print("Skipped.")
                return

            rating_map = {
                "c": "correct",
                "i": "incorrect",
                "p": "partial",
            }

            if choice not in rating_map:
                print("Invalid choice. Use c/i/p/s")
                continue

            rating = rating_map[choice]

            # Get correct answer if incorrect/partial
            correct_answer = None
            notes = None

            if rating in ("incorrect", "partial"):
                correct_answer = input("What should the correct answer be? (or press Enter to skip): ").strip()
                if not correct_answer:
                    correct_answer = None

            notes = input("Any notes? (or press Enter to skip): ").strip()
            if not notes:
                notes = None

            self.rate(entry_id, rating, correct_answer, notes)
            print(f"Rated as: {rating}")
            return

    def _show_stats(self):
        """Display feedback statistics."""
        stats = self.storage.stats()
        print("\nFeedback Statistics")
        print("=" * 40)
        print(f"Total entries: {stats['total']}")
        print(f"\nBy rating:")
        for rating, count in stats['by_rating'].items():
            pct = count / stats['total'] * 100 if stats['total'] > 0 else 0
            print(f"  {rating}: {count} ({pct:.1f}%)")
        print(f"\nExportable to tests: {stats['exportable']}")

    def _show_recent(self, n: int = 5):
        """Show recent entries."""
        entries = self.storage.recent(n)
        print(f"\nLast {n} entries:")
        print("-" * 40)
        for e in entries:
            status = e.rating or "unrated"
            print(f"[{e.id}] {status}")
            print(f"  Q: {e.question[:50]}...")
            print(f"  A: {e.response[:60]}...")
            print()


def export_to_tests(output_file: str = None):
    """
    Export approved feedback entries to test cases.

    Creates pytest test cases from feedback marked as correct
    with verified answers.
    """
    storage = FeedbackStorage()
    exportable = storage.get_exportable()

    if not exportable:
        print("No exportable entries found.")
        print("Mark entries as 'correct' with a verified answer to export.")
        return

    print(f"Found {len(exportable)} exportable entries.")

    test_code = '''"""
Auto-generated test cases from feedback.

Generated: {timestamp}
"""

import pytest
from src.agent.tools import SQLQueryTool, PlayerStatsLookupTool, RankingsTool


class TestFeedbackDerived:
    """Test cases derived from user feedback."""

'''

    for entry in exportable:
        # Create test function
        func_name = f"test_{entry.id}"
        test_code += f'''
    def {func_name}(self):
        """
        Question: {entry.question}
        Expected: {entry.correct_answer}
        """
        # TODO: Implement test based on feedback
        # Original response: {entry.response[:100]}...
        pass

'''
        storage.mark_exported(entry.id)

    from datetime import datetime
    test_code = test_code.format(timestamp=datetime.now().isoformat())

    output_path = output_file or "tests/test_feedback_derived.py"
    print(f"Writing to {output_path}...")

    with open(output_path, "w") as f:
        f.write(test_code)

    print(f"Exported {len(exportable)} test cases.")
    print("Edit the generated file to implement the actual test assertions.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NFL Feedback Runner")
    parser.add_argument("--interactive", "-i", action="store_true", help="Interactive mode")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show tool calls")
    parser.add_argument("--export", action="store_true", help="Export feedback to tests")
    parser.add_argument("--output", type=str, help="Output file for export")
    parser.add_argument("--ask", type=str, help="Ask a single question")

    args = parser.parse_args()

    if args.export:
        export_to_tests(args.output)
    elif args.interactive:
        runner = FeedbackRunner()
        runner.interactive(verbose=args.verbose)
    elif args.ask:
        runner = FeedbackRunner()
        result = runner.ask(args.ask, verbose=args.verbose)
        print(f"\nAnswer: {result['answer']}")
        print(f"Tools: {result['tools_used']}")
        print(f"Entry ID: {result['entry_id']}")
        print("\nUse --interactive to rate responses.")
    else:
        parser.print_help()
