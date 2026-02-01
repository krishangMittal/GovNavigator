"""
test_embedding_search.py - Test embedding-based semantic search

This loads the pre-built embedding index and tests searches.
Only makes 1 API call per query (to embed the query).
"""

import asyncio
import sys
from pathlib import Path

from src.search.embeddings import VoyageEmbeddings, EmbeddingSearchIndex


async def test_search(query: str):
    """Test a single search query."""

    # Load the saved index
    index_path = Path("data/processed/embedding_index.json")

    if not index_path.exists():
        print(f"Error: {index_path} not found!")
        print("Run: python build_embedding_index.py")
        return

    embedder = VoyageEmbeddings()
    index = EmbeddingSearchIndex.load(str(index_path), embedder)

    print(f"Loaded index: {len(index.documents)} documents")
    print()
    print(f"Query: '{query}'")
    print("-" * 60)

    results = await index.search(query, max_results=5)

    for i, r in enumerate(results, 1):
        doc = r["document"]
        print(f"\n{i}. Score: {r['score']}")
        print(f"   Title: {doc['title'][:60]}")
        print(f"   Section: {doc.get('section_number', 'N/A')}")
        print(f"   Preview: {doc['content'][:200]}...")


async def compare_searches():
    """Compare TF-IDF vs Embedding search."""

    from src.search.index import SearchIndex

    # Load both indexes
    tfidf_index = SearchIndex.load("data/processed/search_index.json")
    embedder = VoyageEmbeddings()
    embed_index = EmbeddingSearchIndex.load("data/processed/embedding_index.json", embedder)

    # Test query that shows the difference
    query = "barrier in my yard"

    print("=" * 60)
    print(f"COMPARING: '{query}'")
    print("=" * 60)

    # TF-IDF search
    print("\nTF-IDF Results (exact word matching):")
    print("-" * 40)
    tfidf_results = tfidf_index.search(query, max_results=3)

    if not tfidf_results:
        print("  No results! (word 'barrier' not in any documents)")
    else:
        for i, r in enumerate(tfidf_results, 1):
            print(f"  {i}. {r['document']['title'][:50]} (score: {r['score']})")

    # Embedding search
    print("\nEmbedding Results (semantic similarity):")
    print("-" * 40)
    embed_results = await embed_index.search(query, max_results=3)

    for i, r in enumerate(embed_results, 1):
        print(f"  {i}. {r['document']['title'][:50]} (score: {r['score']})")

    print("\n[!] Notice: Embeddings find relevant results even though")
    print("    'barrier' doesn't appear in the documents!")


async def main():
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
        await test_search(query)
    else:
        await compare_searches()


if __name__ == "__main__":
    asyncio.run(main())
