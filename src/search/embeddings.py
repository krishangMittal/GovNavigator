"""
embeddings.py - Semantic Search using Vector Embeddings

=== WHAT ARE EMBEDDINGS? ===

An embedding converts text into a list of numbers (a "vector") that
captures the MEANING of the text.

Example:
    "fence"   → [0.23, -0.45, 0.89, 0.12, ..., 0.34]  (768 numbers)
    "barrier" → [0.25, -0.42, 0.87, 0.15, ..., 0.31]  (similar!)
    "pizza"   → [0.91, 0.23, -0.56, 0.78, ..., -0.12] (very different)

The AI model learned these representations from billions of text examples,
so semantically similar words/sentences end up with similar vectors.

=== HOW SIMILARITY WORKS ===

We measure similarity using "cosine similarity":
- Two identical vectors: similarity = 1.0
- Completely unrelated: similarity ≈ 0.0
- Opposite meanings: similarity = -1.0

Formula: cos(θ) = (A · B) / (|A| × |B|)
(Don't worry about the math - we'll use a function!)

=== EMBEDDING PROVIDERS ===

1. OpenAI: $0.02 per million tokens (very cheap)
2. Voyage AI: 50M free tokens (what we'll use!)
3. Cohere: 100 API calls/min free tier
4. Local models: sentence-transformers (free, needs GPU for speed)

We'll implement Voyage AI since it has a generous free tier.
"""

import json
import math
import os
from pathlib import Path
from typing import Optional
import httpx  # For making HTTP requests

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


def cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
    """
    Calculate cosine similarity between two vectors.

    === COSINE SIMILARITY EXPLAINED ===

    Imagine two arrows pointing from the origin:
    - If they point the same direction: similarity = 1
    - If they're perpendicular (90°): similarity = 0
    - If they point opposite: similarity = -1

    Formula:
        similarity = (A · B) / (|A| × |B|)

    Where:
        A · B = sum of (a_i × b_i) for all dimensions  (dot product)
        |A| = sqrt(sum of a_i²)  (magnitude/length of vector)

    Args:
        vec1: First embedding vector
        vec2: Second embedding vector

    Returns:
        Similarity score from -1 to 1 (higher = more similar)
    """
    # Dot product: multiply corresponding elements and sum
    dot_product = sum(a * b for a, b in zip(vec1, vec2))

    # Magnitudes: sqrt of sum of squares
    magnitude1 = math.sqrt(sum(a * a for a in vec1))
    magnitude2 = math.sqrt(sum(b * b for b in vec2))

    # Avoid division by zero
    if magnitude1 == 0 or magnitude2 == 0:
        return 0.0

    return dot_product / (magnitude1 * magnitude2)


class VoyageEmbeddings:
    """
    Client for Voyage AI embeddings API.

    === VOYAGE AI ===
    Voyage AI provides high-quality embeddings optimized for search.
    Free tier: 50 million tokens (plenty for learning!)

    Sign up at: https://www.voyageai.com/
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the Voyage AI client.

        Args:
            api_key: Your Voyage AI API key. If not provided,
                     looks for VOYAGE_API_KEY environment variable.
        """
        self.api_key = api_key or os.getenv("VOYAGE_API_KEY")

        if not self.api_key:
            raise ValueError(
                "Voyage AI API key required!\n"
                "1. Sign up at https://www.voyageai.com/\n"
                "2. Get your API key from the dashboard\n"
                "3. Add to .env file: VOYAGE_API_KEY=your_key_here"
            )

        self.base_url = "https://api.voyageai.com/v1"
        self.model = "voyage-2"  # Good balance of quality and speed

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """
        Convert a list of texts into embedding vectors.

        Args:
            texts: List of strings to embed

        Returns:
            List of embedding vectors (each is a list of floats)
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/embeddings",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": self.model,
                    "input": texts,
                    "input_type": "document"  # or "query" for search queries
                },
                timeout=30.0
            )

            if response.status_code != 200:
                raise Exception(f"Voyage API error: {response.text}")

            data = response.json()

            # Extract embeddings from response
            embeddings = [item["embedding"] for item in data["data"]]

            return embeddings

    async def embed_query(self, query: str) -> list[float]:
        """
        Embed a search query.

        Note: Queries are embedded differently than documents
        for better search performance.
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/embeddings",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": self.model,
                    "input": [query],
                    "input_type": "query"  # Optimized for search queries
                },
                timeout=30.0
            )

            if response.status_code != 200:
                raise Exception(f"Voyage API error: {response.text}")

            data = response.json()
            return data["data"][0]["embedding"]


