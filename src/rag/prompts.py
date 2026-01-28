"""
RAG Prompt Builder for NFL RAG.

Contains prompt templates for different query types and
logic to build effective prompts for the LLM.
"""

from typing import Optional
from dataclasses import dataclass

from src.retrieval.vector_store import SearchResult


@dataclass
class RAGContext:
    """Context for RAG prompt building."""
    query: str
    results: list[SearchResult]
    max_context_length: int = 4000
    include_metadata: bool = True


# System prompt that sets the behavior of the NFL assistant
SYSTEM_PROMPT = """You are an expert NFL analyst assistant with deep knowledge of football statistics, players, teams, games, and betting lines.

Your role is to answer questions about the NFL using the provided context information. Follow these guidelines:

1. **Use the provided context**: Base your answers on the information given in the context. The context contains verified NFL data including game results, player statistics, weather conditions, and betting outcomes.

2. **Be specific**: When discussing statistics, include actual numbers. When discussing games, mention scores, dates, and relevant conditions.

3. **Acknowledge uncertainty**: If the context doesn't contain enough information to fully answer a question, say so. Don't make up statistics or game details.

4. **Be conversational**: While being accurate, maintain a natural, engaging tone like a knowledgeable sports analyst would.

5. **Weather and conditions**: When relevant, mention weather conditions as they can significantly impact game outcomes and player performance.

6. **Betting context**: When asked about spreads, over/unders, or betting outcomes, use the provided betting data accurately.

7. **Stay focused**: Only answer questions related to NFL football. Politely redirect off-topic questions."""


# Template for the main RAG prompt
RAG_PROMPT_TEMPLATE = """Based on the following NFL data, please answer the question.

## Context Information

{context}

## Question

{query}

## Instructions

Answer the question using the context provided above. Be specific and cite relevant statistics, scores, or details from the context. If the context doesn't contain enough information to answer the question, acknowledge this."""


# Template for follow-up questions
FOLLOWUP_PROMPT_TEMPLATE = """Based on our conversation and the following additional context, please answer the follow-up question.

## Previous Context
{previous_context}

## Additional Context
{context}

## Follow-up Question
{query}

Please provide a relevant answer based on all available information."""


class RAGPromptBuilder:
    """
    Builds prompts for RAG queries.
    
    Handles:
    - Formatting retrieved context
    - Building effective prompts
    - Managing context length limits
    """
    
    def __init__(
        self,
        system_prompt: Optional[str] = None,
        max_context_chars: int = 6000,
    ):
        """
        Initialize the prompt builder.
        
        Args:
            system_prompt: Custom system prompt (uses default if not provided)
            max_context_chars: Maximum characters for context section
        """
        self.system_prompt = system_prompt or SYSTEM_PROMPT
        self.max_context_chars = max_context_chars
    
    def format_result(self, result: SearchResult, index: int) -> str:
        """
        Format a single search result for the prompt.
        
        Args:
            result: SearchResult to format
            index: Result index (1-based)
            
        Returns:
            Formatted string for the result
        """
        lines = [f"### Source {index}"]
        
        # Add metadata header
        meta = result.metadata
        chunk_type = meta.get("chunk_type", "unknown")
        
        if chunk_type == "game_summary":
            game_type = meta.get("game_type", "REG")
            season = meta.get("season", "")
            week = meta.get("week", "")
            home = meta.get("home_team_name", meta.get("home_team", ""))
            away = meta.get("away_team_name", meta.get("away_team", ""))
            lines.append(f"*{season} {'Playoff ' if meta.get('is_playoff') else ''}Week {week}: {away} at {home}*")
            
        elif chunk_type == "player_game":
            player = meta.get("player_name", "")
            team = meta.get("team_name", meta.get("team", ""))
            season = meta.get("season", "")
            week = meta.get("week", "")
            lines.append(f"*{player} ({team}) - {season} Week {week}*")
            
        elif chunk_type == "player_season":
            player = meta.get("player_name", "")
            team = meta.get("team_name", meta.get("team", ""))
            season = meta.get("season", "")
            lines.append(f"*{player} ({team}) - {season} Season*")
            
        elif chunk_type == "player_bio":
            player = meta.get("player_name", "")
            team = meta.get("team_name", meta.get("team", ""))
            lines.append(f"*{player} ({team}) - Player Profile*")
            
        elif chunk_type == "team_info":
            team = meta.get("team_name", "")
            lines.append(f"*{team} - Team Info*")
        
        # Add the actual content
        lines.append("")
        lines.append(result.text)
        lines.append("")
        
        return "\n".join(lines)
    
    def build_context(
        self,
        results: list[SearchResult],
        max_results: Optional[int] = None,
    ) -> str:
        """
        Build the context section from search results.
        
        Args:
            results: List of SearchResults
            max_results: Maximum number of results to include
            
        Returns:
            Formatted context string
        """
        if not results:
            return "No relevant information found in the database."
        
        context_parts = []
        total_chars = 0
        
        for i, result in enumerate(results):
            if max_results and i >= max_results:
                break
            
            formatted = self.format_result(result, i + 1)
            
            # Check if adding this would exceed limit
            if total_chars + len(formatted) > self.max_context_chars:
                # Try to include at least 2 results
                if i < 2:
                    # Truncate this result
                    available = self.max_context_chars - total_chars - 100
                    if available > 200:
                        formatted = formatted[:available] + "\n[...truncated...]"
                    else:
                        break
                else:
                    break
            
            context_parts.append(formatted)
            total_chars += len(formatted)
        
        return "\n---\n".join(context_parts)
    
    def build_prompt(
        self,
        query: str,
        results: list[SearchResult],
        max_results: int = 5,
    ) -> tuple[str, str]:
        """
        Build the complete RAG prompt.
        
        Args:
            query: User's question
            results: Retrieved search results
            max_results: Maximum results to include in context
            
        Returns:
            Tuple of (system_prompt, user_prompt)
        """
        context = self.build_context(results, max_results=max_results)
        
        user_prompt = RAG_PROMPT_TEMPLATE.format(
            context=context,
            query=query,
        )
        
        return self.system_prompt, user_prompt
    
    def build_chat_messages(
        self,
        query: str,
        results: list[SearchResult],
        conversation_history: Optional[list[dict]] = None,
        max_results: int = 5,
    ) -> list[dict]:
        """
        Build chat messages for conversational RAG.
        
        Args:
            query: Current user question
            results: Retrieved search results
            conversation_history: Previous messages
            max_results: Maximum results to include
            
        Returns:
            List of message dicts for chat API
        """
        messages = [
            {"role": "system", "content": self.system_prompt}
        ]
        
        # Add conversation history
        if conversation_history:
            messages.extend(conversation_history)
        
        # Build current context and query
        context = self.build_context(results, max_results=max_results)
        
        user_content = f"""Based on the following NFL data, please answer my question.

## Context Information

{context}

## My Question

{query}"""
        
        messages.append({"role": "user", "content": user_content})
        
        return messages
    
    def build_simple_prompt(self, query: str, results: list[SearchResult]) -> str:
        """
        Build a simple combined prompt (for non-chat models).
        
        Args:
            query: User's question
            results: Retrieved search results
            
        Returns:
            Combined prompt string
        """
        system, user = self.build_prompt(query, results)
        return f"{system}\n\n---\n\n{user}"


