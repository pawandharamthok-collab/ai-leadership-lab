"""
Enterprise Tier 2 Vector Knowledge Base Module
Author: AI Leadership Lab
Purpose: Granular semantic vector storage and retrieval.
- Cloud Embeddings: Gemini embedding API (768 dimensions, 0% laptop RAM/CPU)
- Pre-Flight Security: Automatic PII scrubbing before vectorization
- Hybrid Storage:
    * Primary: Pinecone Serverless (AWS/GCP, free forever, 100k vectors)
    * Graceful Fallback: Local Zero-RAM SQLite Vector Store (when PINECONE_API_KEY not set)
"""

import os
import json
import math
import sqlite3
import time
from typing import List, Dict, Any, Optional
from google import genai
from google.genai import types
from security_router import PIISanitizer

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "memory.db")

class VectorKnowledgeBase:
    INDEX_NAME = "ai-leadership-kb"
    DIMENSION = 768

    @classmethod
    def get_embedding(cls, client: genai.Client, text: str) -> List[float]:
        """Generates 768-dim embeddings on Google Cloud TPUs (0% laptop RAM load)."""
        response = client.models.embed_content(
            model="gemini-embedding-001",
            contents=text,
            config=types.EmbedContentConfig(output_dimensionality=cls.DIMENSION)
        )
        return response.embeddings[0].values

    @classmethod
    def init_local_table(cls):
        """Ensures SQLite fallback vector table exists."""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS vector_knowledge (
                id TEXT PRIMARY KEY,
                doc_title TEXT NOT NULL,
                chunk_index INTEGER,
                content TEXT NOT NULL,
                embedding_json TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()

    @classmethod
    def chunk_text(cls, text: str, chunk_size: int = 800, overlap: int = 150) -> List[str]:
        """Splits text into overlapping semantic chunks."""
        chunks = []
        start = 0
        while start < len(text):
            end = start + chunk_size
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            start += chunk_size - overlap
        return chunks

    @classmethod
    def index_document(cls, client: genai.Client, content: str, title: str = "Knowledge Snippet") -> Dict[str, Any]:
        """
        Sanitizes text, chunks it, generates cloud embeddings, and indexes into Pinecone or SQLite fallback.
        """
        cls.init_local_table()
        sanitized_content, redactions = PIISanitizer.sanitize(content)
        chunks = cls.chunk_text(sanitized_content)
        if not chunks:
            return {"status": "error", "message": "Document contains no readable content."}

        pinecone_key = os.getenv("PINECONE_API_KEY")
        use_pinecone = bool(pinecone_key and pinecone_key.strip())

        vectors_to_upsert = []
        for i, chunk in enumerate(chunks):
            embedding = cls.get_embedding(client, chunk)
            chunk_id = f"{abs(hash(title))}_{i}_{int(time.time())}"
            vectors_to_upsert.append({
                "id": chunk_id,
                "values": embedding,
                "metadata": {
                    "title": title,
                    "chunk_index": i,
                    "text": chunk
                }
            })

        if use_pinecone:
            try:
                from pinecone import Pinecone, ServerlessSpec
                pc = Pinecone(api_key=pinecone_key)
                
                # Create index if it does not exist
                active_indexes = [idx.name for idx in pc.list_indexes()]
                if cls.INDEX_NAME not in active_indexes:
                    pc.create_index(
                        name=cls.INDEX_NAME,
                        dimension=cls.DIMENSION,
                        metric="cosine",
                        spec=ServerlessSpec(cloud="aws", region="us-east-1")
                    )
                
                index = pc.Index(cls.INDEX_NAME)
                # Pinecone format: list of (id, vector, metadata)
                records = [(v["id"], v["values"], v["metadata"]) for v in vectors_to_upsert]
                index.upsert(vectors=records)

                return {
                    "status": "success",
                    "storage": "Pinecone Serverless (AWS us-east-1)",
                    "title": title,
                    "chunks_indexed": len(chunks),
                    "redactions_applied": len(redactions),
                    "note": f"Indexed {len(chunks)} chunks in Pinecone cloud vector DB. 0% laptop RAM load."
                }
            except Exception as pe:
                # If Pinecone fails or index is warming up, fall back to SQLite
                print("Pinecone warning, falling back to local zero-RAM store:", pe)

        # Fallback: Store cloud embeddings in SQLite
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        for v in vectors_to_upsert:
            cursor.execute("""
                INSERT OR REPLACE INTO vector_knowledge (id, doc_title, chunk_index, content, embedding_json)
                VALUES (?, ?, ?, ?, ?)
            """, (v["id"], title, v["metadata"]["chunk_index"], v["metadata"]["text"], json.dumps(v["values"])))
        conn.commit()
        conn.close()

        return {
            "status": "success",
            "storage": "Tier 2 Zero-RAM Store (Local SQLite + Cloud Embeddings)",
            "title": title,
            "chunks_indexed": len(chunks),
            "redactions_applied": len(redactions),
            "note": f"Indexed {len(chunks)} chunks with cloud embeddings. (Add PINECONE_API_KEY to .env to route directly to Pinecone Serverless)."
        }

    @classmethod
    def semantic_search(cls, client: genai.Client, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """
        Embeds query using Google Cloud and retrieves top matching knowledge chunks.
        """
        cls.init_local_table()
        query_vector = cls.get_embedding(client, query)
        pinecone_key = os.getenv("PINECONE_API_KEY")

        if pinecone_key and pinecone_key.strip():
            try:
                from pinecone import Pinecone
                pc = Pinecone(api_key=pinecone_key)
                active_indexes = [idx.name for idx in pc.list_indexes()]
                if cls.INDEX_NAME in active_indexes:
                    index = pc.Index(cls.INDEX_NAME)
                    results = index.query(vector=query_vector, top_k=top_k, include_metadata=True)
                    matches = []
                    for match in results.matches:
                        matches.append({
                            "title": match.metadata.get("title", "Untitled"),
                            "score": round(match.score, 4),
                            "content": match.metadata.get("text", "")
                        })
                    return matches
            except Exception as pe:
                print("Pinecone query fallback:", pe)

        # Fallback: Cosine similarity in SQLite
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT id, doc_title, chunk_index, content, embedding_json FROM vector_knowledge")
        rows = cursor.fetchall()
        conn.close()

        if not rows:
            return []

        def cosine_similarity(v1: List[float], v2: List[float]) -> float:
            dot = sum(a * b for a, b in zip(v1, v2))
            norm1 = math.sqrt(sum(a * a for a in v1))
            norm2 = math.sqrt(sum(b * b for b in v2))
            return dot / (norm1 * norm2) if norm1 and norm2 else 0.0

        scored = []
        for row in rows:
            emb = json.loads(row[4])
            score = cosine_similarity(query_vector, emb)
            scored.append({
                "title": row[1],
                "score": round(score, 4),
                "content": row[3]
            })

        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]
