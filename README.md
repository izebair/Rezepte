# Rezepte -> OneNote Migration

Windows-first MVP zum Verschieben von OneNote-Rezepten in die neue Desktop-Migration.

Die primäre Nutzung ist die Desktop-App `app.pyw`. Die CLI bleibt fuer Entwickler- und Automationsfaelle erhalten, ist aber nicht mehr der Hauptpfad.

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

## Nutzung unter Windows

### Primär: Desktop-App starten

```bash
python app.pyw
```

Alternativ kann `app.pyw` direkt per Doppelklick gestartet werden, wenn Python-Dateizuordnungen eingerichtet sind.

Aktueller UI-Flow im Rescue-MVP:

1. App starten, OneNote-Login beginnt automatisch
2. links `Notebook -> Abschnitte` waehlen
3. rohe Seiten werden direkt in der Liste geladen
4. `Abschnitt exportieren`
5. extern erzeugtes JSON ueber `Aufbereitetes JSON importieren` zurueckholen
6. `Bereit`-Eintraege pruefen und gesammelt mit `Migration starten` uebernehmen

Wichtige Hinweise:

- sichtbare technische IDs werden in der UI bewusst ausgeblendet
- der Login-Code wird in einem kopierbaren Feld gezeigt
- vor dem JSON-Import sind Seiten absichtlich noch nicht selektierbar
- `Migration starten` arbeitet gesammelt auf den aktuell ausgewaehlten `Bereit`-Eintraegen

### Sekundär: CLI fuer Entwickler-Automation

Die CLI bleibt fuer schnellen Import, Dry-Runs und Regressionstests nutzbar:

```bash
python onenote_import.py --dry-run --input-file rezepte.txt --report-file import_report.json
python onenote_import.py
python onenote_import.py --list-import-meta
python onenote_import.py --check-fingerprint <SHA256>
```

Fuer OneNote-Dry-Runs aus einer Section:

```bash
python onenote_import.py --dry-run --source-type onenote-section --source-section-id <SECTION_ID>
```

## Windows Build

Fuer ein lokales Windows-Build kann die Desktop-App mit `PyInstaller` gebuendelt werden:

```bash
pyinstaller desktop_app.spec
```

Das Build landet anschliessend unter `dist/desktop_app/`.

### Lokale OCR fuer Bild- und PDF-Dateien

Bild- und PDF-Dateien koennen im Dry-Run oder Importlauf lokal per OCR verarbeitet werden:

```bash
python onenote_import.py --dry-run --ocr --input-file scan.png
python onenote_import.py --dry-run --ocr --input-file scan.pdf
```

Nuetzliche Umgebungsvariablen:

```env
REZEPTE_ENABLE_OCR=1
REZEPTE_OCR_PROVIDER=auto
REZEPTE_TESSERACT_CMD=tesseract
REZEPTE_OCRMYPDF_CMD=ocrmypdf
REZEPTE_OCR_ROOT=
REZEPTE_OCR_TIMEOUT=60
REZEPTE_OCR_MAX_BYTES=26214400
```

Hinweise:
- `auto` nutzt fuer Bilder `tesseract` und fuer PDFs `ocrmypdf`.
- Ohne `--ocr` werden Bild- und PDF-Dateien bewusst abgewiesen.
- Fuer private Nutzung ist `tesseract` der einfachste erste Adapter; `ocrmypdf` ist spaeter besonders fuer Scan-PDFs sinnvoll.
- Reports enthalten nur OCR-Metadaten wie Status und Engine, aber keinen kompletten OCR-Rohtext.


## Qualitätssicherung

```bash
python -m pytest -q
```

## Hinweise

- Für OneNote via Graph sind gültige delegierte Berechtigungen nötig (`User.Read`, `Notes.ReadWrite`).
- Bei Tenant-/Lizenz-Problemen können Graph-Fehler auftreten (z. B. fehlende OneDrive/SharePoint-Lizenz).

