"""
NFL Stats Agent - Orchestrates tools to answer questions.

This module implements a ReAct-style (Reason + Act) agent that:
1. Receives a natural language question about NFL statistics
2. Decides which tools to use (SQL, player lookup, rankings, etc.)
3. Executes tools and observes results
4. Synthesizes a final answer from the tool outputs

The agent runs in a loop, calling tools until it has enough information
to answer, or until it hits the maximum iteration limit.
"""

import json
import logging
import re
import time
from typing import Optional
from dataclasses import dataclass, field

from src.rag.llm import OllamaLLM
from src.config import AGENT_MODEL
from src.agent.tools import (
    get_all_tools,
    get_tools_description,
    ToolResult,
)

# Configure logging for this module
logger = logging.getLogger(__name__)


# System prompt that instructs the LLM how to use tools
# Note: {current_year} and {current_nfl_season} are filled in dynamically
AGENT_SYSTEM_PROMPT = """You are an expert NFL statistics analyst with access to a comprehensive database of NFL data from 2014-2025.

IMPORTANT - Current Date Context:
- Today's date is in {current_year}
- The most recent completed NFL season is {current_nfl_season}
- When users say "this year", "this season", or "current season", use season={current_nfl_season}
- The {current_nfl_season} season data is complete

You have access to the following tools:

{tools_description}

## How to Use Tools

To use a tool, respond with a JSON block in this EXACT format:
```json
{{
    "tool": "tool_name",
    "arguments": {{
        "arg1": "value1",
        "arg2": "value2"
    }}
}}
```

## Tool Selection Guidelines

1. **For statistics questions** (averages, totals, records, comparisons):
   - Use `sql_query` for complex queries
   - Use `player_stats` for simple "how did X do against Y" questions

2. **For rankings - BEST performers** (top players, leaders, "who led the league"):
   - Use `rankings` tool with order="desc" (default)
   - Example: `rankings("passing_yards", {current_nfl_season}, position="QB", limit=10)`

3. **For rankings - WORST performers** (bottom players, "worst quarterback"):
   - Use `rankings` tool with order="asc" and min_games >= 10
   - Example: `rankings("passing_yards", {current_nfl_season}, position="QB", limit=10, order="asc", min_games=10)`
   - IMPORTANT: Always set min_games=10 or higher for "worst" queries to get meaningful results

4. **For calculations** (percentages, averages of results):
   - Use `calculator` after getting raw numbers from other tools

5. **For narrative/context** ("tell me about", "describe", famous games):
   - Use `semantic_search` tool

6. **For news and opinions** ("latest news", "what are people saying", rumors, analysis):
   - Use `news_search` tool
   - Filter by source: "espn", "nfl.com", "reddit"
   - Filter by team abbreviation: KC, BUF, SF, etc.

## Common Query Patterns

- "Who led the league in X?" → Use `rankings` with order="desc"
- "Who was the worst at X?" → Use `rankings` with order="asc", min_games=10
- "What are X's stats against Y?" → Use `player_stats` with opponent filter
- "How many X did Y have?" → Use `sql_query` with SUM() and GROUP BY

## Important Notes

- Always use tools to get data - NEVER make up statistics
- Player names: Use full names like "Patrick Mahomes", not just "Mahomes"
- Team abbreviations: KC, BUF, SF, DAL, etc.
- Season types: 'REG' for regular season, 'POST' for playoffs
- After getting tool results, provide a clear, conversational answer with specific numbers
- If a tool returns an error or no results, try a different approach

## Response Format

CRITICAL: After getting tool results, you MUST provide a final answer in natural language.
- Include specific numbers from the tool results
- DO NOT call more tools if you already have the answer
- DO NOT include any JSON in your final answer
- Just write a clear sentence answering the question

Example flow:
1. User asks: "Who led passing yards this year?"
2. You call rankings tool with season={current_nfl_season} → get results
3. You respond with a clear answer including the player name, team, and stat value

IMPORTANT: If you have data from a tool, USE IT to answer. Don't keep searching for more data.
"""


