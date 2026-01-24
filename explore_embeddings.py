"""
Explore how embeddings work and why they're useful for semantic search.
"""

from sentence_transformers import SentenceTransformer
import numpy as np

def cosine_similarity(a, b):
    """Calculate cosine similarity between two vectors."""
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

def main():
    print("Loading embedding model...")
    model = SentenceTransformer('all-MiniLM-L6-v2')
    
    # Sample NFL-related texts
    documents = [
        "Patrick Mahomes threw for 4,183 yards in 2023",
        "The Chiefs quarterback had an excellent passing season",
        "Kansas City's signal caller accumulated over 4000 aerial yards",
        "Tom Brady retired from professional football",
        "The best pizza recipes use fresh mozzarella",
        "Mahomes completed 67.2% of his passes",
        "Travis Kelce caught 93 passes for 984 yards",
    ]
    
    # Create embeddings for all documents
    print("\nCreating embeddings for documents...")
    doc_embeddings = model.encode(documents)
    
    print(f"Each embedding has {len(doc_embeddings[0])} dimensions")
    
    # Test queries
    queries = [
        "How many yards did Mahomes throw for?",
        "Tell me about the Chiefs passing game",
        "What are some good pizza toppings?",
    ]
    
    print("\n" + "=" * 60)
    
    for query in queries:
        print(f"\nQuery: '{query}'")
        print("-" * 60)
        
        # Embed the query
        query_embedding = model.encode(query)
        
        # Calculate similarity to each document
        similarities = []
        for i, doc_emb in enumerate(doc_embeddings):
            sim = cosine_similarity(query_embedding, doc_emb)
            similarities.append((sim, documents[i]))
        
        # Sort by similarity (highest first)
        similarities.sort(reverse=True)
        
        # Show results
        for sim, doc in similarities:
            # Visual indicator of relevance
            if sim > 0.5:
                indicator = "✓✓"
            elif sim > 0.3:
                indicator = "✓ "
            else:
                indicator = "  "
            
            print(f"  {indicator} {sim:.3f}: {doc[:60]}...")
    
    print("\n" + "=" * 60)
    print("\nKey observations:")
    print("1. Semantically similar texts have high similarity scores")
    print("2. Different phrasings of the same concept still match well")
    print("3. Unrelated topics have low similarity scores")
    print("4. The model understands 'yards' relates to 'passing' and 'aerial'")

if __name__ == "__main__":
    main()