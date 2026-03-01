# Rezepte -> OneNote Importer

MVP-Tool zum strukturierten Import von Rezepten aus einer TXT-Datei in OneNote.

Routing im MVP:
- `Gruppe` -> OneNote Abschnittsgruppe
- `Kategorie` -> OneNote Abschnitt
- fehlende Gruppe/Abschnitt werden automatisch angelegt

Validierung im MVP:
- Pflichtfelder fehlen -> Rezept wird nicht importiert, Grund steht im Log
- Testlauf ohne Write-Zugriff via `--dry-run`

## Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Konfiguration (`.env`)

```env
REZEPTE_CLIENT_ID=<Azure App Client ID>
REZEPTE_TENANT_ID=<Tenant ID>
# Optional: consumers | organizations | common | volle Authority URL
REZEPTE_AUTHORITY=

REZEPTE_NOTEBOOK=Rezepte
REZEPTE_INPUT_FILE=rezepte.txt
REZEPTE_LOG_LEVEL=INFO
```

## TXT-Format (verpflichtend im MVP)

Rezepte muessen mit `---` getrennt sein. Feldnamen sind fest:

- `Titel:`
- `Gruppe:`
- `Kategorie:`
- `Zutaten:`
- `Zubereitung:`
- optional: `Portionen:`, `Zeit:`, `Schwierigkeit:`

Beispiel:

```txt
Titel: Spaghetti Bolognese
Gruppe: Hauptgerichte
Kategorie: Pasta
Portionen: 4
Zeit: 35 min
Schwierigkeit: Einfach

Zutaten:
- 400 g Spaghetti
- 500 g Hackfleisch

Zubereitung:
1. Zwiebel anbraten.
2. Hackfleisch dazugeben.
3. Sauce koechlen lassen.
---
Titel: Tomatensuppe
Gruppe: Suppen
Kategorie: Klassiker

Zutaten:
- 1 kg Tomaten

Zubereitung:
1. Kochen.
```

## Nutzung

### 1) Parsing prüfen (ohne OneNote-Write)

```bash
python onenote_import.py --dry-run
```

Schnellstart mit Beispieldatei:

```bash
python onenote_import.py --dry-run --input-file rezepte_mvp_beispiel.txt
```

Mit Report-Datei:

```bash
python onenote_import.py --dry-run --input-file rezepte.txt --report-file import_report.json
```

### 2) Import ausführen

```bash
python onenote_import.py
```

Mit benanntem Report:

```bash
python onenote_import.py --input-file rezepte.txt --report-file import_report.json
```

### 3) Duplikate / Import-Metadaten prüfen

```bash
python onenote_import.py --list-import-meta
python onenote_import.py --check-fingerprint <SHA256>
```

## Qualitätssicherung

```bash
python -m pytest -q
```

## Hinweise

- Für OneNote via Graph sind gültige delegierte Berechtigungen nötig (`User.Read`, `Notes.ReadWrite`).
- Bei Tenant-/Lizenz-Problemen können Graph-Fehler auftreten (z. B. fehlende OneDrive/SharePoint-Lizenz).

