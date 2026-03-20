from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from services.export_package_service import ExportPackageService
from services.onenote_service import OneNoteService


class FakeOneNoteService:
    def __init__(self, pages: list[dict[str, object]]) -> None:
        self._pages = pages
        self.requested_section_ids: list[str] = []

    def get_section_source_items(self, section_id: str) -> list[dict[str, object]]:
        self.requested_section_ids.append(section_id)
        return list(self._pages)


def test_export_package_creates_markdown_images_and_metadata(tmp_path: Path) -> None:
    service = ExportPackageService(
        FakeOneNoteService(
            [
                {
                    "id": "page-1",
                    "title": "Kuchen",
                    "text": "Rohtext\nmit Bild",
                    "media": [
                        {"type": "image", "name": "bild.jpg", "bytes": b"image-one", "caption": "Schnitt"},
                        {"type": "image", "name": "zweites.png", "bytes": b"image-two", "caption": ""},
                    ],
                }
            ]
        ),
        run_id_factory=lambda: "run-fixed",
        clock=lambda: datetime(2026, 3, 20, 10, 0, tzinfo=timezone.utc),
    )

    result = service.export_section(
        source_notebook_id="nb-1",
        source_section_id="sec-1",
        source_section_name="Diverse",
        output_root=tmp_path,
    )

    run_root = tmp_path / "run-fixed"
    metadata_path = run_root / "metadata.json"
    markdown_path = run_root / "section_export.md"
    images_dir = run_root / "images"

    assert result.export_run_id == "run-fixed"
    assert result.source_notebook_id == "nb-1"
    assert result.source_section_id == "sec-1"
    assert result.exported_at == "2026-03-20T10:00:00Z"
    assert result.exported_page_ids == ["page-1"]
    assert Path(result.export_root) == run_root
    assert markdown_path.exists()
    assert images_dir.exists()
    assert metadata_path.exists()
    assert metadata_path.read_text(encoding="utf-8") == (
        '{\n'
        '  "export_run_id": "run-fixed",\n'
        '  "exported_at": "2026-03-20T10:00:00Z",\n'
        '  "exported_page_ids": [\n'
        '    "page-1"\n'
        '  ],\n'
        '  "source_notebook_id": "nb-1",\n'
        '  "source_section_id": "sec-1"\n'
        '}\n'
    )

    markdown = markdown_path.read_text(encoding="utf-8")
    assert "![Schnitt](images/page-1-001.jpg)" in markdown
    assert "![zweites](images/page-1-002.png)" in markdown
    assert (images_dir / "page-1-001.jpg").read_bytes() == b"image-one"
    assert (images_dir / "page-1-002.png").read_bytes() == b"image-two"


def test_export_package_uses_page_id_and_ordinal_for_relative_image_paths(tmp_path: Path) -> None:
    service = ExportPackageService(
        FakeOneNoteService(
            [
                {
                    "id": "page-1",
                    "title": "Erste",
                    "text": "Erster Text",
                    "media": [{"type": "image", "name": "eins.jpg", "bytes": b"one", "caption": "eins"}],
                },
                {
                    "id": "page-2",
                    "title": "Zweite",
                    "text": "Zweiter Text",
                    "media": [{"type": "image", "name": "zwei.jpg", "bytes": b"two", "caption": "zwei"}],
                },
            ]
        ),
        run_id_factory=lambda: "run-two",
        clock=lambda: datetime(2026, 3, 20, 10, 5, tzinfo=timezone.utc),
    )

    result = service.export_section(
        source_notebook_id="nb-1",
        source_section_id="sec-2",
        source_section_name="Backen",
        output_root=tmp_path,
    )

    markdown = Path(result.export_root, "section_export.md").read_text(encoding="utf-8")

    assert "images/page-1-001.jpg" in markdown
    assert "images/page-2-001.jpg" in markdown
    assert markdown.index("images/page-1-001.jpg") < markdown.index("images/page-2-001.jpg")
    assert sorted(path.name for path in Path(result.export_root, "images").iterdir()) == [
        "page-1-001.jpg",
        "page-2-001.jpg",
    ]


def test_onenote_service_can_collect_section_source_items_in_order() -> None:
    service = OneNoteService(token_provider=lambda: "token")
    pages = [{"id": "page-1"}, {"id": "page-2"}]
    calls: list[str] = []

    service.list_pages = lambda section_id: calls.append(section_id) or list(pages)  # type: ignore[method-assign]
    service.get_page_source_item = lambda page: {"id": page["id"], "text": f"text-{page['id']}"}  # type: ignore[method-assign]

    items = service.get_section_source_items("sec-1")

    assert calls == ["sec-1"]
    assert [item["id"] for item in items] == ["page-1", "page-2"]
    assert [item["text"] for item in items] == ["text-page-1", "text-page-2"]
