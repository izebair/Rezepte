from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from .contracts import ExportRunContext


class ExportPackageService:
    def __init__(
        self,
        onenote_service: Any,
        *,
        run_id_factory: Callable[[], str] | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._onenote_service = onenote_service
        self._run_id_factory = run_id_factory or (lambda: str(uuid4()))
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def export_section(
        self,
        *,
        source_notebook_id: str,
        source_section_id: str,
        source_section_name: str,
        output_root: str | Path,
    ) -> ExportRunContext:
        export_run_id = self._run_id_factory()
        exported_at = self._format_timestamp(self._clock())
        run_root = Path(output_root) / export_run_id
        images_root = run_root / "images"
        run_root.mkdir(parents=True, exist_ok=True)
        images_root.mkdir(parents=True, exist_ok=True)

        source_items = self._onenote_service.get_section_source_items(source_section_id)
        exported_page_ids = [str(item.get("id") or "").strip() for item in source_items if str(item.get("id") or "").strip()]

        markdown = self._build_markdown(source_section_name, source_items, images_root)
        (run_root / "section_export.md").write_text(markdown, encoding="utf-8")
        (run_root / "import_prompt.md").write_text(
            self._build_import_prompt(
                export_run_id=export_run_id,
                source_section_id=source_section_id,
                exported_at=exported_at,
                source_section_name=source_section_name,
            ),
            encoding="utf-8",
        )

        metadata = {
            "export_run_id": export_run_id,
            "exported_at": exported_at,
            "exported_page_ids": exported_page_ids,
            "source_notebook_id": source_notebook_id,
            "source_section_id": source_section_id,
        }
        (run_root / "metadata.json").write_text(
            json.dumps(metadata, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        return ExportRunContext(
            export_run_id=export_run_id,
            source_notebook_id=source_notebook_id,
            source_section_id=source_section_id,
            source_section_name=source_section_name,
            exported_at=exported_at,
            export_root=str(run_root),
            exported_page_ids=exported_page_ids,
        )

    def _build_markdown(self, section_name: str, source_items: list[dict[str, Any]], images_root: Path) -> str:
        blocks = [f"# Abschnittsexport: {section_name}"]
        for item in source_items:
            page_id = str(item.get("id") or "").strip()
            title = str(item.get("title") or "").strip() or page_id or "Ohne Titel"
            text = str(item.get("text") or "").strip()
            blocks.extend(
                [
                    "",
                    f"## {title}",
                    "",
                    f"- source_page_id: {page_id}",
                ]
            )
            if text:
                blocks.extend(["", text])
            media = item.get("media")
            if isinstance(media, list):
                image_lines = self._export_media(page_id, media, images_root)
                if image_lines:
                    blocks.extend(["", "### Bilder", "", *image_lines])
            blocks.extend(["", "---"])
        return "\n".join(blocks).strip() + "\n"

    def _export_media(self, page_id: str, media_items: list[dict[str, Any]], images_root: Path) -> list[str]:
        image_lines: list[str] = []
        image_index = 0
        for media in media_items:
            if str(media.get("type") or "").strip().lower() != "image":
                continue
            content = media.get("bytes")
            if not isinstance(content, (bytes, bytearray)):
                continue
            image_index += 1
            suffix = self._normalized_suffix(str(media.get("name") or ""))
            filename = f"{page_id}-{image_index:03d}{suffix}"
            (images_root / filename).write_bytes(bytes(content))
            caption = str(media.get("caption") or "").strip()
            alt_text = caption or Path(str(media.get("name") or filename)).stem
            image_lines.append(f"![{alt_text}](images/{filename})")
        return image_lines

    def _normalized_suffix(self, filename: str) -> str:
        suffix = Path(filename).suffix.lower()
        if suffix:
            return suffix
        return ".bin"

    def _build_import_prompt(
        self,
        *,
        export_run_id: str,
        source_section_id: str,
        exported_at: str,
        source_section_name: str,
    ) -> str:
        schema_example = {
            "export_run_id": export_run_id,
            "source_section_id": source_section_id,
            "exported_at": exported_at,
            "recipes": [
                {
                    "source_page_id": "page-1",
                    "title": "Beispielrezept",
                    "target_main_category": "Dessert",
                    "target_subcategory": "Kuchen",
                    "zutaten": [],
                    "zubereitung": "",
                    "images": ["images/page-1-001.jpg"],
                }
            ],
        }
        schema_text = json.dumps(schema_example, indent=2, ensure_ascii=False)
        return (
            f"# Aufbereitung für Abschnitt: {source_section_name}\n\n"
            "Nutze `section_export.md` als Primärquelle und die referenzierten Dateien im Ordner `images`.\n"
            "Copy every source_page_id exactly from section_export.md. Do not invent placeholder IDs like `page-1`.\n"
            "Liefere als Antwort nur ein gültiges JSON im folgenden Format zurück.\n\n"
            "```json\n"
            f"{schema_text}\n"
            "```\n"
        )

    def _format_timestamp(self, value: datetime) -> str:
        normalized = value.astimezone(timezone.utc).replace(microsecond=0)
        return normalized.isoformat().replace("+00:00", "Z")
