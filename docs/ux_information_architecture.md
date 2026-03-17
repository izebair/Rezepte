# UX Information Architecture

## Produktziel

Die Web-App dient zuerst als Review- und Pflegeoberflaeche fuer migrierte Rezepte. Spaeter kommt die Neuerfassung hinzu.

## Hauptnavigation

- `Inbox`
- `Rezepte`
- `Neu`
- `Importe & Reports`
- `Einstellungen`

## Kernscreens

### Inbox

Zentrale Queue fuer:
- `Needs Review`
- `Needs OCR`
- `Invalid`
- `Duplicates`
- `Errors`
- `Ready to Publish`

### Recipe Review

Split View:
- links: Quellen, Bilder, Screenshots, PDFs, OCR-Texte
- mitte: strukturierte Rezeptdaten
- rechts: Findings, Vorschlaege, Gesundheitsampel, Disclaimer

Aktionen:
- `Speichern`
- `Freigeben`
- `Zurueckstellen`
- `Als Duplikat markieren`
- `Ablehnen`

### Recipe Detail

Mobile Leseansicht fuer iPhone:
- grosse Zutatenliste
- klare Schrittansicht
- Bildergalerie
- Health-Hinweise sichtbar aber nicht dominant

### Recipe Editor

Fuer neue Rezepte und spaetere Bearbeitung:
- strukturierte Eingabe
- Medien-Upload
- Inline-Validierung

### Import Run Detail

- Laufzusammenfassung
- Status pro Rezept
- Link in Review
- Report/JSON-Ansicht

## Ziel-Taxonomie

### Hauptkategorien
- `Dessert`
- `Getraenke`
- `Hauptgericht`
- `Snack`
- `Vorspeise`

### Unterkategorien

#### Dessert
- `Kuchen & Gebaeck`
- `Cremes & Pudding`
- `Eis`
- `Frucht`

#### Getraenke
- `Kaffee & Tee`
- `Cocktails & Mocktails`
- `Smoothies & Saefte`

#### Hauptgericht
- `Pasta`
- `Fleisch`
- `Fisch`
- `Vegetarisch`
- `Auflaeufe & Eintoepfe`
- `International`

#### Snack
- `Herzhaft`
- `Suess`
- `Dips & Kleinigkeiten`

#### Vorspeise
- `Salat`
- `Suppe`
- `Antipasti & Kleinigkeiten`

## UX-Prinzipien

- wenige Hauptkategorien, keine freie Kategorie-Explosion
- Tags statt tiefer Ordnerstrukturen
- unsichere Inhalte sichtbar markieren
- Review zuerst, Vollautomation spaeter
- mobile Nutzung von Anfang an mitdenken

## Empfohlener Nutzerfluss

1. Import startet
2. Rezepte landen in der Inbox
3. unsichere Rezepte werden im Review geprueft
4. Rezept wird freigegeben oder abgelehnt
5. freigegebene Rezepte erscheinen in der Bibliothek
6. spaeter koennen neue Rezepte direkt ueber `Neu` erstellt werden
