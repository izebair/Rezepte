from sources.onenote import (
    build_blocks_from_onenote_pages,
    extract_media_refs_from_onenote_html,
    extract_text_from_onenote_html,
    page_to_source_item,
)


HTML_SAMPLE = """
<html>
  <body>
    <h1>Tomatensuppe</h1>
    <p>2 Tomaten</p>
    <p>500 ml Wasser</p>
    <img src="https://example.com/soup.jpg" alt="Suppe" />
    <a href="https://example.com/rezept.pdf">PDF</a>
    <p style="display:none">REZEPTE_IMPORT_ID:abc</p>
    <p>20 Minuten kochen</p>
  </body>
</html>
"""


def test_extract_text_from_onenote_html_removes_hidden_marker():
    text = extract_text_from_onenote_html(HTML_SAMPLE)
    assert "Tomatensuppe" in text
    assert "500 ml Wasser" in text
    assert "REZEPTE_IMPORT_ID" not in text


def test_extract_media_refs_from_onenote_html_reads_images_and_pdfs():
    media = extract_media_refs_from_onenote_html(HTML_SAMPLE)
    assert any(item["type"] == "image" for item in media)
    assert any(item["type"] == "pdf" for item in media)


def test_page_to_source_item_contains_text_and_media():
    item = page_to_source_item({"id": "1", "title": "Tomatensuppe", "content": HTML_SAMPLE})
    assert item["title"] == "Tomatensuppe"
    assert "2 Tomaten" in item["text"]
    assert len(item["media"]) == 2
    assert item["source_type"] == "onenote_page"


def test_build_blocks_from_onenote_pages_prefixes_title_when_needed():
    pages = [{"title": "Tomatensuppe", "content": "<p>2 Tomaten</p><p>Kochen</p>"}]
    blocks = build_blocks_from_onenote_pages(pages)
    assert len(blocks) == 1
    assert blocks[0].startswith("Tomatensuppe")
    assert "2 Tomaten" in blocks[0]
