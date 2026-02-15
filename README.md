# Rezepte → OneNote Importer

Dieses Projekt automatisiert den Import einer bestehenden Rezeptesammlung (z. B. aus OneNote-Export/Textquellen) in eine saubere OneNote-Struktur über die Microsoft Graph API.

## Zielbild

Die App soll Rezepte:
- aus einer Textquelle zuverlässig parsen,
- analysieren (Titel, Kategorie, Zutaten, Schritte, Metadaten),
- in eine neue OneNote-Struktur einsortieren,
- bei Bedarf neue Abschnitte (und perspektivisch Unterstrukturen) anlegen.

## Aktueller Stand

- Parser für Rezepte mit Unterstützung für Felder wie `Titel`, `Kategorie`, `Zutaten`, `Zubereitung`, `Portionen`, `Zeit`, `Schwierigkeit`, `Bilder`.
- Fallback-Logik für weniger strukturierte Texte.
- OneNote-Import via Device Code Login (MSAL) + Microsoft Graph.
- Automatisches Finden/Anlegen von Notizbuch und Abschnitt.
- `--dry-run` zum Testen ohne API-Schreibzugriff.
- Basis-Tests für Splitting/Parsing.

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
REZEPTE_SECTION=Inbox
REZEPTE_INPUT_FILE=rezepte.txt
REZEPTE_LOG_LEVEL=INFO

# Optional: Kategorie-Routing (JSON oder key=value;key2=value2)
# Beispiel JSON: {"asiatisch":"International","asiatisch/curry":"Currys"}
REZEPTE_CATEGORY_MAPPING=

# Optional: Trenner für Unterkategorie in "Kategorie/Subkategorie"
REZEPTE_SUBCATEGORY_SEPARATOR=/

# Optional: Unterkategorie als Seitentitelpräfix verwenden (1/0)
REZEPTE_SUBCATEGORY_TITLE_PREFIX=1
```

## Nutzung

### 1) Parsing prüfen (ohne OneNote-Write)

```bash
python onenote_import.py --dry-run
```

### 2) Import ausführen

```bash
python onenote_import.py
```

Optional mit fixer Ziel-Section-ID:

```bash
python onenote_import.py --abschnitt-id <SECTION_ID>
```

### Kategorie-Routing (neu)

Die Zielablage kann jetzt über `REZEPTE_CATEGORY_MAPPING` gesteuert werden:

- Wenn ein exaktes Mapping für die volle Kategorie existiert (z. B. `asiatisch/curry`), wird dieses verwendet.
- Sonst wird auf die Hauptkategorie gemappt (z. B. `asiatisch -> International`).
- Ohne Mapping wird die Hauptkategorie direkt als Abschnitt verwendet.
- Optional wird die Unterkategorie im Seitentitel als Präfix ergänzt (`[Curry] ...`).

## KI-Layoutvorgabe für die manuelle Vorprüfung

Wenn Rezepte aktuell per Chatbot geprüft und formatiert werden, sollte der Bot **exakt** dieses Layout ausgeben, damit der Import stabil bleibt:

```text
Titel: <Rezeptname>

Kategorie:
<Hauptkategorie>/<Unterkategorie>

Portionen:
<z. B. 2>

Zeit:
<z. B. 25 Minuten>

Schwierigkeit:
<Einfach|Mittel|Schwer>

Zutaten:
- <Menge + Zutat>
- <Menge + Zutat>

Zubereitung:
1. <Schritt 1>
2. <Schritt 2>
3. <Optional: Verbesserungstipps / Gesundheits-Hinweise als Schritt>

Bilder:
https://...
```

**Wichtig:** Nur die unterstützten Header verwenden (`Titel`, `Kategorie`, `Portionen`, `Zeit`, `Schwierigkeit`, `Zutaten`, `Zubereitung`, `Bilder`).

## Qualitätssicherung

```bash
pytest -q
```

## Ergebnis des Reviews / Auffälligkeiten

- **Behoben:** Test-Suite konnte das Hauptmodul nicht importieren (`ModuleNotFoundError`).
  - Lösung: `tests/conftest.py` ergänzt, um das Repo-Root sauber zum Python-Pfad hinzuzufügen.
- **Behoben:** Rückgabecode von `main()` wurde beim CLI-Start nicht an den Prozess weitergegeben.
  - Lösung: `sys.exit(main())` im Entrypoint.

## Nächste sinnvolle Schritte

1. **Struktur-Engine für Zielablage**
   - Regelwerk für `Kategorie -> Abschnitt` und optional `Unterkategorie -> Unterabschnitt/Seitenpräfix`.
2. **Analyse-Schicht**
   - Erkennung von Dubletten (ähnlicher Titel + Zutaten-Overlap).
   - Qualitätschecks: fehlende Zutaten/Schritte, leere Titel, inkonsistente Metadaten.
3. **Idempotenter Import**
   - Wiederholbare Läufe ohne Duplikate (z. B. Hash pro Rezept in Seiten-Metadaten).
4. **Bessere Datenquellen**
   - Direkter OneNote-Export/Import-Connector statt reinem Flat-Text.
5. **Erweiterte Tests**
   - Edge-Cases (gemischte Header, mehrsprachige Labels, fehlerhafte Bild-URLs).
6. **Reporting**
   - Nach jedem Lauf eine Zusammenfassung (neu erstellt, übersprungen, Fehler, Warnungen).

## Hinweise

- Für OneNote via Graph sind gültige delegierte Berechtigungen nötig (`User.Read`, `Notes.ReadWrite`).
- Bei Tenant-/Lizenz-Problemen können Graph-Fehler auftreten (z. B. fehlende OneDrive/SharePoint-Lizenz).
