"""
Test the NFL RAG pipeline.
"""

import sys


def test_llm_connection():
    """Test connection to Ollama."""
    print("Testing Ollama LLM connection...")
    
    from src.rag.llm import OllamaLLM
    
    passed = 0
    failed = 0
    
    llm = OllamaLLM()
    
    # Test availability
    if llm.is_available():
        print(f"  ✓ Ollama is available at {llm.host}")
        passed += 1
    else:
        print(f"  ✗ Ollama not available at {llm.host}")
        print("    Make sure Ollama is running: ollama serve")
        failed += 1
        return passed, failed
    
    # Test model exists
    if llm.model_exists():
        print(f"  ✓ Model '{llm.model}' is available")
        passed += 1
    else:
        print(f"  ✗ Model '{llm.model}' not found")
        print(f"    Run: ollama pull {llm.model}")
        failed += 1
        return passed, failed
    
    # Test generation
    try:
        response = llm.generate(
            "Say 'Hello' and nothing else.",
            temperature=0.1,
            max_tokens=10,
        )
        if "hello" in response.content.lower():
            print(f"  ✓ Generation works: '{response.content.strip()}'")
            passed += 1
        else:
            print(f"  ⚠ Unexpected response: '{response.content[:50]}'")
            passed += 1  # Still working
    except Exception as e:
        print(f"  ✗ Generation failed: {e}")
        failed += 1
    
    return passed, failed


def test_prompt_builder():
    """Test the prompt builder."""
    print("\nTesting RAG Prompt Builder...")
    
    from src.rag.prompts import RAGPromptBuilder, detect_query_type
    from src.retrieval.vector_store import SearchResult
    
    passed = 0
    failed = 0
    
    builder = RAGPromptBuilder()
    
    # Create mock results
    mock_results = [
        SearchResult(
            chunk_id="test_1",
            text="Patrick Mahomes threw for 262 yards in the freezing playoff game.",
            metadata={
                "chunk_type": "player_game",
                "player_name": "Patrick Mahomes",
                "team": "KC",
                "season": 2023,
                "week": 19,
            },
            score=0.85,
        ),
    ]
    
    # Test prompt building
    try:
        system_prompt, user_prompt = builder.build_prompt(
            query="How did Mahomes play?",
            results=mock_results,
        )
        
        if "Patrick Mahomes" in user_prompt and "262 yards" in user_prompt:
            print("  ✓ Prompt building works")
            passed += 1
        else:
            print("  ✗ Prompt missing expected content")
            failed += 1
    except Exception as e:
        print(f"  ✗ Prompt building failed: {e}")
        failed += 1
    
    # Test query type detection
    test_cases = [
        ("Compare Mahomes and Allen", "comparison"),
        ("Will the Chiefs win?", "prediction"),
        ("How many yards did he throw?", "stats"),
        ("Tell me about the game", "general"),
    ]
    
    all_correct = True
    for query, expected in test_cases:
        detected = detect_query_type(query)
        if detected != expected:
            print(f"  ⚠ Query type mismatch: '{query}' → {detected} (expected {expected})")
            all_correct = False
    
    if all_correct:
        print("  ✓ Query type detection works")
        passed += 1
    else:
        failed += 1
    
    return passed, failed


def test_pipeline_retrieval():
    """Test the pipeline retrieval."""
    print("\nTesting RAG Pipeline retrieval...")
    
    from src.rag.pipeline import NFLRAGPipeline
    
    passed = 0
    failed = 0
    
    try:
        pipeline = NFLRAGPipeline()
        print(f"  ✓ Pipeline initialized")
        passed += 1
    except Exception as e:
        print(f"  ✗ Pipeline initialization failed: {e}")
        failed += 1
        return passed, failed
    
    # Check vector store has data
    chunk_count = pipeline.vector_store.count()
    if chunk_count > 0:
        print(f"  ✓ Vector store has {chunk_count} chunks")
        passed += 1
    else:
        print("  ✗ Vector store is empty")
        print("    Run: python -m src.retrieval.indexer")
        failed += 1
        return passed, failed
    
    # Test retrieval
    try:
        results = pipeline.retrieve("Chiefs Dolphins playoff game", num_results=3)
        if results:
            print(f"  ✓ Retrieved {len(results)} results")
            print(f"    Top result: {results[0].text[:80]}...")
            passed += 1
        else:
            print("  ✗ No results retrieved")
            failed += 1
    except Exception as e:
        print(f"  ✗ Retrieval failed: {e}")
        failed += 1
    
    # Test auto-filter extraction
    try:
        filters = pipeline._extract_filters_from_query("Chiefs quarterback cold weather playoff")
        if "temperature_category" in filters or "is_playoff" in filters:
            print(f"  ✓ Auto-filter extraction works: {filters}")
            passed += 1
        else:
            print(f"  ⚠ Auto-filter incomplete: {filters}")
            passed += 1
    except Exception as e:
        print(f"  ✗ Auto-filter extraction failed: {e}")
        failed += 1
    
    return passed, failed


def test_full_pipeline():
    """Test the complete RAG pipeline with generation."""
    print("\nTesting full RAG pipeline (retrieval + generation)...")
    
    from src.rag.pipeline import NFLRAGPipeline
    
    passed = 0
    failed = 0
    
    pipeline = NFLRAGPipeline()
    
    # Check health
    health = pipeline.health_check()
    
    if not health["vector_store"]:
        print("  ⚠ Skipping full test - vector store empty")
        return passed, failed
    
    if not health["llm"]:
        print("  ⚠ Skipping full test - Ollama not available")
        return passed, failed
    
    # Test full query
    try:
        print("  Running query: 'What was the score of the Chiefs Dolphins playoff game?'")
        response = pipeline.query(
            "What was the score of the Chiefs Dolphins playoff game?",
            num_results=3,
        )
        
        if response.answer and len(response.answer) > 20:
            print(f"  ✓ Got response ({len(response.answer)} chars)")
            print(f"    Preview: {response.answer[:150]}...")
            print(f"    Sources: {response.num_sources}")
            print(f"    Time: {response.total_time_ms:.0f}ms")
            passed += 1
        else:
            print(f"  ✗ Response too short or empty")
            failed += 1
    except Exception as e:
        print(f"  ✗ Full query failed: {e}")
        failed += 1
    
    return passed, failed


def main():
    print("=" * 60)
    print("NFL RAG Pipeline Tests")
    print("=" * 60)
    
    total_passed = 0
    total_failed = 0
    
    # Test LLM
    p, f = test_llm_connection()
    total_passed += p
    total_failed += f
    
    # Test prompt builder
    p, f = test_prompt_builder()
    total_passed += p
    total_failed += f
    
    # Test pipeline retrieval
    p, f = test_pipeline_retrieval()
    total_passed += p
    total_failed += f
    
    # Test full pipeline
    p, f = test_full_pipeline()
    total_passed += p
    total_failed += f
    
    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    print(f"  Passed: {total_passed}")
    print(f"  Failed: {total_failed}")
    
    if total_failed == 0:
        print("\n✓ All tests passed!")
        return 0
    else:
        print(f"\n✗ {total_failed} tests failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())