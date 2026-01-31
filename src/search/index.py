"""
index.py - Text Search Engine using TF-IDF

=== WHAT IS TF-IDF? ===
TF-IDF (Term Frequency - Inverse Document Frequency) is a way to measure
how important a word is to a document in a collection.

Think of it like this:
- If "fence" appears 10 times in a document about fences → HIGH relevance
- If "the" appears 100 times → LOW relevance (it's in EVERY document)

The formula combines two ideas:

1. TF (Term Frequency) = How often the word appears in THIS document
   - "fence" appears 5 times in doc A → TF = 5

2. IDF (Inverse Document Frequency) = How rare is this word across ALL docs?
   - "fence" in 2 out of 100 docs → IDF = log(100/2) = ~3.9
   - "the" in 100 out of 100 docs → IDF = log(100/100) = 0

3. TF-IDF = TF × IDF
   - "fence": 5 × 3.9 = 19.5 (important!)
   - "the": 100 × 0 = 0 (not important)

=== WHY NOT USE AI EMBEDDINGS? ===
Embeddings (like from OpenAI) convert text to vectors that capture MEANING.
"fence" and "barrier" would be close in embedding space.

TF-IDF only matches exact words (or stems), but:
- It's FREE (no API costs)
- It's FAST (pure math, no network calls)
- It's EDUCATIONAL (you understand exactly what's happening)
- It works surprisingly well for many use cases!

=== IMPLEMENTATION APPROACH ===
We'll build this from scratch using only Python standard library + basic math.
This teaches you the fundamentals without hiding complexity in libraries.
"""

import json
import math
import re
from pathlib import Path
from collections import defaultdict
from typing import Optional


# === STOP WORDS ===
# These are common words that don't help with search
# We remove them because "the fence" should match "fence regulations"
STOP_WORDS = {
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "as", "is", "was", "are", "were", "been",
    "be", "have", "has", "had", "do", "does", "did", "will", "would",
    "could", "should", "may", "might", "must", "shall", "can", "need",
    "this", "that", "these", "those", "it", "its", "they", "them", "their",
    "he", "she", "him", "her", "his", "we", "us", "our", "you", "your",
    "who", "which", "what", "where", "when", "why", "how", "all", "each",
    "any", "both", "more", "most", "other", "some", "such", "no", "nor",
    "not", "only", "own", "same", "so", "than", "too", "very", "just",
    "also", "now", "here", "there", "then", "if", "else", "because",
    "about", "into", "through", "during", "before", "after", "above",
    "below", "between", "under", "again", "further", "once", "upon",
}


def tokenize(text: str) -> list[str]:
    """
    Convert text into a list of tokens (words).

    === TOKENIZATION ===
    Breaking text into individual words/tokens is the first step in text processing.

    Example:
        "Can I build a 6-foot fence?"
        → ["can", "i", "build", "a", "6", "foot", "fence"]

    Args:
        text: The input text to tokenize

    Returns:
        List of lowercase tokens (words)
    """
    # Convert to lowercase
    text = text.lower()

    # Replace non-alphanumeric characters with spaces
    # \w matches word characters (letters, digits, underscore)
    # [^\w\s] matches anything that's NOT a word char or whitespace
    text = re.sub(r"[^\w\s]", " ", text)

    # Split on whitespace and filter empty strings
    tokens = text.split()

    # Remove stop words and very short tokens
    tokens = [t for t in tokens if t not in STOP_WORDS and len(t) > 1]

    return tokens


def simple_stem(word: str) -> str:
    """
    Very simple stemming - reduces words to approximate roots.

    === STEMMING ===
    Stemming converts related words to a common form:
    - "fencing", "fences", "fenced" → "fenc"
    - "running", "runs", "ran" → handled differently in real stemmers

    Real stemmers (Porter, Snowball) are complex. We use a simple approach:
    - Remove common suffixes like "ing", "ed", "s", "ly"

    This isn't perfect but works for basic search.

    Args:
        word: Word to stem

    Returns:
        Stemmed word
    """
    # Simple suffix removal (not as good as Porter stemmer, but works)
    if len(word) > 5:
        if word.endswith("ing"):
            return word[:-3]
        elif word.endswith("tion"):
            return word[:-4]
        elif word.endswith("ment"):
            return word[:-4]
        elif word.endswith("ness"):
            return word[:-4]
        elif word.endswith("able"):
            return word[:-4]
        elif word.endswith("ible"):
            return word[:-4]
        elif word.endswith("ous"):
            return word[:-3]
        elif word.endswith("ive"):
            return word[:-3]
        elif word.endswith("ly"):
            return word[:-2]
        elif word.endswith("ed"):
            return word[:-2]
        elif word.endswith("er"):
            return word[:-2]
        elif word.endswith("es"):
            return word[:-2]

    if len(word) > 3 and word.endswith("s"):
        return word[:-1]

    return word