@dataclass
class AgentResponse:
    """
    Response from the agent containing the answer and metadata.

    Attributes:
        answer: The natural language answer to the user's question
        tool_calls: List of tools called with their arguments and results
        thinking: High-level trace of the agent's reasoning process
        total_time_ms: Total time taken to generate the response
        iterations: Number of ReAct loop iterations used
    """
    answer: str
    tool_calls: list = field(default_factory=list)
    thinking: list = field(default_factory=list)
    total_time_ms: float = 0.0
    iterations: int = 0


class NFLStatsAgent:
    """
    Agent that uses tools to answer NFL statistics questions.

    Uses a ReAct-style reasoning loop where the LLM decides which tools
    to use and synthesizes the results into a final answer.

    The agent has access to:
    - sql_query: Execute SQL against the NFL database
    - player_stats: Quick lookup for player statistics
    - rankings: Get leaderboards for specific stats
    - calculator: Perform math operations
    - semantic_search: Search narrative content
    - news_search: Search news from ESPN, NFL.com, Reddit

    Example:
        agent = NFLStatsAgent()
        response = agent.run("What's Mahomes' record against the Bills in the playoffs?")
        print(response.answer)
    """

    # Maximum number of tool calls before forcing an answer
    # Prevents infinite loops if the LLM keeps calling tools
    # Reduced from 6 to 4 to encourage faster answers
    MAX_ITERATIONS = 4

    def __init__(self, model: Optional[str] = None, timeout: int = 180):
        """
        Initialize the agent.

        Args:
            model: Ollama model to use (default: from config)
            timeout: Request timeout in seconds for LLM calls
        """
        from datetime import datetime

        self.model = model or AGENT_MODEL
        self.llm = OllamaLLM(model=self.model, timeout=timeout)

        # Build a dictionary of available tools for quick lookup
        self.tools = {tool.name: tool for tool in get_all_tools()}

        # Determine current year and NFL season
        # NFL season spans two calendar years (e.g., 2025 season runs Sep 2025 - Feb 2026)
        # If we're in Jan-Aug, the "current" NFL season is the previous year
        current_year = datetime.now().year
        current_month = datetime.now().month
        if current_month <= 8:  # Jan-Aug: previous year's season just ended
            current_nfl_season = current_year - 1
        else:  # Sep-Dec: current year's season is ongoing
            current_nfl_season = current_year

        # Inject tool descriptions and date context into the system prompt
        self.system_prompt = AGENT_SYSTEM_PROMPT.format(
            tools_description=get_tools_description(),
            current_year=current_year,
            current_nfl_season=current_nfl_season,
        )

        logger.info(f"NFLStatsAgent initialized with model={self.model}, season={current_nfl_season}, tools={list(self.tools.keys())}")

    def _parse_tool_call(self, response: str) -> Optional[dict]:
        """
        Extract a tool call from the LLM's response text.

        The LLM is instructed to format tool calls as JSON blocks.
        This method tries multiple parsing strategies:
        1. Look for ```json ... ``` code blocks
        2. Find raw JSON objects with "tool" key

        Args:
            response: The raw text response from the LLM

        Returns:
            Parsed tool call dict with "tool" and "arguments" keys,
            or None if no valid tool call found
        """
        # Strategy 1: Look for fenced JSON code block
        json_match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
        if json_match:
            try:
                parsed = json.loads(json_match.group(1))
                logger.debug(f"Parsed tool call from code block: {parsed.get('tool')}")
                return parsed
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse JSON from code block: {e}")

        # Strategy 2: Find raw JSON object in response
        try:
            start = response.find('{')
            if start == -1:
                return None

            # Find matching closing brace by tracking depth
            depth = 0
            end = start
            for i, char in enumerate(response[start:], start):
                if char == '{':
                    depth += 1
                elif char == '}':
                    depth -= 1
                    if depth == 0:
                        end = i + 1
                        break

            if end > start:
                json_str = response[start:end]
                parsed = json.loads(json_str)
                # Validate it's actually a tool call
                if "tool" in parsed:
                    logger.debug(f"Parsed tool call from raw JSON: {parsed.get('tool')}")
                    return parsed
        except (json.JSONDecodeError, ValueError) as e:
            logger.debug(f"No valid JSON tool call found: {e}")

        return None

    def _execute_tool(self, tool_call: dict) -> ToolResult:
        """
        Execute a tool call and return the result.

        Routes the call to the appropriate tool based on the tool name
        and passes the arguments.

        Args:
            tool_call: Dict with "tool" name and "arguments" dict

        Returns:
            ToolResult with success status, data, and any error message
        """
        tool_name = tool_call.get("tool")
        arguments = tool_call.get("arguments", {})

        logger.info(f"Executing tool: {tool_name} with args: {arguments}")

        # Check if tool exists
        if tool_name not in self.tools:
            logger.error(f"Unknown tool requested: {tool_name}")
            return ToolResult(
                success=False,
                data=None,
                error=f"Unknown tool: {tool_name}. Available: {list(self.tools.keys())}"
            )

        tool = self.tools[tool_name]

        try:
            # Route to the appropriate tool method
            # Each tool has different argument signatures
            if tool_name == "sql_query":
                # Accept both "sql" and "query" as the SQL argument
                sql = arguments.get("sql") or arguments.get("query") or ""
                result = tool.execute(sql)

            elif tool_name == "player_stats":
                result = tool.execute(
                    player_name=arguments.get("player_name", ""),
                    opponent=arguments.get("opponent"),
                    season=arguments.get("season"),
                    season_type=arguments.get("season_type"),
                )

            elif tool_name == "calculator":
                result = tool.execute(
                    operation=arguments.get("operation", ""),
                    values=arguments.get("values"),
                )

            elif tool_name == "semantic_search":
                result = tool.execute(
                    query=arguments.get("query", ""),
                    num_results=arguments.get("num_results", 5),
                )

            elif tool_name == "rankings":
                result = tool.execute(
                    stat=arguments.get("stat", ""),
                    season=arguments.get("season", 2024),
                    position=arguments.get("position"),
                    limit=arguments.get("limit", 10),
                    season_type=arguments.get("season_type", "REG"),
                    order=arguments.get("order", "desc"),
                    min_games=arguments.get("min_games", 1),
                )

            elif tool_name == "news_search":
                result = tool.execute(
                    query=arguments.get("query", ""),
                    source=arguments.get("source"),
                    team=arguments.get("team"),
                    num_results=arguments.get("num_results", 5),
                )

            else:
                logger.error(f"Tool '{tool_name}' exists but execution not implemented")
                return ToolResult(
                    success=False,
                    data=None,
                    error=f"Tool '{tool_name}' execution not implemented"
                )

            logger.info(f"Tool {tool_name} completed: success={result.success}")
            return result

        except Exception as e:
            logger.exception(f"Tool {tool_name} raised exception: {e}")
            return ToolResult(success=False, data=None, error=str(e))

    def run(self, question: str, verbose: bool = False) -> AgentResponse:
        """
        Run the agent to answer a question.

        This is the main entry point. It runs a ReAct loop:
        1. Send question to LLM
        2. If LLM returns a tool call, execute it and feed result back
        3. Repeat until LLM returns a final answer or max iterations reached

        Args:
            question: The user's natural language question
            verbose: If True, print intermediate steps (useful for debugging)

        Returns:
            AgentResponse with the answer, tool calls made, and metadata
        """
        logger.info(f"Agent processing question: {question[:100]}...")
        start_time = time.time()

        tool_calls = []  # Track all tool calls made
        thinking = []    # High-level reasoning trace

        # Initialize conversation with system prompt and user question
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": question},
        ]

        # ReAct loop: iterate until we get an answer or hit max iterations
        for iteration in range(self.MAX_ITERATIONS):
            logger.debug(f"Starting iteration {iteration + 1}/{self.MAX_ITERATIONS}")

            if verbose:
                print(f"\n{'='*60}")
                print(f"Iteration {iteration + 1}")
                print("="*60)

            # Get LLM response
            try:
                llm_response = self.llm.chat(messages, temperature=0.2)
                response_text = llm_response.content
            except Exception as e:
                logger.exception(f"LLM communication error: {e}")
                return AgentResponse(
                    answer=f"Error communicating with LLM: {e}",
                    tool_calls=tool_calls,
                    thinking=thinking,
                    total_time_ms=(time.time() - start_time) * 1000,
                    iterations=iteration + 1,
                )

            if verbose:
                print(f"\nLLM Response:\n{response_text[:800]}{'...' if len(response_text) > 800 else ''}")

            # Check if the response contains a tool call
            tool_call = self._parse_tool_call(response_text)

            if tool_call:
                # LLM wants to use a tool
                tool_name = tool_call.get("tool")
                tool_args = tool_call.get("arguments", {})

                if verbose:
                    print(f"\nTool Call: {tool_name}")
                    print(f"Arguments: {json.dumps(tool_args, indent=2)}")

                # Execute the tool
                result = self._execute_tool(tool_call)

                if verbose:
                    result_preview = result.to_string()[:500]
                    print(f"\nTool Result:\n{result_preview}{'...' if len(result.to_string()) > 500 else ''}")

                # Record the tool call for the response
                tool_calls.append({
                    "tool": tool_name,
                    "arguments": tool_args,
                    "result": result.data if result.success else None,
                    "error": result.error if not result.success else None,
                    "success": result.success,
                })

                thinking.append(f"Used {tool_name}: {'success' if result.success else 'failed'}")

                # Add the exchange to conversation history for next iteration
                messages.append({"role": "assistant", "content": response_text})

                # Build a more directive prompt based on whether the tool succeeded
                if result.success and result.data:
                    followup = (
                        f"Tool result:\n{result.to_string()}\n\n"
                        "You now have data to answer the question. "
                        "Provide your final answer as a clear sentence using the numbers above. "
                        "DO NOT call another tool - just answer the question."
                    )
                else:
                    followup = (
                        f"Tool result:\n{result.to_string()}\n\n"
                        "The tool didn't return useful data. Try a different approach or tool."
                    )

                messages.append({"role": "user", "content": followup})

            else:
                # No tool call found - LLM is providing the final answer
                thinking.append("Generated final answer")
                elapsed_ms = (time.time() - start_time) * 1000

                logger.info(f"Agent completed in {elapsed_ms:.0f}ms with {len(tool_calls)} tool calls")

                return AgentResponse(
                    answer=response_text,
                    tool_calls=tool_calls,
                    thinking=thinking,
                    total_time_ms=elapsed_ms,
                    iterations=iteration + 1,
                )

        # Max iterations reached without a final answer
        # This can happen if the LLM keeps calling tools in a loop
        elapsed_ms = (time.time() - start_time) * 1000
        logger.warning(f"Agent hit max iterations ({self.MAX_ITERATIONS}) without final answer")

        # Build a fallback answer from the tool results
        # Try to extract meaningful data from the most useful tool call
        final_answer = self._build_fallback_answer(tool_calls)

        return AgentResponse(
            answer=final_answer,
            tool_calls=tool_calls,
            thinking=thinking,
            total_time_ms=elapsed_ms,
            iterations=self.MAX_ITERATIONS,
        )

    def _build_fallback_answer(self, tool_calls: list) -> str:
        """
        Build a reasonable answer from tool call results when max iterations is hit.

        Tries to extract the most useful information from rankings or player_stats
        tool calls rather than dumping raw data.

        Args:
            tool_calls: List of tool call records with results

        Returns:
            A human-readable answer string
        """
        if not tool_calls:
            return "I couldn't find relevant data to answer this question."

        # Look for successful tool calls with data
        for tc in tool_calls:
            if not tc.get("success") or not tc.get("result"):
                continue

            tool = tc.get("tool")
            result = tc.get("result")

            # Handle rankings results - extract the leader's stats
            if tool == "rankings" and isinstance(result, list) and len(result) > 0:
                first = result[0]
                player = first.get("player", "Unknown")
                # Find the stat value (column name varies based on the stat)
                stat_value = None
                stat_name = ""
                for key, value in first.items():
                    if key.startswith("total_") and isinstance(value, (int, float)):
                        stat_value = value
                        stat_name = key.replace("total_", "").replace("_", " ")
                        break

                if stat_value is not None:
                    games = first.get("games", "")
                    games_str = f" in {games} games" if games else ""
                    return f"Based on the data, {player} led with {stat_value:,} {stat_name}{games_str}."

            # Handle player_stats results - summarize the player's performance
            if tool == "player_stats" and isinstance(result, dict):
                summary = result.get("summary", {})
                if summary:
                    player = summary.get("player", "The player")
                    games = summary.get("games_played", 0)
                    pass_yds = summary.get("total_passing_yards", 0)
                    pass_tds = summary.get("total_passing_tds", 0)

                    if pass_yds > 0:
                        return f"{player} had {pass_yds:,} passing yards and {pass_tds} touchdowns in {games} games."

            # Handle SQL query results - format as key-value pairs
            if tool == "sql_query" and isinstance(result, list) and len(result) > 0:
                first = result[0]
                parts = []
                for key, value in first.items():
                    if value is not None:
                        parts.append(f"{key}: {value}")
                if parts:
                    return "Based on the data: " + ", ".join(parts[:5])

        # If no structured data found, return a generic message
        return "I found some data but couldn't determine a clear answer. Try rephrasing your question or being more specific."

    def is_available(self) -> bool:
        """Check if the agent's LLM is available and the model exists."""
        available = self.llm.is_available() and self.llm.model_exists()
        logger.debug(f"Agent availability check: {available}")
        return available


