"""
Configuration module for the NFL RAG application.
Loads environment variables and provides app-wide settings.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Base paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"

# Ensure directories exist
RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)

# Ollama settings
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1")

# ChromaDB settings
CHROMA_PERSIST_DIRECTORY = os.getenv("CHROMA_PERSIST_DIRECTORY", "./chroma_db")
CHROMA_COLLECTION_NAME = "nfl_data"

# Embedding settings (runs locally - no API needed!)
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")

# Application settings
DEBUG = os.getenv("DEBUG", "false").lower() == "true"

# Scraping settings
REQUEST_DELAY = 3  # Seconds between requests (be nice to Pro Football Reference)
USER_AGENT = "NFL-RAG-App/1.0 (Educational Project)"


def validate_config():
    """Check that required configuration is present."""
    print("Configuration Summary:")
    print(f"  Ollama Host: {OLLAMA_HOST}")
    print(f"  Ollama Model: {OLLAMA_MODEL}")
    print(f"  Embedding Model: {EMBEDDING_MODEL}")
    print(f"  ChromaDB Directory: {CHROMA_PERSIST_DIRECTORY}")
    print(f"  Debug Mode: {DEBUG}")
    return True


if __name__ == "__main__":
    # Test configuration when run directly
    print(f"Base directory: {BASE_DIR}")
    print(f"Data directory: {DATA_DIR}")
    print()
    validate_config()