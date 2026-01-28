"""
NFL RAG Pipeline - Main orchestration of retrieval and generation.

This module ties together:
1. Query understanding
2. Retrieval from ChromaDB
3. Context building
4. LLM generation
5. Response formatting
"""

import time
from typing import Optional, Generator
from dataclasses import dataclass, field

from src.config import DEBUG
from src.retrieval.vector_store import NFLVectorStore, SearchResult, build_metadata_filter
from src.rag.llm import OllamaLLM, LLMResponse
from src.rag.prompts import RAGPromptBuilder, detect_query_type


@dataclass
class RAGResponse:
    """Complete response from the RAG pipeline."""
    answer: str
    sources: list[SearchResult]
    query: str
    retrieval_time_ms: float
    generation_time_ms: float
    total_time_ms: float
    model: str
    num_sources: int
    
    def format_sources(self) -> str:
        """Format sources for display."""
        if not self.sources:
            return "No sources used."
        
        lines = ["Sources:"]
        for i, source in enumerate(self.sources, 1):
            meta = source.metadata
            chunk_type = meta.get("chunk_type", "")
            
            if chunk_type == "game_summary":
                desc = f"{meta.get('season')} Week {meta.get('week')}: {meta.get('away_team')} @ {meta.get('home_team')}"
            elif chunk_type == "player_game":
                desc = f"{meta.get('player_name')} - {meta.get('season')} Week {meta.get('week')}"
            elif chunk_type == "player_season":
                desc = f"{meta.get('player_name')} - {meta.get('season')} Season"
            elif chunk_type == "player_bio":
                desc = f"{meta.get('player_name')} - Bio"
            else:
                desc = chunk_type
            
            lines.append(f"  {i}. {desc} (relevance: {source.score:.2f})")
        
        return "\n".join(lines)
    
    def __str__(self) -> str:
        return f"{self.answer}\n\n{self.format_sources()}"


@dataclass 
class ConversationTurn:
    """A single turn in the conversation."""
    query: str
    response: RAGResponse
    timestamp: float = field(default_factory=time.time)


