"""
build_embedding_index.py - Build embedding search index from scraped data

This script:
1. Loads the scraped ordinances
2. Converts each document to an embedding vector using Voyage AI
3. Saves the index for fast searching

Run this once after scraping to create the embedding index.
"""

import asyncio
import json
from pathlib import Path

from src.search.embeddings import VoyageEmbeddings, EmbeddingSearchIndex


async def build_index():
    """Build the embedding index from scraped ordinances."""

    print("=" * 60)
    print("Building Embedding Search Index")
    print("=" * 60)

    # Load scraped ordinances
    data_path = Path("data/raw/madison_ordinances_full.json")

    if not data_path.exists():
        print(f"Error: {data_path} not found!")
        print("Run the scraper first: python -m src.scraper.municode_scraper")
        return

    with open(data_path, "r", encoding="utf-8") as f:
        documents = json.load(f)

    print(f"\nLoaded {len(documents)} documents")

    # Create embedder and index
    embedder = VoyageEmbeddings()
    index = EmbeddingSearchIndex(embedder)

    # Add documents (this calls the Voyage API)
    print("\nGenerating embeddings (this may take a moment)...")
    await index.add_documents(documents, batch_size=10)

    # Save the index
    output_path = Path("data/processed/embedding_index.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    index.save(str(output_path))

    print(f"\nIndex saved to {output_path}")
    print(f"Total documents: {len(index.documents)}")
    print(f"Embedding dimension: {len(index.embeddings[0])}")

    # Test a search
    print("\n" + "=" * 60)
    print("Testing Search")
    print("=" * 60)

    test_queries = [
        "Can I build a barrier in my yard?",  # Should find fence regulations!
        "noise complaint late night",
        "starting a business permit",
    ]

    for query in test_queries:
        print(f"\nQuery: '{query}'")
        results = await index.search(query, max_results=3)

        for i, r in enumerate(results, 1):
            print(f"  {i}. {r['document']['title'][:50]}... (score: {r['score']})")


if __name__ == "__main__":
    asyncio.run(build_index())
