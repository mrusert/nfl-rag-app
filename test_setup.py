"""
Test script to verify the development environment is set up correctly.
"""

def test_imports():
    """Test that all required packages can be imported."""
    print("Testing imports...")
    
    tests = [
        ("fastapi", lambda: __import__("fastapi").__version__),
        ("requests", lambda: __import__("requests").__version__),
        ("beautifulsoup4", lambda: __import__("bs4").__version__),
        ("chromadb", lambda: __import__("chromadb").__version__),
        ("ollama", lambda: "installed"),
        ("pandas", lambda: __import__("pandas").__version__),
        ("sentence-transformers", lambda: "installed"),
    ]
    
    for name, get_version in tests:
        try:
            version = get_version()
            print(f"  ✓ {name} {version}")
        except ImportError as e:
            print(f"  ✗ {name}: {e}")


def test_config():
    """Test that the config module works."""
    print("\nTesting configuration...")
    
    try:
        from src.config import BASE_DIR, OLLAMA_MODEL, validate_config
        print(f"  ✓ Config module loaded")
        print(f"  ✓ Base directory: {BASE_DIR}")
        print(f"  ✓ Ollama model: {OLLAMA_MODEL}")
    except Exception as e:
        print(f"  ✗ Config error: {e}")


def test_chromadb():
    """Test that ChromaDB works."""
    print("\nTesting ChromaDB...")
    
    try:
        import chromadb
        
        # Create a temporary in-memory client
        client = chromadb.Client()
        
        # Create a test collection
        collection = client.create_collection("test")
        
        # Add a document
        collection.add(
            documents=["The Kansas City Chiefs won Super Bowl LVIII."],
            ids=["test1"]
        )
        
        # Query it
        results = collection.query(
            query_texts=["Who won the Super Bowl?"],
            n_results=1
        )
        
        print(f"  ✓ ChromaDB working correctly")
        print(f"  ✓ Test query returned: {results['documents'][0][0][:50]}...")
        
        # Clean up
        client.delete_collection("test")
        
    except Exception as e:
        print(f"  ✗ ChromaDB error: {e}")


def test_ollama():
    """Test that Ollama is running and has a model available."""
    print("\nTesting Ollama...")
    
    try:
        import ollama
        
        # List available models
        models = ollama.list()
        model_names = [m['name'] for m in models.get('models', [])]
        
        if model_names:
            print(f"  ✓ Ollama is running")
            print(f"  ✓ Available models: {', '.join(model_names)}")
            
            # Test a simple generation
            from src.config import OLLAMA_MODEL
            print(f"\n  Testing generation with {OLLAMA_MODEL}...")
            
            response = ollama.generate(
                model=OLLAMA_MODEL,
                prompt="Say 'Hello, NFL RAG!' and nothing else.",
            )
            
            print(f"  ✓ Model responded: {response['response'].strip()}")
        else:
            print(f"  ⚠ Ollama is running but no models installed")
            print(f"    Run: ollama pull llama3.1")
            
    except Exception as e:
        print(f"  ✗ Ollama error: {e}")
        print(f"    Make sure Ollama app is running on your Mac")


def test_embeddings():
    """Test that the embedding model works."""
    print("\nTesting embedding model...")
    
    try:
        from sentence_transformers import SentenceTransformer
        from src.config import EMBEDDING_MODEL
        
        print(f"  Loading {EMBEDDING_MODEL}... (this may take a moment the first time)")
        model = SentenceTransformer(EMBEDDING_MODEL)
        
        # Create a test embedding
        test_text = "Patrick Mahomes threw for 300 yards"
        embedding = model.encode(test_text)
        
        print(f"  ✓ Embedding model loaded")
        print(f"  ✓ Test embedding shape: {embedding.shape}")
        
    except Exception as e:
        print(f"  ✗ Embedding error: {e}")


if __name__ == "__main__":
    print("=" * 50)
    print("NFL RAG App - Environment Verification")
    print("=" * 50)
    
    test_imports()
    test_config()
    test_chromadb()
    test_ollama()
    test_embeddings()
    
    print("\n" + "=" * 50)
    print("Verification complete!")
    print("=" * 50)