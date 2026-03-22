from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import shutil
from uuid import uuid4

from services.export_package_service import ExportPackageService
from services.onenote_service import OneNoteService


class FakeOneNoteService:
    def __init__(self, pages: list[dict[str, object]]) -> None:
        self._pages = pages
        self.requested_section_ids: list[str] = []

    def get_section_source_items(self, section_id: str) -> list[dict[str, object]]:
        self.requested_section_ids.append(section_id)
        return list(self._pages)


def _local_test_dir(prefix: str) -> Path:
    root = Path(".tmp_test_runs")
    root.mkdir(exist_ok=True)
    path = root / f"{prefix}-{uuid4()}"
    path.mkdir()
    return path


def test_export_package_creates_markdown_images_and_metadata() -> None:
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
    tmp_path = _local_test_dir("export-package")
    try:
        result = service.export_section(
            source_notebook_id="nb-1",
            source_section_id="sec-1",
            source_section_name="Diverse",
            output_root=tmp_path,
        )

        run_root = tmp_path / "run-fixed"
        metadata_path = run_root / "metadata.json"
        markdown_path = run_root / "section_export.md"
        prompt_path = run_root / "import_prompt.md"
        taxonomy_path = run_root / "taxonomy_reference.md"
        quality_path = run_root / "quality_reference.md"
        health_path = run_root / "health_reference.md"
        response_schema_path = run_root / "response_schema.json"
        response_example_path = run_root / "response_example.json"
        images_dir = run_root / "images"

        assert result.export_run_id == "run-fixed"
        assert result.source_notebook_id == "nb-1"
        assert result.source_section_id == "sec-1"
        assert result.exported_at == "2026-03-20T10:00:00Z"
        assert result.exported_page_ids == ["page-1"]
        assert Path(result.export_root) == run_root
        assert markdown_path.exists()
        assert prompt_path.exists()
        assert taxonomy_path.exists()
        assert quality_path.exists()
        assert health_path.exists()
        assert response_schema_path.exists()
        assert response_example_path.exists()
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
        prompt = prompt_path.read_text(encoding="utf-8")
        taxonomy_reference = taxonomy_path.read_text(encoding="utf-8")
        quality_reference = quality_path.read_text(encoding="utf-8")
        health_reference = health_path.read_text(encoding="utf-8")
        response_schema = response_schema_path.read_text(encoding="utf-8")
        response_example = response_example_path.read_text(encoding="utf-8")
        assert "![Schnitt](images/page-1-001.jpg)" in markdown
        assert "![zweites](images/page-1-002.png)" in markdown
        assert '"export_run_id": "run-fixed"' in prompt
        assert '"source_section_id": "sec-1"' in prompt
        assert '"recipes"' in prompt
        assert "section_export.md" in prompt
        assert "Qualität" in prompt
        assert "Krebspatient" in prompt
        assert "Original aus OneNote" in prompt
        assert "response_schema.json" in prompt
        assert "response_example.json" in prompt
        assert "Liefere das Ergebnis bevorzugt als Datei" in prompt
        assert "Dessert" in taxonomy_reference
        assert "Vorspeise" in taxonomy_reference
        assert "Kuchen & Gebaeck" in taxonomy_reference
        assert "Mengenangaben in deutsches Format" in quality_reference
        assert "Pflichtfelder fuer die Zielversion" in quality_reference
        assert "Prostata" in health_reference
        assert "Brustkrebs" in health_reference
        assert '"gesundheitshinweise"' in response_schema
        assert '"schritte"' in response_schema
        assert '"gesundheitshinweise"' in response_example
        assert '"source_page_id": "page-1"' in response_example
        assert (images_dir / "page-1-001.jpg").read_bytes() == b"image-one"
        assert (images_dir / "page-1-002.png").read_bytes() == b"image-two"
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_export_package_uses_page_id_and_ordinal_for_relative_image_paths() -> None:
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
    tmp_path = _local_test_dir("export-paths")
    try:
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
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


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