class NFLRAGPipeline:
    """
    Main RAG pipeline for NFL question answering.
    
    Usage:
        pipeline = NFLRAGPipeline()
        response = pipeline.query("How did Mahomes play in the cold playoff game?")
        print(response.answer)
    """
    
    def __init__(
        self,
        vector_store: Optional[NFLVectorStore] = None,
        llm: Optional[OllamaLLM] = None,
        prompt_builder: Optional[RAGPromptBuilder] = None,
        default_num_results: int = 5,
        default_temperature: float = 0.7,
    ):
        """
        Initialize the RAG pipeline.
        
        Args:
            vector_store: Vector store instance (creates default if not provided)
            llm: LLM instance (creates default if not provided)
            prompt_builder: Prompt builder instance
            default_num_results: Default number of results to retrieve
            default_temperature: Default LLM temperature
        """
        self.vector_store = vector_store or NFLVectorStore()
        self.llm = llm or OllamaLLM()
        self.prompt_builder = prompt_builder or RAGPromptBuilder()
        self.default_num_results = default_num_results
        self.default_temperature = default_temperature
        
        # Conversation history for multi-turn
        self.conversation_history: list[ConversationTurn] = []
        
        if DEBUG:
            print("NFL RAG Pipeline initialized")
            print(f"  Vector store: {self.vector_store.count()} chunks")
            print(f"  LLM model: {self.llm.model}")
    
    def _enhance_query(self, query: str) -> str:
        """
        Enhance the query for better semantic search results.
        
        Rewrites queries to be more explicit and match chunk text better.
        """
        query_lower = query.lower()
        
        # Player name mapping for common names
        player_names = {
            "mahomes": "Patrick Mahomes",
            "mahome's": "Patrick Mahomes",
            "kelce": "Travis Kelce", 
            "allen": "Josh Allen",
            "burrow": "Joe Burrow",
            "jackson": "Lamar Jackson",
            "hurts": "Jalen Hurts",
            "herbert": "Justin Herbert",
            "hill": "Tyreek Hill",
            "chase": "Ja'Marr Chase",
            "jefferson": "Justin Jefferson",
            "henry": "Derrick Henry",
            "taylor": "Jonathan Taylor",
            "chubb": "Nick Chubb",
            "diggs": "Stefon Diggs",
            "adams": "Davante Adams",
            "kupp": "Cooper Kupp",
            "lamb": "CeeDee Lamb",
            "waddle": "Jaylen Waddle",
            "kelce's": "Travis Kelce",
            "allen's": "Josh Allen",
        }
        
        # Team name mapping
        team_names = {
            "bills": "Buffalo Bills",
            "chiefs": "Kansas City Chiefs",
            "dolphins": "Miami Dolphins",
            "eagles": "Philadelphia Eagles",
            "cowboys": "Dallas Cowboys",
            "49ers": "San Francisco 49ers",
            "niners": "San Francisco 49ers",
            "packers": "Green Bay Packers",
            "ravens": "Baltimore Ravens",
            "bengals": "Cincinnati Bengals",
            "lions": "Detroit Lions",
            "bears": "Chicago Bears",
            "vikings": "Minnesota Vikings",
            "saints": "New Orleans Saints",
        }
        
        enhanced = query
        
        # Expand player names
        for short, full in player_names.items():
            if short in query_lower:
                # Replace with full name for better matching
                enhanced = enhanced + f" {full}"
                break
        
        # Check for "against [team]" or "vs [team]" patterns
        for team_short, team_full in team_names.items():
            if team_short in query_lower:
                # If asking about stats against a team, make it explicit
                if any(word in query_lower for word in ["against", "vs", "versus", "playing"]):
                    enhanced = enhanced + f" playing against {team_full} opponent"
                break
        
        return enhanced

    def _extract_filters_from_query(self, query: str) -> dict:
        """
        Extract metadata filters from the query.
        
        This is a simple heuristic-based extraction.
        Could be enhanced with NER or LLM-based extraction.
        
        Args:
            query: User's query
            
        Returns:
            Filter dict for ChromaDB
        """
        filters = {}
        query_lower = query.lower()
        
        # Player name detection - if a specific player is mentioned, filter by their name
        player_names = {
            "mahomes": "Patrick Mahomes",
            "mahome's": "Patrick Mahomes",
            "kelce": "Travis Kelce",
            "kelce's": "Travis Kelce", 
            "josh allen": "Josh Allen",
            "allen's": "Josh Allen",
            "burrow": "Joe Burrow",
            "lamar": "Lamar Jackson",
            "lamar jackson": "Lamar Jackson",
            "hurts": "Jalen Hurts",
            "herbert": "Justin Herbert",
            "tyreek": "Tyreek Hill",
            "tyreek hill": "Tyreek Hill",
            "ja'marr chase": "Ja'Marr Chase",
            "chase": "Ja'Marr Chase",
            "justin jefferson": "Justin Jefferson",
            "jefferson": "Justin Jefferson",
            "derrick henry": "Derrick Henry",
            "henry": "Derrick Henry",
            "chubb": "Nick Chubb",
            "diggs": "Stefon Diggs",
            "davante adams": "Davante Adams",
            "davante": "Davante Adams",
            "kupp": "Cooper Kupp",
            "ceedee lamb": "CeeDee Lamb",
            "ceedee": "CeeDee Lamb",
            "lamb": "CeeDee Lamb",
            "waddle": "Jaylen Waddle",
            "tua": "Tua Tagovailoa",
            "tagovailoa": "Tua Tagovailoa",
            "jalen waddle": "Jaylen Waddle",
            "isiah pacheco": "Isiah Pacheco",
            "pacheco": "Isiah Pacheco",
            "rashee rice": "Rashee Rice",
        }
        
        # Check for player names and add to filter
        detected_player = None
        for pattern, full_name in player_names.items():
            if pattern in query_lower:
                detected_player = full_name
                break
        
        if detected_player:
            filters["player_name"] = detected_player
        
        # Team detection (only use for opponent context, not primary filter when player is specified)
        team_keywords = {
            "chiefs": "KC",
            "kansas city": "KC",
            "dolphins": "MIA",
            "miami": "MIA",
            "bills": "BUF",
            "buffalo": "BUF",
            "eagles": "PHI",
            "philadelphia": "PHI",
            "49ers": "SF",
            "san francisco": "SF",
            "cowboys": "DAL",
            "dallas": "DAL",
            "patriots": "NE",
            "new england": "NE",
            "packers": "GB",
            "green bay": "GB",
            "ravens": "BAL",
            "baltimore": "BAL",
            "bengals": "CIN",
            "cincinnati": "CIN",
            "lions": "DET",
            "detroit": "DET",
            "bears": "CHI",
            "chicago": "CHI",
            "broncos": "DEN",
            "denver": "DEN",
            "raiders": "LV",
            "las vegas": "LV",
            "chargers": "LAC",
            "rams": "LA",
            "seahawks": "SEA",
            "seattle": "SEA",
            "cardinals": "ARI",
            "arizona": "ARI",
            "falcons": "ATL",
            "atlanta": "ATL",
            "panthers": "CAR",
            "carolina": "CAR",
            "browns": "CLE",
            "cleveland": "CLE",
            "texans": "HOU",
            "houston": "HOU",
            "colts": "IND",
            "indianapolis": "IND",
            "jaguars": "JAX",
            "jacksonville": "JAX",
            "titans": "TEN",
            "tennessee": "TEN",
            "vikings": "MIN",
            "minnesota": "MIN",
            "saints": "NO",
            "new orleans": "NO",
            "giants": "NYG",
            "jets": "NYJ",
            "steelers": "PIT",
            "pittsburgh": "PIT",
            "buccaneers": "TB",
            "tampa": "TB",
            "commanders": "WAS",
            "washington": "WAS",
        }
        
        found_teams = []
        for keyword, abbr in team_keywords.items():
            if keyword in query_lower:
                if abbr not in found_teams:
                    found_teams.append(abbr)
        
        # Position detection
        position_keywords = {
            "quarterback": "QB",
            "qb": "QB",
            "running back": "RB",
            "rb": "RB",
            "wide receiver": "WR",
            "wr": "WR",
            "tight end": "TE",
            "te": "TE",
        }
        
        for keyword, pos in position_keywords.items():
            if keyword in query_lower:
                filters["position"] = pos
                break
        
        # Game type detection - use game_type field which exists on player_game chunks
        # game_type values: REG, POST, WC, DIV, CON, SB
        if any(word in query_lower for word in ["playoff", "postseason"]):
            # Don't use is_playoff as it may not exist on player_game chunks
            # Instead, we'll handle this in the query enhancement
            # For now, just note that we want playoff games
            filters["game_type"] = {"$ne": "REG"}  # Not regular season
        elif "wild card" in query_lower:
            filters["game_type"] = "WC"
        elif "divisional" in query_lower:
            filters["game_type"] = "DIV"
        elif "conference championship" in query_lower or "afc championship" in query_lower or "nfc championship" in query_lower:
            filters["game_type"] = "CON"
        elif "super bowl" in query_lower:
            filters["game_type"] = "SB"
        
        # Weather detection - only apply if specifically asking about weather/conditions
        # Don't apply just because "cold" appears (could be asking about player performance)
        weather_focus = any(word in query_lower for word in ["weather", "conditions", "temperature", "coldest", "hottest", "warmest"])
        if weather_focus:
            if any(word in query_lower for word in ["cold", "freezing", "frozen", "ice", "snow", "coldest"]):
                filters["temperature_category"] = "freezing"
        
        # Detect if query is about a specific player
        # Common player name patterns - if we detect a player name, DON'T restrict chunk_type
        player_indicators = ["mahomes", "kelce", "allen", "burrow", "jackson", "herbert", 
                           "hurts", "hill", "chase", "jefferson", "diggs", "adams",
                           "henry", "chubb", "taylor", "ekeler", "stats", "performance",
                           "how did", "how many", "threw", "rushed", "caught", "yards"]
        
        is_player_query = any(indicator in query_lower for indicator in player_indicators)
        
        # Chunk type hints - be more careful about when to apply these
        # Don't apply chunk_type filter if it seems like a player-focused query
        if not is_player_query:
            if any(word in query_lower for word in ["final score", "who won", "who beat", "result of the game"]):
                filters["chunk_type"] = "game_summary"
            elif any(word in query_lower for word in ["season stats", "season total", "full season", "yearly"]):
                filters["chunk_type"] = "player_season"
            elif any(word in query_lower for word in ["profile", "college", "drafted", "height", "weight", "age", "born"]):
                filters["chunk_type"] = "player_bio"
        
        return filters
    
    def retrieve(
        self,
        query: str,
        num_results: Optional[int] = None,
        filters: Optional[dict] = None,
        auto_filter: bool = True,
    ) -> list[SearchResult]:
        """
        Retrieve relevant chunks for a query.
        
        Args:
            query: User's question
            num_results: Number of results to retrieve
            filters: Manual metadata filters
            auto_filter: Whether to auto-extract filters from query
            
        Returns:
            List of SearchResults
        """
        n = num_results or self.default_num_results
        
        # Build filters
        where = filters
        if auto_filter and not filters:
            extracted = self._extract_filters_from_query(query)
            if extracted:
                where = build_metadata_filter(**extracted)
                if DEBUG:
                    print(f"  Auto-extracted filters: {extracted}")
        
        # Enhance query for better semantic matching
        enhanced_query = self._enhance_query(query)
        if DEBUG and enhanced_query != query:
            print(f"  Enhanced query: {enhanced_query}")
        
        # Retrieve
        results = self.vector_store.search(
            query=enhanced_query,
            n_results=n,
            where=where,
        )
        
        return results
    
    def query(
        self,
        query: str,
        num_results: Optional[int] = None,
        filters: Optional[dict] = None,
        temperature: Optional[float] = None,
        auto_filter: bool = True,
        stream: bool = False,
    ) -> RAGResponse:
        """
        Execute a RAG query.
        
        Args:
            query: User's question
            num_results: Number of chunks to retrieve
            filters: Metadata filters for retrieval
            temperature: LLM temperature
            auto_filter: Auto-extract filters from query
            stream: Whether to stream the response (not implemented yet)
            
        Returns:
            RAGResponse with answer and metadata
        """
        start_time = time.time()
        
        # Step 1: Retrieve relevant chunks
        retrieval_start = time.time()
        results = self.retrieve(
            query=query,
            num_results=num_results,
            filters=filters,
            auto_filter=auto_filter,
        )
        retrieval_time = (time.time() - retrieval_start) * 1000
        
        if DEBUG:
            print(f"  Retrieved {len(results)} chunks in {retrieval_time:.0f}ms")
        
        # Step 2: Build prompt
        system_prompt, user_prompt = self.prompt_builder.build_prompt(
            query=query,
            results=results,
            max_results=num_results or self.default_num_results,
        )
        
        # Step 3: Generate response
        generation_start = time.time()
        
        temp = temperature or self.default_temperature
        
        try:
            llm_response = self.llm.generate(
                prompt=user_prompt,
                system_prompt=system_prompt,
                temperature=temp,
            )
            answer = llm_response.content
        except Exception as e:
            answer = f"Error generating response: {e}"
        
        generation_time = (time.time() - generation_start) * 1000
        total_time = (time.time() - start_time) * 1000
        
        if DEBUG:
            print(f"  Generated response in {generation_time:.0f}ms")
        
        # Build response
        response = RAGResponse(
            answer=answer,
            sources=results,
            query=query,
            retrieval_time_ms=retrieval_time,
            generation_time_ms=generation_time,
            total_time_ms=total_time,
            model=self.llm.model,
            num_sources=len(results),
        )
        
        # Store in conversation history
        self.conversation_history.append(ConversationTurn(
            query=query,
            response=response,
        ))
        
        return response
    
    def query_stream(
        self,
        query: str,
        num_results: Optional[int] = None,
        filters: Optional[dict] = None,
        temperature: Optional[float] = None,
    ) -> Generator[str, None, RAGResponse]:
        """
        Execute a streaming RAG query.
        
        Yields chunks of the response as they're generated.
        Returns the complete RAGResponse at the end.
        
        Args:
            query: User's question
            num_results: Number of chunks to retrieve
            filters: Metadata filters
            temperature: LLM temperature
            
        Yields:
            Chunks of generated text
            
        Returns:
            Complete RAGResponse
        """
        start_time = time.time()
        
        # Retrieve
        retrieval_start = time.time()
        results = self.retrieve(
            query=query,
            num_results=num_results,
            filters=filters,
        )
        retrieval_time = (time.time() - retrieval_start) * 1000
        
        # Build prompt
        system_prompt, user_prompt = self.prompt_builder.build_prompt(
            query=query,
            results=results,
        )
        
        # Stream generation
        generation_start = time.time()
        temp = temperature or self.default_temperature
        
        answer_parts = []
        for chunk in self.llm.generate_stream(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=temp,
        ):
            answer_parts.append(chunk)
            yield chunk
        
        generation_time = (time.time() - generation_start) * 1000
        total_time = (time.time() - start_time) * 1000
        
        answer = "".join(answer_parts)
        
        return RAGResponse(
            answer=answer,
            sources=results,
            query=query,
            retrieval_time_ms=retrieval_time,
            generation_time_ms=generation_time,
            total_time_ms=total_time,
            model=self.llm.model,
            num_sources=len(results),
        )
    
    def clear_history(self):
        """Clear conversation history."""
        self.conversation_history = []
    
    def get_history(self) -> list[ConversationTurn]:
        """Get conversation history."""
        return self.conversation_history
    
    def health_check(self) -> dict:
        """
        Check the health of all pipeline components.
        
        Returns:
            Dict with health status of each component
        """
        health = {
            "vector_store": False,
            "llm": False,
            "chunk_count": 0,
            "llm_model": self.llm.model,
        }
        
        # Check vector store
        try:
            health["chunk_count"] = self.vector_store.count()
            health["vector_store"] = health["chunk_count"] > 0
        except Exception as e:
            health["vector_store_error"] = str(e)
        
        # Check LLM
        try:
            health["llm"] = self.llm.is_available()
            if health["llm"]:
                health["llm_model_exists"] = self.llm.model_exists()
        except Exception as e:
            health["llm_error"] = str(e)
        
        health["healthy"] = health["vector_store"] and health["llm"]
        
        return health


