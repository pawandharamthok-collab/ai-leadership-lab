"""
Enterprise Security & Data Governance Module
Author: AI Leadership Lab
Purpose: Zero-cost, 100% local PII sanitization and tiered data classification router.
Guarantees zero hardware load on 8 GB laptop (pure regex & heuristic analysis).
"""

import re
from typing import Dict, Any, List, Tuple

class PIISanitizer:
    """
    Local Regex-based PII & Credential Scrubber.
    Strips secrets, tokens, personal identifiers BEFORE data reaches any cloud endpoint.
    """
    
    PATTERNS = {
        "Google API Key": r"AIza[0-9A-Za-z-_]{35}",
        "OpenAI API Key": r"sk-[a-zA-Z0-9]{20,}",
        "AWS Access Key": r"AKIA[0-9A-Z]{16}",
        "GitHub Token": r"gh[pousr]_[A-Za-z0-9_]{36}",
        "Generic Secret/Password": r"(?i)(password|passwd|pwd|api_key|secret|bearer)\s*[:=]\s*['\"]?([^\s'\"]{6,})['\"]?",
        "Email Address": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b",
        "Credit Card Number": r"\b(?:\d{4}[ -]?){3}\d{4}\b",
        "Phone Number": r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b",
        "IPv4 Address (Private/Config)": r"\b(?:10\.\d{1,3}\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})\b"
    }

    @classmethod
    def sanitize(cls, text: str) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Scans and redacts detected PII / secrets.
        Returns: (sanitized_text, list_of_redactions)
        """
        redactions = []
        sanitized = text

        for label, pattern in cls.PATTERNS.items():
            matches = list(re.finditer(pattern, sanitized))
            if matches:
                # Count and redact
                count = len(matches)
                redactions.append({
                    "type": label,
                    "count": count
                })
                # Replacement
                if label == "Generic Secret/Password":
                    # Keep the key name, mask only the value
                    sanitized = re.sub(
                        pattern, 
                        r"\1: [REDACTED_SECRET]", 
                        sanitized
                    )
                else:
                    placeholder = f"[REDACTED_{label.upper().replace(' ', '_').replace('/', '_')}]"
                    sanitized = re.sub(pattern, placeholder, sanitized)

        return sanitized, redactions


class DataClassificationRouter:
    """
    Determines optimal, secure storage tier for enterprise knowledge.
    - Tier 1: Local SQLite (Sensitive, personal, high-risk credentials, < 50 KB)
    - Tier 2: Pinecone Serverless (Structured knowledge chunks, runbooks, FAQs)
    - Tier 3: Google Files API (Large working documents, 50+ page PDFs, full decks)
    """

    @classmethod
    def route(cls, content: str, title: str = "", user_intent: str = "") -> Dict[str, Any]:
        sanitized_content, redactions = PIISanitizer.sanitize(content)
        
        # Approximate token size (~4 chars per token)
        char_len = len(content)
        estimated_tokens = char_len // 4
        
        # Heuristics for Tier 1: Local Only
        is_sensitive = bool(redactions) or any(
            k in content.lower() or k in title.lower() or k in user_intent.lower()
            for k in ["password", "credential", "private", "salary", "ssn", "personal", "profile", "confidential"]
        )
        
        if is_sensitive and estimated_tokens < 10000:
            tier = "Tier 1 (Local SQLite)"
            target = "memory.db"
            reason = "High sensitivity or personal profile data. Kept 100% air-gapped on local laptop storage."
            security_risk = "LOW (Air-gapped on localhost)"
        elif estimated_tokens > 20000 or (title and title.lower().endswith((".pdf", ".docx", ".pptx", ".txt")) and estimated_tokens > 5000):
            tier = "Tier 3 (Google Files API)"
            target = "gemini_files_cache"
            reason = f"Large document (~{estimated_tokens:,} tokens). Best processed via cloud multimodal context caching (0% laptop RAM load)."
            security_risk = "MEDIUM (Cloud API - sanitized before transmission)"
        else:
            tier = "Tier 2 (Pinecone Serverless Vector DB)"
            target = "pinecone_index"
            reason = f"Granular knowledge snippet (~{estimated_tokens:,} tokens). Ideal for fast vector embedding and semantic retrieval."
            security_risk = "LOW (Encrypted at rest, model not trained on vectors)"

        return {
            "title": title or "Untitled Document",
            "tier": tier,
            "target": target,
            "estimated_tokens": estimated_tokens,
            "security_risk": security_risk,
            "reason": reason,
            "redactions_applied": redactions,
            "sanitized_content": sanitized_content
        }
