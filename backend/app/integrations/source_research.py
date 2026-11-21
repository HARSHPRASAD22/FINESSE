import hashlib
import io
import re
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from pypdf import PdfReader
from pypdf.errors import PdfReadError


ALLOWED_SOURCE_HOSTS = {
    "foscos.fssai.gov.in",
    "www.fssai.gov.in",
    "wb.gov.in",
    "labour.wb.gov.in",
    "wbshopsonline.gov.in",
    "udma.wb.gov.in",
    "edistrict.wb.gov.in",
    "gst.gov.in",
    "www.gst.gov.in",
    "india.gov.in",
}
RELEVANT_SITE_LINK = re.compile(
    r"\b(registr(?:ation|y)?|shop|establishment|application|licen[cs]e|forms?|certificate|service|download|document|guideline)\b",
    re.I,
)
DOCUMENT_SUFFIXES = {".pdf", ".doc", ".docx", ".xls", ".xlsx"}
MAX_FORM_DOCUMENT_BYTES = 8 * 1024 * 1024
SOURCE_HEADERS = {
    "Accept": "text/html,application/pdf,application/xhtml+xml,*/*;q=0.8",
    "User-Agent": "Mozilla/5.0 (compatible; PermitPilot/1.0)",
}


def _validate_source_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in ALLOWED_SOURCE_HOSTS:
        raise ValueError("Only allowlisted official HTTPS sources can be captured")


def _get_source_response(url: str, timeout: float) -> httpx.Response:
    target = url
    for _ in range(5):
        _validate_source_url(target)
        for attempt in range(2):
            try:
                response = httpx.get(
                    target,
                    timeout=timeout,
                    follow_redirects=False,
                    headers=SOURCE_HEADERS,
                )
                break
            except httpx.TimeoutException:
                if attempt:
                    raise
                time.sleep(0.25)
        if not response.is_redirect:
            break
        location = response.headers.get("location")
        if not location:
            raise ValueError("Official source returned a redirect without a target")
        target = urljoin(target, location)
    else:
        raise ValueError("Official source exceeded the redirect limit")

    _validate_source_url(str(response.url))
    response.raise_for_status()
    return response


def describe_capture_error(error: Exception) -> str:
    detail = str(error).casefold()
    if isinstance(error, httpx.TimeoutException):
        return "The secure connection timed out after one retry. The official portal may be temporarily unavailable."
    if isinstance(error, httpx.ConnectError) and "unsafe_legacy_renegotiation" in detail:
        return "The portal uses outdated TLS settings. Secure certificate checks were not bypassed."
    if isinstance(error, httpx.ConnectError):
        return "A secure connection to the official portal could not be established."
    if isinstance(error, httpx.HTTPStatusError):
        return f"The official portal returned HTTP {error.response.status_code}."
    if isinstance(error, (ValueError, UnicodeError)):
        return str(error)
    return f"The official source could not be captured ({type(error).__name__})."


def capture_failure_details(error: Exception) -> dict:
    if isinstance(error, httpx.HTTPStatusError):
        status_code = error.response.status_code
        validity_status = "not_found" if status_code in {404, 410} else "unavailable"
        return {"validation_status": validity_status, "http_status": status_code}
    if isinstance(error, httpx.HTTPError):
        return {"validation_status": "unreachable", "http_status": None}
    return {"validation_status": "unavailable", "http_status": None}


def is_official_document_link(link: dict) -> bool:
    parsed = urlparse(link.get("url", ""))
    suffix = parsed.path.casefold().rsplit(".", 1)
    return bool(suffix and len(suffix) == 2 and f".{suffix[-1]}" in DOCUMENT_SUFFIXES)


def capture_source(url: str, timeout: float = 20) -> dict:
    response = _get_source_response(url, timeout)
    soup = BeautifulSoup(response.text, "html.parser")
    for tag in soup(["script", "style", "noshow"]):
        tag.decompose()
    text = " ".join(soup.get_text(" ", strip=True).split())
    title_tag = soup.find("title")
    title = " ".join(title_tag.get_text(" ", strip=True).split()) if title_tag else url
    content_hash = hashlib.sha256(response.content).hexdigest()
    links = []
    for anchor in soup.find_all("a", href=True):
        link = urljoin(str(response.url), anchor["href"])
        parsed_link = urlparse(link)
        label = " ".join(anchor.get_text(" ", strip=True).split()) or anchor.get("title", "").strip()
        if not label and parsed_link.path:
            label = parsed_link.path.rsplit("/", 1)[-1]
        if (
            parsed_link.scheme == "https"
            and parsed_link.hostname in ALLOWED_SOURCE_HOSTS
            and label
        ):
            links.append({"title": label[:200], "url": link})

    return {
        "canonical_url": str(response.url),
        "title": title[:300],
        "content_hash": content_hash,
        "text_excerpt": text[:8000],
        "links": links[:100],
        "status_code": response.status_code,
        "content_type": response.headers.get("content-type", "text/html"),
    }


