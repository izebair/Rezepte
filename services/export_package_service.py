from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from health_rules import DISCLAIMER as HEALTH_DISCLAIMER
from health_rules import PROCESSED_MEAT_KEYWORDS, RED_MEAT_KEYWORDS, ALCOHOL_KEYWORDS, PROTECTIVE_KEYWORDS
from quality_rules import build_quality_suggestions
from taxonomy import MAIN_CATEGORIES, SUBCATEGORY_MAP

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
        (run_root / "taxonomy_reference.md").write_text(self._build_taxonomy_reference(), encoding="utf-8")
        (run_root / "quality_reference.md").write_text(self._build_quality_reference(), encoding="utf-8")
        (run_root / "health_reference.md").write_text(self._build_health_reference(), encoding="utf-8")
        (run_root / "response_schema.json").write_text(
            json.dumps(self._build_response_schema(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        (run_root / "response_example.json").write_text(
            json.dumps(
                self._build_response_example(
                    export_run_id=export_run_id,
                    source_section_id=source_section_id,
                    exported_at=exported_at,
                ),
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
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
        schema_text = json.dumps(
            self._build_response_example(
                export_run_id=export_run_id,
                source_section_id=source_section_id,
                exported_at=exported_at,
            ),
            indent=2,
            ensure_ascii=False,
        )
        return (
            f"# Aufbereitung für Abschnitt: {source_section_name}\n\n"
            "Nutze `section_export.md` als Primärquelle und die referenzierten Dateien im Ordner `images`.\n"
            "Lies zusätzlich `taxonomy_reference.md`, `quality_reference.md`, `health_reference.md`, `response_schema.json` und `response_example.json`.\n\n"
            "## Ziel\n\n"
            "Erzeuge pro Quelleintrag eine endgültige, qualitativ verbesserte Rezeptversion in deutscher Sprache.\n"
            "Arbeite Qualitätsverbesserungen direkt in Zutaten und Schritte ein, statt sie nur zu kommentieren.\n"
            "Bewerte jedes Rezept mit Blick auf Krebs- und Gesundheitsaspekte und liefere die Hinweise strukturiert im Feld `gesundheitshinweise`.\n"
            "Der Originaltext bleibt in der App erhalten und wird später unter der Überschrift `Original aus OneNote` ergänzt.\n"
            "Erfinde keine neuen Haupt- oder Unterkategorien außerhalb der Referenzdatei.\n"
            "Übernimm jede `source_page_id` exakt aus `section_export.md`.\n\n"
            "## Ausgabeformat\n\n"
            "Liefere das Ergebnis bevorzugt als Datei im JSON-Format. Falls der Chat keine Datei erzeugen kann, gib nur einen einzigen JSON-Codeblock ohne Begleittext zurück.\n"
            "Die Antwort muss dem Schema in `response_schema.json` entsprechen.\n\n"
            "```json\n"
            f"{schema_text}\n"
            "```\n"
        )

    def _build_taxonomy_reference(self) -> str:
        lines = [
            "# Taxonomie-Referenz",
            "",
            "Verwende ausschließlich diese kontrollierten Haupt- und Unterkategorien.",
            "Neue Hauptkategorien oder freie Mischformen sind nicht erlaubt.",
            "",
        ]
        for main_category in MAIN_CATEGORIES:
            lines.append(f"## {main_category}")
            for subcategory in SUBCATEGORY_MAP.get(main_category, []):
                lines.append(f"- {subcategory}")
            lines.append("")
        return "\n".join(lines).strip() + "\n"

    def _build_quality_reference(self) -> str:
        suggestion_examples = build_quality_suggestions({"zutaten": ["1 Tomate"], "zeit": ""}, [])
        lines = [
            "# Qualitäts-Referenz",
            "",
            "Ziel ist eine endgültige, verbesserte Rezeptversion. Verbesserungen werden direkt eingearbeitet.",
            "",
            "## Pflichtfelder fuer die Zielversion",
            "- Titel",
            "- target_main_category",
            "- target_subcategory",
            "- zutaten als Liste",
            "- schritte als Liste",
            "",
            "## Qualitätsregeln",
            "- Mengenangaben in deutsches Format mit klaren Einheiten überführen.",
            "- Titel, Zutaten und Schritte dürfen nicht leer sein.",
            "- Zubereitungsschritte sollen handlungsorientiert, logisch und vollständig sein.",
            "- Zeit- und Temperaturangaben sollen plausibel und eindeutig sein.",
            "- Unklare oder offensichtlich fehlerhafte Stellen sollen sprachlich bereinigt und präzisiert werden.",
            "- Bilder oder OCR-Hinweise nur berücksichtigen, wenn sie den Rezeptinhalt sinnvoll ergänzen.",
            "",
            "## Beispielhafte Verbesserungsziele",
            *[f"- {entry}" for entry in suggestion_examples],
            "",
        ]
        return "\n".join(lines).strip() + "\n"

    def _build_health_reference(self) -> str:
        lines = [
            "# Gesundheits- und Krebs-Referenz",
            "",
            "Liefere für jede Zielversion kurze, verständliche `gesundheitshinweise` in deutscher Sprache.",
            "Beziehe dich dabei besonders auf Prostata- und Brustkrebspatienten.",
            "",
            "## Hinweise zur Bewertung",
            "- Verarbeitetes Fleisch ist kritisch.",
            f"- Beispiel-Schlagworte verarbeitetes Fleisch: {', '.join(PROCESSED_MEAT_KEYWORDS)}",
            f"- Beispiel-Schlagworte rotes Fleisch: {', '.join(RED_MEAT_KEYWORDS)}",
            f"- Beispiel-Schlagworte Alkohol: {', '.join(ALCOHOL_KEYWORDS)}",
            f"- Eher günstige Zutaten: {', '.join(PROTECTIVE_KEYWORDS)}",
            "",
            "## Form der Hinweise",
            "- Kurz und konkret formulieren.",
            "- Problematische Zutaten benennen und wenn sinnvoll verträgliche Alternativen nennen.",
            f"- Disclaimer sinngemäß beachten: {HEALTH_DISCLAIMER}",
            "",
        ]
        return "\n".join(lines).strip() + "\n"

    def _build_response_schema(self) -> dict[str, Any]:
        return {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "required": ["export_run_id", "source_section_id", "exported_at", "recipes"],
            "properties": {
                "export_run_id": {"type": "string", "minLength": 1},
                "source_section_id": {"type": "string", "minLength": 1},
                "exported_at": {"type": "string", "minLength": 1},
                "recipes": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": [
                            "source_page_id",
                            "title",
                            "target_main_category",
                            "target_subcategory",
                            "zutaten",
                            "schritte",
                            "gesundheitshinweise",
                            "images",
                        ],
                        "properties": {
                            "source_page_id": {"type": "string", "minLength": 1},
                            "title": {"type": "string", "minLength": 1},
                            "target_main_category": {"type": "string", "minLength": 1},
                            "target_subcategory": {"type": "string", "minLength": 1},
                            "zutaten": {"type": "array", "items": {"type": "string"}},
                            "schritte": {"type": "array", "items": {"type": "string"}},
                            "gesundheitshinweise": {"type": "array", "items": {"type": "string"}},
                            "images": {"type": "array", "items": {"type": "string"}},
                        },
                        "additionalProperties": True,
                    },
                },
            },
            "additionalProperties": False,
        }

    def _build_response_example(self, *, export_run_id: str, source_section_id: str, exported_at: str) -> dict[str, Any]:
        return {
            "export_run_id": export_run_id,
            "source_section_id": source_section_id,
            "exported_at": exported_at,
            "recipes": [
                {
                    "source_page_id": "page-1",
                    "title": "Beispielrezept",
                    "target_main_category": "Dessert",
                    "target_subcategory": "Kuchen & Gebaeck",
                    "zutaten": ["250 g Mehl", "2 Eier"],
                    "schritte": ["Backofen vorheizen.", "Teig verrühren und backen."],
                    "gesundheitshinweise": [
                        "Für Krebspatienten nur gelegentlich geeignet, da das Rezept zuckerreich ist.",
                        "Zucker kann bei Bedarf reduziert werden."
                    ],
                    "images": ["images/page-1-001.jpg"],
                }
            ],
        }

    def _format_timestamp(self, value: datetime) -> str:
        normalized = value.astimezone(timezone.utc).replace(microsecond=0)
        return normalized.isoformat().replace("+00:00", "Z")