# =============================================================================
# CLI for testing the agent directly
# =============================================================================

if __name__ == "__main__":
    import argparse

    # Set up logging for CLI usage
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    parser = argparse.ArgumentParser(description="NFL Stats Agent")
    parser.add_argument("question", nargs="?", help="Question to ask")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show thinking process")
    parser.add_argument("--interactive", "-i", action="store_true", help="Interactive mode")
    parser.add_argument("--model", "-m", type=str, help="Ollama model to use")
    parser.add_argument("--debug", "-d", action="store_true", help="Enable debug logging")

    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    agent = NFLStatsAgent(model=args.model) if args.model else NFLStatsAgent()

    # Check availability before proceeding
    if not agent.llm.is_available():
        print("Error: Ollama is not running")
        print("Start it with: ollama serve")
        exit(1)

    if not agent.llm.model_exists():
        print(f"Error: Model '{agent.model}' not found")
        print(f"Download it with: ollama pull {agent.model}")
        exit(1)

    print(f"Agent ready (model: {agent.model})")

    if args.interactive:
        # Interactive REPL mode
        print("\nNFL Stats Agent - Interactive Mode")
        print("=" * 60)
        print("Ask questions about NFL statistics (2014-2025)")
        print("Type 'quit' to exit")
        print("=" * 60)

        while True:
            try:
                question = input("\nYour question: ").strip()
            except (KeyboardInterrupt, EOFError):
                print("\nGoodbye!")
                break

            if question.lower() in ("quit", "exit", "q"):
                print("Goodbye!")
                break

            if not question:
                continue

            print("\nThinking...")
            response = agent.run(question, verbose=args.verbose)

            print("\n" + "=" * 60)
            print("Answer:")
            print(response.answer)
            print("=" * 60)
            print(f"Tools used: {[tc['tool'] for tc in response.tool_calls]}")
            print(f"Iterations: {response.iterations}")
            print(f"Time: {response.total_time_ms:.0f}ms")

    elif args.question:
        # Single question mode
        response = agent.run(args.question, verbose=args.verbose)

        print("\n" + "=" * 60)
        print("Answer:")
        print(response.answer)
        print("=" * 60)
        print(f"\nTools used: {[tc['tool'] for tc in response.tool_calls]}")
        print(f"Iterations: {response.iterations}")
        print(f"Time: {response.total_time_ms:.0f}ms")

    else:
        parser.print_help()
