from __future__ import annotations

from html import unescape
from typing import Any, Dict, Iterable, List
import re

try:
    from bs4 import BeautifulSoup
except Exception:
    BeautifulSoup = None


WHITESPACE_RE = re.compile(r"\n{3,}")


def extract_text_from_onenote_html(content: str) -> str:
    if not content:
        return ""

    if BeautifulSoup is not None:
        soup = BeautifulSoup(content, "html.parser")
        for hidden in soup.select('[style*="display:none"]'):
            hidden.decompose()
        text = soup.get_text("\n")
    else:
        text = re.sub(r"<[^>]+>", "\n", content)
        text = unescape(text)

    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip() and "REZEPTE_IMPORT_ID:" not in line
    ]
    return "\n".join(lines)


def extract_media_refs_from_onenote_html(content: str) -> List[Dict[str, object]]:
    if not content:
        return []

    media: List[Dict[str, object]] = []

    if BeautifulSoup is not None:
        soup = BeautifulSoup(content, "html.parser")
        for index, img in enumerate(soup.find_all("img"), start=1):
            src = str(img.get("src") or "").strip()
            if src:
                media.append({
                    "media_id": f"image-{index}",
                    "type": "image",
                    "ref": src,
                    "caption": str(img.get("alt") or "").strip(),
                    "ocr_text_ref": "",
                    "ocr_status": "pending",
                    "ocr_confidence": 0.0,
                })
        for index, link in enumerate(soup.find_all("a"), start=1):
            href = str(link.get("href") or "").strip()
            if href.lower().endswith(".pdf"):
                media.append({
                    "media_id": f"pdf-{index}",
                    "type": "pdf",
                    "ref": href,
                    "caption": link.get_text(" ", strip=True),
                    "ocr_text_ref": "",
                    "ocr_status": "pending",
                    "ocr_confidence": 0.0,
                })
        return media

    for index, src in enumerate(re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', content, re.IGNORECASE), start=1):
        media.append({"media_id": f"image-{index}", "type": "image", "ref": src, "caption": "", "ocr_text_ref": "", "ocr_status": "pending", "ocr_confidence": 0.0})
    for index, href in enumerate(re.findall(r'<a[^>]+href=["\']([^"\']+\.pdf)["\']', content, re.IGNORECASE), start=1):
        media.append({"media_id": f"pdf-{index}", "type": "pdf", "ref": href, "caption": "", "ocr_text_ref": "", "ocr_status": "pending", "ocr_confidence": 0.0})
    return media


def page_to_source_item(page: Dict[str, Any]) -> Dict[str, Any]:
    title = str(page.get("title") or "").strip()
    content = str(page.get("content") or "")
    return {
        "id": str(page.get("id") or ""),
        "title": title,
        "text": extract_text_from_onenote_html(content),
        "ocr_text": "",
        "ocr_confidence": 0.0,
        "media": extract_media_refs_from_onenote_html(content),
        "content": content,
    }


def page_to_block(page: Dict[str, Any]) -> str:
    source_item = page_to_source_item(page)
    title = source_item["title"]
    body_text = source_item["text"]
    if title and body_text and not body_text.lower().startswith(title.lower()):
        return f"{title}\n\n{body_text}".strip()
    if title and not body_text:
        return title
    return body_text.strip()


def build_blocks_from_onenote_pages(pages: Iterable[Dict[str, Any]]) -> List[str]:
    blocks: List[str] = []
    for page in pages:
        block = page_to_block(page)
        if block:
            blocks.append(WHITESPACE_RE.sub("\n\n", block).strip())
    return blocks

