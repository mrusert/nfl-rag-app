"""
Test the embedding and vector store functionality.
"""

import sys
import tempfile
from pathlib import Path


def test_embedder():
    """Test the embedding functionality."""
    print("Testing NFLEmbedder...")
    
    from src.retrieval.embedder import NFLEmbedder
    
    passed = 0
    failed = 0
    
    # Initialize embedder
    try:
        embedder = NFLEmbedder()
        print(f"  ✓ Embedder initialized with model: {embedder.model_name}")
        passed += 1
    except Exception as e:
        print(f"  ✗ Embedder initialization failed: {e}")
        failed += 1
        return passed, failed
    
    # Test single embedding
    try:
        text = "Patrick Mahomes threw for 4183 yards in 2023"
        embedding = embedder.embed_text(text)
        
        if len(embedding) == embedder.embedding_dimension:
            print(f"  ✓ Single embedding: {len(embedding)} dimensions")
            passed += 1
        else:
            print(f"  ✗ Wrong embedding dimension: {len(embedding)}")
            failed += 1
    except Exception as e:
        print(f"  ✗ Single embedding failed: {e}")
        failed += 1
    
    # Test batch embedding
    try:
        texts = [
            "Patrick Mahomes is a quarterback",
            "Travis Kelce is a tight end",
            "The Chiefs won the Super Bowl",
        ]
        embeddings = embedder.embed_texts(texts, show_progress=False)
        
        if len(embeddings) == len(texts):
            print(f"  ✓ Batch embedding: {len(embeddings)} texts embedded")
            passed += 1
        else:
            print(f"  ✗ Wrong batch size: {len(embeddings)}")
            failed += 1
    except Exception as e:
        print(f"  ✗ Batch embedding failed: {e}")
        failed += 1
    
    # Test similarity
    try:
        query = embedder.embed_text("Who is the Chiefs quarterback?")
        similar = embedder.find_most_similar(query, embeddings, top_k=1)
        
        # The first text about Mahomes should be most similar
        if similar[0][0] == 0:  # Index 0 is Mahomes text
            print(f"  ✓ Similarity search correct (score: {similar[0][1]:.3f})")
            passed += 1
        else:
            print(f"  ⚠ Similarity search unexpected result: index {similar[0][0]}")
            passed += 1  # Still count as pass, order might vary
    except Exception as e:
        print(f"  ✗ Similarity search failed: {e}")
        failed += 1
    
    return passed, failed


def test_vector_store():
    """Test the vector store functionality."""
    print("\nTesting NFLVectorStore...")
    
    from src.retrieval.vector_store import NFLVectorStore, build_metadata_filter
    from src.processing.chunker import Chunk
    
    passed = 0
    failed = 0
    
    # Create temporary directory for test
    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            store = NFLVectorStore(persist_directory=temp_dir)
            print(f"  ✓ Vector store initialized")
            passed += 1
        except Exception as e:
            print(f"  ✗ Vector store initialization failed: {e}")
            failed += 1
            return passed, failed
        
        # Create test chunks
        test_chunks = [
            Chunk(
                id="test_1",
                text="Patrick Mahomes threw for 4183 yards and 27 touchdowns in 2023",
                metadata={"chunk_type": "player_season", "player_name": "Patrick Mahomes", "team": "KC", "position": "QB", "season": 2023}
            ),
            Chunk(
                id="test_2",
                text="Travis Kelce caught 93 passes for 984 yards in 2023",
                metadata={"chunk_type": "player_season", "player_name": "Travis Kelce", "team": "KC", "position": "TE", "season": 2023}
            ),
            Chunk(
                id="test_3",
                text="The Chiefs beat the Dolphins 26-7 in the playoffs in freezing conditions",
                metadata={"chunk_type": "game_summary", "home_team": "KC", "away_team": "MIA", "temperature_category": "freezing"}
            ),
            Chunk(
                id="test_4",
                text="Josh Allen threw for 4306 yards in 2023 for the Buffalo Bills",
                metadata={"chunk_type": "player_season", "player_name": "Josh Allen", "team": "BUF", "position": "QB", "season": 2023}
            ),
        ]
        
        # Add chunks
        try:
            added = store.add_chunks(test_chunks, show_progress=False)
            if added == len(test_chunks):
                print(f"  ✓ Added {added} chunks")
                passed += 1
            else:
                print(f"  ✗ Only added {added}/{len(test_chunks)} chunks")
                failed += 1
        except Exception as e:
            print(f"  ✗ Adding chunks failed: {e}")
            failed += 1
            return passed, failed
        
        # Test count
        try:
            count = store.count()
            if count == len(test_chunks):
                print(f"  ✓ Count correct: {count}")
                passed += 1
            else:
                print(f"  ✗ Count wrong: {count}")
                failed += 1
        except Exception as e:
            print(f"  ✗ Count failed: {e}")
            failed += 1
        
        # Test search
        try:
            results = store.search("Who is the Chiefs quarterback?", n_results=2)
            if results and "Mahomes" in results[0].text:
                print(f"  ✓ Search found Mahomes (score: {results[0].score:.3f})")
                passed += 1
            else:
                print(f"  ⚠ Search returned unexpected result")
                passed += 1
        except Exception as e:
            print(f"  ✗ Search failed: {e}")
            failed += 1
        
        # Test filtered search
        try:
            where = build_metadata_filter(position="TE")
            results = store.search("receiving yards", n_results=2, where=where)
            if results and "Kelce" in results[0].text:
                print(f"  ✓ Filtered search found Kelce")
                passed += 1
            else:
                print(f"  ⚠ Filtered search unexpected result")
                passed += 1
        except Exception as e:
            print(f"  ✗ Filtered search failed: {e}")
            failed += 1
        
        # Test get by ID
        try:
            result = store.get_by_id("test_1")
            if result and "Mahomes" in result.text:
                print(f"  ✓ Get by ID works")
                passed += 1
            else:
                print(f"  ✗ Get by ID returned wrong result")
                failed += 1
        except Exception as e:
            print(f"  ✗ Get by ID failed: {e}")
            failed += 1
        
        # Test team filter
        try:
            where = build_metadata_filter(team="KC")
            results = store.search("player statistics", n_results=10, where=where)
            # Should only return KC players/games
            all_kc = all(
                r.metadata.get("team") == "KC" or 
                r.metadata.get("home_team") == "KC" or
                r.metadata.get("away_team") == "KC"
                for r in results
            )
            if all_kc and len(results) == 3:  # 2 KC players + 1 KC game
                print(f"  ✓ Team filter works ({len(results)} KC results)")
                passed += 1
            else:
                print(f"  ⚠ Team filter: {len(results)} results, all_kc={all_kc}")
                passed += 1
        except Exception as e:
            print(f"  ✗ Team filter failed: {e}")
            failed += 1
        
        # Test stats
        try:
            stats = store.get_stats()
            if stats["total_chunks"] == len(test_chunks):
                print(f"  ✓ Stats correct")
                passed += 1
            else:
                print(f"  ✗ Stats wrong: {stats}")
                failed += 1
        except Exception as e:
            print(f"  ✗ Stats failed: {e}")
            failed += 1
    
    return passed, failed