# Interactive CLI
def interactive_mode(pipeline: NFLRAGPipeline):
    """Run an interactive Q&A session."""
    print("\n" + "=" * 60)
    print("NFL RAG Assistant - Interactive Mode")
    print("=" * 60)
    print("Ask questions about NFL games, players, and statistics.")
    print("Type 'quit' or 'exit' to end the session.")
    print("Type 'clear' to clear conversation history.")
    print("=" * 60 + "\n")
    
    while True:
        try:
            query = input("\n📋 Your question: ").strip()
            
            if not query:
                continue
            
            if query.lower() in ("quit", "exit", "q"):
                print("\nGoodbye! 🏈")
                break
            
            if query.lower() == "clear":
                pipeline.clear_history()
                print("Conversation history cleared.")
                continue
            
            if query.lower() == "history":
                history = pipeline.get_history()
                if history:
                    print(f"\nConversation history ({len(history)} turns):")
                    for i, turn in enumerate(history, 1):
                        print(f"  {i}. {turn.query[:50]}...")
                else:
                    print("No conversation history.")
                continue
            
            print("\n🔍 Searching...", end="", flush=True)
            
            response = pipeline.query(query)
            
            print(f" Found {response.num_sources} relevant sources.")
            print("\n" + "-" * 60)
            print("🏈 Answer:\n")
            print(response.answer)
            print("\n" + "-" * 60)
            print(response.format_sources())
            print(f"\n⏱️ Time: {response.total_time_ms:.0f}ms (retrieval: {response.retrieval_time_ms:.0f}ms, generation: {response.generation_time_ms:.0f}ms)")
            
        except KeyboardInterrupt:
            print("\n\nGoodbye! 🏈")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")


