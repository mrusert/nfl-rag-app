"""
NFL Embedder - Generates vector embeddings for text chunks.

Uses sentence-transformers for local embedding generation.
The default model (all-MiniLM-L6-v2) provides a good balance of
speed and quality for semantic search.
"""

from typing import Optional
import numpy as np
from tqdm import tqdm

from src.config import EMBEDDING_MODEL, DEBUG


class NFLEmbedder:
    """
    Generates embeddings for NFL text chunks.
    
    Uses sentence-transformers models which run locally without
    requiring an API key.
    
    Default model: all-MiniLM-L6-v2
    - Embedding dimension: 384
    - Fast inference
    - Good quality for semantic similarity
    
    Alternative models:
    - all-mpnet-base-v2: Better quality, slower (768 dims)
    - paraphrase-MiniLM-L6-v2: Optimized for paraphrase detection
    """
    
    def __init__(
        self,
        model_name: Optional[str] = None,
        device: Optional[str] = None,
        batch_size: int = 64,
    ):
        """
        Initialize the embedder.
        
        Args:
            model_name: Name of sentence-transformers model
            device: Device to run on ('cpu', 'cuda', 'mps')
            batch_size: Batch size for encoding
        """
        self.model_name = model_name or EMBEDDING_MODEL
        self.batch_size = batch_size
        self._model = None
        self._device = device
    
    @property
    def model(self):
        """Lazy load the model on first use."""
        if self._model is None:
            if DEBUG:
                print(f"Loading embedding model: {self.model_name}")
            
            from sentence_transformers import SentenceTransformer
            
            self._model = SentenceTransformer(
                self.model_name,
                device=self._device,
            )
            
            if DEBUG:
                print(f"  Model loaded. Embedding dimension: {self.embedding_dimension}")
        
        return self._model
    
    @property
    def embedding_dimension(self) -> int:
        """Get the embedding dimension for the model."""
        return self.model.get_sentence_embedding_dimension()
    
    def embed_text(self, text: str) -> list[float]:
        """
        Generate embedding for a single text.
        
        Args:
            text: Text to embed
            
        Returns:
            List of floats representing the embedding
        """
        embedding = self.model.encode(
            text,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return embedding.tolist()
    
    def embed_texts(
        self,
        texts: list[str],
        show_progress: bool = True,
    ) -> list[list[float]]:
        """
        Generate embeddings for multiple texts.
        
        Args:
            texts: List of texts to embed
            show_progress: Show progress bar
            
        Returns:
            List of embeddings (each is a list of floats)
        """
        if not texts:
            return []
        
        if DEBUG:
            print(f"Embedding {len(texts)} texts...")
        
        embeddings = self.model.encode(
            texts,
            batch_size=self.batch_size,
            convert_to_numpy=True,
            show_progress_bar=show_progress,
        )
        
        return embeddings.tolist()
    
    def embed_chunks(
        self,
        chunks: list,
        show_progress: bool = True,
    ) -> list[tuple[str, list[float], dict]]:
        """
        Generate embeddings for Chunk objects.
        
        Args:
            chunks: List of Chunk objects
            show_progress: Show progress bar
            
        Returns:
            List of (chunk_id, embedding, metadata) tuples
        """
        if not chunks:
            return []
        
        # Extract texts
        texts = [chunk.text for chunk in chunks]
        
        # Generate embeddings
        embeddings = self.embed_texts(texts, show_progress=show_progress)
        
        # Combine with chunk info
        results = []
        for chunk, embedding in zip(chunks, embeddings):
            results.append((chunk.id, embedding, chunk.metadata))
        
        return results
    
    def compute_similarity(
        self,
        embedding1: list[float],
        embedding2: list[float],
    ) -> float:
        """
        Compute cosine similarity between two embeddings.
        
        Args:
            embedding1: First embedding
            embedding2: Second embedding
            
        Returns:
            Cosine similarity score (0-1)
        """
        vec1 = np.array(embedding1)
        vec2 = np.array(embedding2)
        
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return float(dot_product / (norm1 * norm2))
    
    def find_most_similar(
        self,
        query_embedding: list[float],
        candidate_embeddings: list[list[float]],
        top_k: int = 5,
    ) -> list[tuple[int, float]]:
        """
        Find most similar embeddings to a query.
        
        Args:
            query_embedding: Query embedding
            candidate_embeddings: List of candidate embeddings
            top_k: Number of results to return
            
        Returns:
            List of (index, similarity_score) tuples, sorted by similarity
        """
        similarities = []
        
        for idx, candidate in enumerate(candidate_embeddings):
            sim = self.compute_similarity(query_embedding, candidate)
            similarities.append((idx, sim))
        
        # Sort by similarity (descending)
        similarities.sort(key=lambda x: x[1], reverse=True)
        
        return similarities[:top_k]


# Quick test
if __name__ == "__main__":
    print("Testing NFLEmbedder...")
    print("=" * 60)
    
    embedder = NFLEmbedder()
    
    # Test single embedding
    text = "Patrick Mahomes threw for 4183 yards in 2023"
    embedding = embedder.embed_text(text)
    print(f"✓ Single embedding: {len(embedding)} dimensions")
    
    # Test batch embedding
    texts = [
        "Patrick Mahomes is a quarterback for the Kansas City Chiefs",
        "Travis Kelce is a tight end who plays for KC",
        "The weather was cold and windy",
        "The Chiefs beat the Dolphins in the playoffs",
    ]
    embeddings = embedder.embed_texts(texts, show_progress=False)
    print(f"✓ Batch embedding: {len(embeddings)} texts embedded")
    
    # Test similarity
    query = embedder.embed_text("Who is the Chiefs quarterback?")
    similar = embedder.find_most_similar(query, embeddings, top_k=2)
    
    print(f"\n✓ Similarity search:")
    print(f"  Query: 'Who is the Chiefs quarterback?'")
    for idx, score in similar:
        print(f"  #{idx+1} (score: {score:.3f}): '{texts[idx][:50]}...'")
    
    print("\n✓ All tests passed!")