# Specialized prompt templates for different query types

COMPARISON_PROMPT = """Compare the following NFL data and provide an analysis.

## Data for Comparison

{context}

## Comparison Question

{query}

Provide a clear comparison highlighting key differences and similarities. Use specific statistics and data points."""


PREDICTION_DISCLAIMER = """

Note: While I can analyze historical data and trends, I cannot predict future outcomes. My analysis is based solely on past performance data."""


def detect_query_type(query: str) -> str:
    """
    Detect the type of query for specialized handling.
    
    Args:
        query: User's question
        
    Returns:
        Query type: "comparison", "prediction", "stats", "general"
    """
    query_lower = query.lower()
    
    # Comparison queries
    if any(word in query_lower for word in ["compare", "versus", "vs", "better", "difference between"]):
        return "comparison"
    
    # Prediction queries
    if any(word in query_lower for word in ["will", "predict", "going to", "chances", "likelihood"]):
        return "prediction"
    
    # Statistics queries
    if any(word in query_lower for word in ["stats", "statistics", "average", "total", "how many", "how much"]):
        return "stats"
    
    return "general"


# CLI for testing
if __name__ == "__main__":
    # Test the prompt builder
    from src.retrieval.vector_store import SearchResult
    
    # Create mock results
    mock_results = [
        SearchResult(
            chunk_id="test_1",
            text="Patrick Mahomes, QB for the Kansas City Chiefs (KC) - 2023 NFL Season Statistics\nPassing: 4183 yards, 27 touchdowns, 14 interceptions",
            metadata={"chunk_type": "player_season", "player_name": "Patrick Mahomes", "team": "KC", "season": 2023},
            score=0.85,
        ),
        SearchResult(
            chunk_id="test_2",
            text="2023 NFL Wild Card Playoff Round: Miami Dolphins (MIA) at Kansas City Chiefs (KC)\nWeather conditions were extremely cold (-3°F, freezing conditions)",
            metadata={"chunk_type": "game_summary", "home_team": "KC", "away_team": "MIA", "season": 2023, "week": 19, "is_playoff": True},
            score=0.75,
        ),
    ]
    
    builder = RAGPromptBuilder()
    
    print("=" * 60)
    print("RAG Prompt Builder Test")
    print("=" * 60)
    
    query = "How did Patrick Mahomes perform in the cold playoff game against the Dolphins?"
    
    system_prompt, user_prompt = builder.build_prompt(query, mock_results)
    
    print("\n--- SYSTEM PROMPT ---")
    print(system_prompt[:500] + "...")
    
    print("\n--- USER PROMPT ---")
    print(user_prompt)
    
    print("\n--- QUERY TYPE ---")
    print(f"Detected type: {detect_query_type(query)}")