class EmbeddingSearchIndex:
    """
    Search index using vector embeddings.

    === HOW IT WORKS ===

    Building the index:
    1. Load all documents
    2. Convert each document's content to an embedding vector
    3. Store vectors alongside documents

    Searching:
    1. Convert query to embedding vector
    2. Calculate similarity between query vector and all document vectors
    3. Return documents with highest similarity

    This finds semantically similar content even with different words!
    """

    def __init__(self, embedder: Optional[VoyageEmbeddings] = None):
        """
        Initialize the embedding search index.

        Args:
            embedder: Embedding provider (VoyageEmbeddings instance)
        """
        self.embedder = embedder
        self.documents: list[dict] = []
        self.embeddings: list[list[float]] = []

    async def add_documents(self, documents: list[dict], batch_size: int = 5):
        """
        Add documents to the index.

        Args:
            documents: List of document dicts (must have 'content' key)
            batch_size: How many to embed at once (smaller for rate limits)
        """
        import asyncio

        print(f"Indexing {len(documents)} documents...")
        print("  (Free tier has rate limits - adding delays between batches)")

        for i in range(0, len(documents), batch_size):
            batch = documents[i:i + batch_size]

            # Create text to embed (title + content preview)
            texts = [
                f"{doc.get('title', '')} {doc.get('content', '')[:1000]}"
                for doc in batch
            ]

            # Get embeddings with retry logic
            try:
                batch_embeddings = await self.embedder.embed_texts(texts)

                # Store documents and their embeddings
                self.documents.extend(batch)
                self.embeddings.extend(batch_embeddings)

                print(f"  Indexed {min(i + batch_size, len(documents))}/{len(documents)}")

            except Exception as e:
                if "rate" in str(e).lower():
                    print(f"  Rate limited, waiting 30 seconds...")
                    await asyncio.sleep(30)
                    # Retry
                    batch_embeddings = await self.embedder.embed_texts(texts)
                    self.documents.extend(batch)
                    self.embeddings.extend(batch_embeddings)
                    print(f"  Indexed {min(i + batch_size, len(documents))}/{len(documents)}")
                else:
                    raise

            # Wait between batches to respect rate limits (3 RPM = 20 seconds between)
            if i + batch_size < len(documents):
                print("  Waiting 25 seconds for rate limit...")
                await asyncio.sleep(25)

        print(f"Done! Index contains {len(self.documents)} documents")

    async def search(self, query: str, max_results: int = 5) -> list[dict]:
        """
        Search for documents similar to the query.

        Args:
            query: Natural language search query
            max_results: Maximum number of results

        Returns:
            List of results with document, score, and snippet
        """
        # Embed the query
        query_embedding = await self.embedder.embed_query(query)

        # Calculate similarity with all documents
        similarities = []
        for i, doc_embedding in enumerate(self.embeddings):
            score = cosine_similarity(query_embedding, doc_embedding)
            similarities.append((i, score))

        # Sort by similarity (highest first)
        similarities.sort(key=lambda x: x[1], reverse=True)

        # Build results
        results = []
        for doc_idx, score in similarities[:max_results]:
            doc = self.documents[doc_idx]

            results.append({
                "document": doc,
                "score": round(score, 4),
                "snippet": doc.get("content", "")[:300] + "..."
            })

        return results

    def save(self, filepath: str):
        """Save the index to disk."""
        data = {
            "documents": self.documents,
            "embeddings": self.embeddings
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f)

        print(f"Index saved to {filepath}")

    @classmethod
    def load(cls, filepath: str, embedder: VoyageEmbeddings) -> "EmbeddingSearchIndex":
        """Load a previously saved index."""
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        index = cls(embedder)
        index.documents = data["documents"]
        index.embeddings = data["embeddings"]

        return index


# === DEMO ===
async def demo():
    """Demonstrate embeddings vs TF-IDF."""

    print("=" * 60)
    print("EMBEDDING DEMO")
    print("=" * 60)

    # Check for API key
    api_key = os.getenv("VOYAGE_API_KEY")
    if not api_key:
        print("\nTo use embeddings, you need a Voyage AI API key:")
        print("1. Go to https://www.voyageai.com/")
        print("2. Sign up (free)")
        print("3. Get your API key")
        print("4. Add to .env file: VOYAGE_API_KEY=your_key_here")
        print("\nFor now, here's how embeddings would work:\n")

        # Show conceptual demo
        print("Query: 'Can I build a barrier in my yard?'")
        print()
        print("TF-IDF result: [X] No match (no documents contain 'barrier')")
        print()
        print("Embedding result: [OK] Finds fence regulations!")
        print("  Because 'barrier' and 'fence' have similar embeddings:")
        print("    'barrier' -> [0.23, -0.45, 0.89, ...]")
        print("    'fence'   -> [0.25, -0.42, 0.87, ...]  (very similar!)")
        return

    # If we have API key, do real demo
    embedder = VoyageEmbeddings(api_key)

    # Test with sample sentences
    sentences = [
        "fence regulations for residential property",
        "barrier requirements in yard",
        "pizza delivery hours",
    ]

    print("\nEmbedding sample sentences...")
    embeddings = await embedder.embed_texts(sentences)

    print(f"\nEmbedding dimension: {len(embeddings[0])}")

    print("\nSimilarity scores:")
    for i, s1 in enumerate(sentences):
        for j, s2 in enumerate(sentences):
            if i < j:
                sim = cosine_similarity(embeddings[i], embeddings[j])
                print(f"  '{s1[:30]}...' vs '{s2[:30]}...': {sim:.3f}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(demo())