class SearchIndex:
    """
    A TF-IDF based search index for ordinances.

    === HOW IT WORKS ===
    1. Build phase: Process all documents, compute TF-IDF scores
    2. Search phase: Match query terms against index, rank results

    === DATA STRUCTURES ===
    - documents: List of original document dicts
    - inverted_index: Maps terms → list of (doc_id, tf_score)
    - doc_lengths: Number of tokens per document (for normalization)
    - idf_scores: IDF score for each term
    """

    def __init__(self):
        """Initialize an empty search index."""
        self.documents: list[dict] = []

        # === INVERTED INDEX ===
        # Maps: term → [(doc_id, term_frequency), ...]
        # Example: "fence" → [(0, 5), (3, 2)] means:
        #   - Document 0 has "fence" 5 times
        #   - Document 3 has "fence" 2 times
        self.inverted_index: dict[str, list[tuple[int, int]]] = defaultdict(list)

        # Number of tokens in each document (for normalization)
        self.doc_lengths: list[int] = []

        # IDF score for each term
        self.idf_scores: dict[str, float] = {}

        # Total number of documents
        self.num_docs: int = 0

    def add_document(self, doc: dict) -> int:
        """
        Add a document to the index.

        Args:
            doc: Document dict with 'content', 'title', etc.

        Returns:
            The document ID (index in documents list)
        """
        doc_id = len(self.documents)
        self.documents.append(doc)

        # Combine title and content for indexing
        # Title words get extra weight (added twice)
        text = f"{doc.get('title', '')} {doc.get('title', '')} {doc.get('content', '')}"

        # Tokenize and stem
        tokens = tokenize(text)
        stemmed_tokens = [simple_stem(t) for t in tokens]

        # Count term frequencies in this document
        term_counts: dict[str, int] = defaultdict(int)
        for token in stemmed_tokens:
            term_counts[token] += 1

        # Add to inverted index
        for term, count in term_counts.items():
            self.inverted_index[term].append((doc_id, count))

        # Track document length
        self.doc_lengths.append(len(stemmed_tokens))

        self.num_docs += 1
        return doc_id

    def build_idf_scores(self):
        """
        Calculate IDF scores for all terms.

        === IDF FORMULA ===
        IDF(term) = log(N / df)

        Where:
        - N = total number of documents
        - df = number of documents containing the term

        A term in many documents has LOW IDF (not distinctive)
        A term in few documents has HIGH IDF (very distinctive)
        """
        for term, postings in self.inverted_index.items():
            # df = document frequency (how many docs have this term)
            df = len(postings)

            # IDF = log(N / df)
            # We add 1 to avoid division by zero and log(0)
            self.idf_scores[term] = math.log((self.num_docs + 1) / (df + 1))

    def search(self, query: str, max_results: int = 10) -> list[dict]:
        """
        Search the index for documents matching the query.

        === SEARCH ALGORITHM ===
        1. Tokenize and stem the query
        2. For each query term, find matching documents
        3. Score each document using TF-IDF
        4. Return top-ranked documents

        Args:
            query: Natural language search query
            max_results: Maximum number of results to return

        Returns:
            List of result dicts with 'document', 'score', 'matched_terms'
        """
        # Tokenize and stem query
        query_tokens = tokenize(query)
        query_stems = [simple_stem(t) for t in query_tokens]

        if not query_stems:
            return []

        # Track scores for each document
        # doc_id → score
        doc_scores: dict[int, float] = defaultdict(float)
        doc_matched_terms: dict[int, set[str]] = defaultdict(set)

        # Score each document for each query term
        for stem in query_stems:
            if stem not in self.inverted_index:
                continue

            idf = self.idf_scores.get(stem, 0)

            # For each document containing this term
            for doc_id, tf in self.inverted_index[stem]:
                # === TF-IDF SCORING ===
                # TF: Use log(1 + tf) to dampen high frequencies
                # IDF: From pre-computed scores
                # Normalization: Divide by doc length to not favor long docs

                tf_score = math.log(1 + tf)
                doc_length = self.doc_lengths[doc_id]

                # Final score for this term in this doc
                score = (tf_score * idf) / math.sqrt(doc_length + 1)

                doc_scores[doc_id] += score
                doc_matched_terms[doc_id].add(stem)

        # Sort by score (descending)
        ranked_docs = sorted(
            doc_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )[:max_results]

        # Build result list
        results = []
        for doc_id, score in ranked_docs:
            doc = self.documents[doc_id]
            matched = doc_matched_terms[doc_id]

            # Create a snippet around matched terms
            snippet = self._create_snippet(doc["content"], query_tokens)

            results.append({
                "document": doc,
                "score": round(score, 4),
                "matched_terms": list(matched),
                "snippet": snippet
            })

        return results

    def _create_snippet(self, content: str, query_terms: list[str], context: int = 100) -> str:
        """
        Create a relevant snippet from the content.

        Finds the first occurrence of a query term and extracts
        surrounding context.

        Args:
            content: Full document content
            query_terms: Original query terms (not stemmed)
            context: Number of characters before/after to include

        Returns:
            Snippet string with "..." for truncation
        """
        content_lower = content.lower()

        for term in query_terms:
            pos = content_lower.find(term.lower())
            if pos != -1:
                # Found the term, extract context around it
                start = max(0, pos - context)
                end = min(len(content), pos + len(term) + context)

                snippet = content[start:end]

                # Clean up snippet
                if start > 0:
                    snippet = "..." + snippet
                if end < len(content):
                    snippet = snippet + "..."

                return snippet.strip()

        # No exact match found, return beginning
        return content[:200] + "..." if len(content) > 200 else content

    def save(self, filepath: str):
        """
        Save the index to disk for later use.

        === PERSISTENCE ===
        Saving the index means we don't have to rebuild it each time.
        We store:
        - The documents
        - The inverted index
        - IDF scores
        - Document lengths
        """
        data = {
            "documents": self.documents,
            "inverted_index": dict(self.inverted_index),
            "idf_scores": self.idf_scores,
            "doc_lengths": self.doc_lengths,
            "num_docs": self.num_docs,
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f)

        print(f"Index saved to {filepath}")

    @classmethod
    def load(cls, filepath: str) -> "SearchIndex":
        """
        Load a previously saved index.

        Args:
            filepath: Path to the saved index

        Returns:
            SearchIndex instance with loaded data
        """
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        index = cls()
        index.documents = data["documents"]
        index.inverted_index = defaultdict(list, {
            k: [tuple(x) for x in v]
            for k, v in data["inverted_index"].items()
        })
        index.idf_scores = data["idf_scores"]
        index.doc_lengths = data["doc_lengths"]
        index.num_docs = data["num_docs"]

        return index