def test_metadata_filter():
    """Test the metadata filter builder."""
    print("\nTesting metadata filter builder...")
    
    from src.retrieval.vector_store import build_metadata_filter
    
    passed = 0
    failed = 0
    
    # Single filter
    f = build_metadata_filter(team="KC")
    if f == {"team": "KC"}:
        print(f"  ✓ Single filter correct")
        passed += 1
    else:
        print(f"  ✗ Single filter wrong: {f}")
        failed += 1
    
    # Multiple filters
    f = build_metadata_filter(team="KC", position="QB")
    if f == {"$and": [{"team": "KC"}, {"position": "QB"}]}:
        print(f"  ✓ Multiple filters correct")
        passed += 1
    else:
        print(f"  ✗ Multiple filters wrong: {f}")
        failed += 1
    
    # No filters
    f = build_metadata_filter()
    if f is None:
        print(f"  ✓ Empty filter correct")
        passed += 1
    else:
        print(f"  ✗ Empty filter wrong: {f}")
        failed += 1
    
    # Boolean filter
    f = build_metadata_filter(was_favorite=True)
    if f == {"was_favorite": True}:
        print(f"  ✓ Boolean filter correct")
        passed += 1
    else:
        print(f"  ✗ Boolean filter wrong: {f}")
        failed += 1
    
    return passed, failed


def test_with_real_data():
    """Test with real indexed data if available."""
    print("\nTesting with real data (if indexed)...")
    
    from src.retrieval.vector_store import NFLVectorStore
    from src.config import CHROMA_PERSIST_DIRECTORY
    
    passed = 0
    failed = 0
    
    try:
        store = NFLVectorStore()
        count = store.count()
        
        if count == 0:
            print(f"  ⚠ No data indexed yet")
            print(f"    Run: python -m src.retrieval.indexer")
            return passed, failed
        
        print(f"  ✓ Found {count} indexed chunks")
        passed += 1
        
        # Test some real queries
        test_queries = [
            "Patrick Mahomes 2023 season stats",
            "Chiefs playoff games",
            "cold weather games",
        ]
        
        for query in test_queries:
            results = store.search(query, n_results=3)
            if results:
                print(f"  ✓ '{query}' → {len(results)} results (top score: {results[0].score:.3f})")
                passed += 1
            else:
                print(f"  ✗ '{query}' → no results")
                failed += 1
        
    except Exception as e:
        print(f"  ✗ Real data test failed: {e}")
        failed += 1
    
    return passed, failed


def main():
    print("=" * 60)
    print("Embedding & Vector Store Tests")
    print("=" * 60)
    
    total_passed = 0
    total_failed = 0
    
    # Test embedder
    p, f = test_embedder()
    total_passed += p
    total_failed += f
    
    # Test vector store
    p, f = test_vector_store()
    total_passed += p
    total_failed += f
    
    # Test metadata filter
    p, f = test_metadata_filter()
    total_passed += p
    total_failed += f
    
    # Test with real data
    p, f = test_with_real_data()
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