import os
from urllib.parse import urlparse

import httpx


class GeminiProvider:
    def __init__(self) -> None:
        self.api_key = os.getenv("GEMINI_API_KEY")
        self.model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        self.base_url = os.getenv(
            "GOOGLE_API_BASE_URL",
            "https://generativelanguage.googleapis.com",
        )

    def generate_structured(self, prompt: str, system_prompt: str) -> dict:
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY is not configured")

        response = httpx.post(
            f"{self.base_url}/v1beta/models/{self.model}:generateContent",
            params={"key": self.api_key},
            json={
                "systemInstruction": {"parts": [{"text": system_prompt}]},
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.1, "responseMimeType": "application/json"},
            },
            timeout=30,
        )
        response.raise_for_status()
        text = response.json()["candidates"][0]["content"]["parts"][0]["text"]
        import json

        return json.loads(text)

    def search_grounded(self, prompt: str) -> dict:
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY is not configured")

        response = httpx.post(
            f"{self.base_url}/v1beta/models/{self.model}:generateContent",
            params={"key": self.api_key},
            json={
                "systemInstruction": {
                    "parts": [{
                        "text": (
                            "Use Google Search for current information. Prefer official West Bengal government pages. "
                            "Do not give legal advice or claim a requirement applies. Clearly state when official "
                            "information is unavailable."
                        ),
                    }],
                },
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "tools": [{"google_search": {}}],
                "generationConfig": {"temperature": 0.1},
            },
            timeout=30,
        )
        response.raise_for_status()
        candidate = response.json()["candidates"][0]
        answer = " ".join(
            part["text"].strip()
            for part in candidate.get("content", {}).get("parts", [])
            if isinstance(part.get("text"), str) and part["text"].strip()
        )
        metadata = candidate.get("groundingMetadata") or {}
        sources = []
        seen_urls = set()
        for chunk in metadata.get("groundingChunks", []):
            web = chunk.get("web") or {}
            url = web.get("uri") or web.get("url")
            parsed = urlparse(url or "")
            if (
                parsed.scheme != "https"
                or not parsed.hostname
                or not (parsed.hostname == "gov.in" or parsed.hostname.endswith(".gov.in"))
                or url in seen_urls
            ):
                continue
            seen_urls.add(url)
            sources.append({"url": url, "title": web.get("title") or parsed.hostname})
        return {
            "status": "available" if answer and sources else "no_official_citations",
            "answer": answer if sources else "",
            "sources": sources,
            "queries": metadata.get("webSearchQueries", []),
        }
