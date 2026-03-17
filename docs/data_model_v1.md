# Datenmodell v1

## Ziel

Das Datenmodell bildet strukturierte Rezepte, freie Texte, OCR-Ergebnisse, Medien, Review-Status, Qualitaetspruefung und Gesundheits-Hinweise in einer gemeinsamen Struktur ab.

## Kernobjekt Recipe

Pflichtfelder:
- `recipe_id`
- `title`
- `category_main`
- `ingredients[]`
- `steps[]`
- `review.status`
- `uncertainty.overall`

Optionale Felder:
- `category_sub`
- `description`
- `servings`
- `prep_minutes`
- `cook_minutes`
- `total_minutes`
- `temperatures[]`
- `notes`
- `tags[]`

## Identitaet und Herkunft

- `recipe_id`: stabile ID
- `fingerprint`: fuer Dedupe und Idempotenz
- `sources[]`:
  - `type`: `onenote_page` | `text_file` | `ocr_pdf` | `ocr_image` | `manual`
  - `ref`
  - `captured_at`
  - `raw_text`
  - `confidence`

## Taxonomie

`category_main` ist genau einer von:
- `Dessert`
- `Getraenke`
- `Hauptgericht`
- `Snack`
- `Vorspeise`

`category_sub` kommt aus kontrollierten Listen.

`taxonomy_decision` dokumentiert:
- `chosen_by`: `rule` | `user` | `default`
- `candidates[]`
- `notes`

## Zutaten

Jede Zutat ist ein Objekt:
- `name_raw`
- `name_norm`
- `quantity_raw`
- `quantity_norm`
- `unit_raw`
- `unit_norm`
- `preparation`
- `is_optional`
- `notes`

## Schritte

Jeder Schritt ist ein Objekt:
- `order`
- `text_raw`
- `text_norm`
- `duration_minutes`
- `temperature_c`
- `equipment`
- `notes`

## Medien

`media[]` enthaelt:
- `media_id`
- `type`: `image` | `pdf` | `screenshot`
- `ref`
- `checksum`
- `caption`
- `ocr_text_ref`
- `ocr_status`

## Qualitaet

`quality` enthaelt:
- `status`: `ok` | `unsicher` | `problematisch`
- `findings[]`
- `suggestions[]`

Jedes `finding` enthaelt:
- `id`
- `area`: `taxonomy` | `ingredients` | `steps` | `times_temps` | `media` | `health`
- `severity`: `info` | `warning` | `error`
- `certainty`: `low` | `medium` | `high`
- `message`
- `evidence`
- `suggestions[]`
- `requires_review`

## Gesundheits-Hinweise

`health.assessments[]` enthaelt je Zielgruppe:
- `condition`: `prostate_cancer` | `breast_cancer`
- `light`: `green` | `yellow` | `red` | `unrated`
- `certainty`
- `reasons[]`
- `substitutions[]`
- `requires_review`

Zusatz:
- `health.disclaimer`

## Review

`review` enthaelt:
- `status`: `extracted` | `needs_review` | `approved` | `rejected`
- `owner`
- `last_reviewed_at`
- `changelog[]`

## Unsicherheit

`uncertainty` enthaelt:
- `overall`: `low` | `medium` | `high`
- `reasons[]`
- `confidence_by_stage`:
  - `parsing`
  - `taxonomy`
  - `health`
  - `ocr`

## Begleitobjekte

### MediaAsset
- `media_id`
- `type`
- `file_ref`
- `checksum`
- `page_ref`
- `ocr_status`

### OCRExtract
- `ocr_id`
- `media_id`
- `text`
- `confidence`
- `engine`
- `language`

### ImportRun
- `run_id`
- `created_at`
- `mode`
- `stats`
- `items[]`

## Regeln fuer ein gut migriertes Rezept

Ein Rezept gilt erst dann als gut migriert, wenn:
- `review.status = approved`
- `category_main` gesetzt ist
- keine kritischen `error`-Findings in Kernbereichen vorliegen
- `uncertainty.overall` nicht `high` ist
- Medienreferenzen erhalten wurden, wenn die Quelle Medien hatte
