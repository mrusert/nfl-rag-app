"""
Configuration settings for the NFL RAG application.

Loads settings from environment variables with sensible defaults.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"

# Create directories if they don't exist
RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)

# DuckDB settings
DUCKDB_PATH = DATA_DIR / "nfl_stats.duckdb"

# Debug mode
DEBUG = os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")

# Ollama settings
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1")

# Agent model (for tool-use)
# Recommended: qwen2.5:14b (better at function calling) - run: ollama pull qwen2.5:14b
# Fallback: llama3.1 (works but less reliable with tools)
AGENT_MODEL = os.getenv("AGENT_MODEL", "llama3.1")

# ChromaDB settings
CHROMA_PERSIST_DIRECTORY = os.getenv(
    "CHROMA_PERSIST_DIRECTORY", 
    str(PROJECT_ROOT / "chroma_db")
)

# Embedding model
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")

# API settings
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8000"))


def validate_config():
    """Validate the configuration settings."""
    errors = []
    
    if not RAW_DATA_DIR.exists():
        errors.append(f"Raw data directory does not exist: {RAW_DATA_DIR}")
    
    if errors:
        for error in errors:
            print(f"Config Error: {error}")
        return False
    
    return True


if __name__ == "__main__":
    print("Configuration Settings")
    print("=" * 50)
    print(f"PROJECT_ROOT: {PROJECT_ROOT}")
    print(f"RAW_DATA_DIR: {RAW_DATA_DIR}")
    print(f"PROCESSED_DATA_DIR: {PROCESSED_DATA_DIR}")
    print(f"DUCKDB_PATH: {DUCKDB_PATH}")
    print(f"DEBUG: {DEBUG}")
    print(f"OLLAMA_HOST: {OLLAMA_HOST}")
    print(f"OLLAMA_MODEL: {OLLAMA_MODEL}")
    print(f"AGENT_MODEL: {AGENT_MODEL}")
    print(f"CHROMA_PERSIST_DIRECTORY: {CHROMA_PERSIST_DIRECTORY}")
    print(f"EMBEDDING_MODEL: {EMBEDDING_MODEL}")
    print(f"API_HOST: {API_HOST}")
    print(f"API_PORT: {API_PORT}")
    print("=" * 50)
    print(f"Config valid: {validate_config()}")