# CLI entry point
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="NFL RAG Pipeline")
    parser.add_argument("--query", "-q", type=str, help="Single query to run")
    parser.add_argument("--interactive", "-i", action="store_true", help="Interactive mode")
    parser.add_argument("--health", action="store_true", help="Check pipeline health")
    parser.add_argument("--num-results", "-n", type=int, default=5, help="Number of results")
    parser.add_argument("--no-auto-filter", action="store_true", help="Disable auto-filtering")
    parser.add_argument("--model", type=str, help="Ollama model to use")
    parser.add_argument("--temperature", type=float, default=0.7, help="LLM temperature")
    
    args = parser.parse_args()
    
    # Initialize pipeline
    llm = OllamaLLM(model=args.model) if args.model else None
    pipeline = NFLRAGPipeline(llm=llm, default_temperature=args.temperature)
    
    if args.health:
        print("Checking pipeline health...")
        health = pipeline.health_check()
        print("\nHealth Status:")
        print("=" * 40)
        for key, value in health.items():
            status = "✓" if value == True else ("✗" if value == False else value)
            print(f"  {key}: {status}")
    
    elif args.interactive:
        # Check health first
        health = pipeline.health_check()
        if not health["healthy"]:
            print("⚠️  Warning: Pipeline not fully healthy")
            if not health["llm"]:
                print("   - Ollama not available. Make sure it's running: ollama serve")
            if not health["vector_store"]:
                print("   - Vector store empty. Run: python -m src.retrieval.indexer")
            print()
        
        interactive_mode(pipeline)
    
    elif args.query:
        response = pipeline.query(
            query=args.query,
            num_results=args.num_results,
            auto_filter=not args.no_auto_filter,
        )
        
        print("\n" + "=" * 60)
        print("Answer:")
        print("=" * 60)
        print(response.answer)
        print("\n" + "-" * 60)
        print(response.format_sources())
        print(f"\nTime: {response.total_time_ms:.0f}ms")
    
    else:
        parser.print_help()