def build_index_from_file(json_path: str, output_path: Optional[str] = None) -> SearchIndex:
    """
    Build a search index from scraped ordinances.

    Args:
        json_path: Path to the scraped ordinances JSON
        output_path: Optional path to save the index

    Returns:
        SearchIndex ready for searching
    """
    print(f"Loading documents from {json_path}...")

    with open(json_path, "r", encoding="utf-8") as f:
        documents = json.load(f)

    print(f"Found {len(documents)} documents")

    # Create and populate index
    index = SearchIndex()

    for doc in documents:
        index.add_document(doc)

    # Build IDF scores
    index.build_idf_scores()

    print(f"Index built!")
    print(f"  - {index.num_docs} documents")
    print(f"  - {len(index.inverted_index)} unique terms")

    # Save if output path provided
    if output_path:
        index.save(output_path)

    return index


# === DEMO / TEST ===
if __name__ == "__main__":
    # Build index from scraped data
    index = build_index_from_file(
        "data/raw/madison_ordinances.json",
        "data/processed/search_index.json"
    )

    # Test some searches
    test_queries = [
        "fence height regulations",
        "parking permit",
        "fire department",
        "noise complaint",
        "building permit required",
    ]

    print("\n" + "=" * 60)
    print("SEARCH TESTS")
    print("=" * 60)

    for query in test_queries:
        print(f"\nQuery: '{query}'")
        print("-" * 40)

        results = index.search(query, max_results=3)

        if not results:
            print("  No results found")
            continue

        for i, r in enumerate(results):
            title = r["document"]["title"][:50]
            score = r["score"]
            terms = ", ".join(r["matched_terms"][:5])

            print(f"  {i+1}. {title}...")
            print(f"     Score: {score}, Terms: {terms}")
            print(f"     Snippet: {r['snippet'][:100]}...")