def capture_official_document(
    url: str,
    timeout: float = 10,
    max_bytes: int = MAX_FORM_DOCUMENT_BYTES,
    cache_directory: Path | None = None,
) -> dict:
    _validate_source_url(url)
    response = _get_source_response(url, timeout)
    content = response.content
    if len(content) > max_bytes:
        raise ValueError(f"Official form document exceeds the {max_bytes // (1024 * 1024)} MB size limit")

    canonical_url = str(response.url)
    path = urlparse(canonical_url).path.casefold()
    suffix_parts = path.rsplit(".", 1)
    suffix = f".{suffix_parts[-1]}" if len(suffix_parts) == 2 else ""
    content_type = response.headers.get("content-type", "").split(";", 1)[0].strip().casefold()
    is_pdf = content_type == "application/pdf" or content.startswith(b"%PDF-")
    if suffix == ".pdf" and not is_pdf:
        raise ValueError("The official PDF link returned a non-PDF response")
    if not is_pdf and suffix not in DOCUMENT_SUFFIXES:
        raise ValueError("The candidate link did not return a supported form document")

    result = {
        "official_url": canonical_url,
        "document_type": "PDF" if is_pdf else suffix.removeprefix(".").upper(),
        "content_type": content_type or "application/octet-stream",
        "byte_size": len(content),
        "content_hash": hashlib.sha256(content).hexdigest(),
        "preview_status": "unsupported_format",
        "page_count": None,
        "text_excerpt": "",
        "fillable_fields": [],
    }
    if not is_pdf:
        return result

    if cache_directory is not None:
        cache_directory.mkdir(parents=True, exist_ok=True)
        cached_path = cache_directory / f"{result['content_hash']}.pdf"
        if not cached_path.exists():
            cached_path.write_bytes(content)
        result["cached_pdf_name"] = cached_path.name

    try:
        reader = PdfReader(io.BytesIO(content), strict=False)
        result["page_count"] = len(reader.pages)
        fields = reader.get_fields() or {}
        result["fillable_fields"] = [
            {
                "name": name,
                "label": str(field.get("/TU") or field.get("/TM") or name)[:200],
                "type": "text",
            }
            for name, field in fields.items()
            if str(field.get("/FT", "")) == "/Tx"
        ][:100]
        extracted = "\n".join(
            page.extract_text() or ""
            for page in reader.pages[:20]
        ).strip()
    except (PdfReadError, OSError, ValueError, TypeError):
        result["preview_status"] = "unreadable"
        return result
    if extracted:
        result["preview_status"] = "available"
        result["text_excerpt"] = extracted[:4000]
    else:
        result["preview_status"] = "no_selectable_text"
    return result


def capture_site_pages(url: str, max_linked_pages: int = 2, timeout: float = 8) -> list[dict]:
    root = capture_source(url, timeout=timeout)
    root_url = root["canonical_url"]
    root_host = urlparse(root_url).hostname
    pages = [{
        "url": root_url,
        "title": root["title"],
        "source": root,
        "depth": 0,
        "parent_url": None,
        "captured": True,
    }]
    if max_linked_pages <= 0:
        return pages
    candidates = []
    seen_urls = {root_url}
    for link in root["links"]:
        parsed = urlparse(link["url"])
        if (
            parsed.scheme != "https"
            or parsed.hostname != root_host
            or parsed.path.casefold().endswith((".pdf", ".doc", ".docx", ".xls", ".xlsx"))
            or not RELEVANT_SITE_LINK.search(f"{link['title']} {link['url']}")
            or link["url"] in seen_urls
        ):
            continue
        seen_urls.add(link["url"])
        candidates.append(link)
        if len(candidates) >= max_linked_pages:
            break

    for link in candidates:
        try:
            source = capture_source(link["url"], timeout=timeout)
        except (httpx.HTTPError, ValueError, UnicodeError) as exc:
            failure_details = capture_failure_details(exc)
            pages.append({
                "url": link["url"],
                "title": link["title"],
                "depth": 1,
                "parent_url": root_url,
                "captured": False,
                "capture_error": describe_capture_error(exc),
                **failure_details,
            })
        else:
            pages.append({
                "url": source["canonical_url"],
                "title": source["title"] or link["title"],
                "source": source,
                "depth": 1,
                "parent_url": root_url,
                "captured": True,
            })
    return pages
