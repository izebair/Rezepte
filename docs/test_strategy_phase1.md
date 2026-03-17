# Teststrategie Phase 1

## Ziel

Phase 1 testet das fachliche Fundament: Datenmodell, Taxonomie, Qualitaetschecks, Gesundheitsampel und Review-Status.

## Testbereiche

### 1. Datenmodell

Zu pruefen:
- Pflichtfelder vorhanden
- strukturierte und unstrukturierte Quellen abbildbar
- Medien und OCR referenzierbar
- Review-Status und Unsicherheiten speicherbar

Wichtige Faelle:
- strukturiertes Rezept
- freier Text
- OCR-Extrakt aus Screenshot
- OCR-Extrakt aus PDF

### 2. Taxonomie

Zu pruefen:
- nur 5 Hauptkategorien erlaubt
- Unterkategorien aus kontrollierter Liste
- keine freie Hauptkategorie wird akzeptiert
- mehrdeutige Faelle fuehren zu Review

### 3. Qualitaetschecks

Zu pruefen:
- Titel, Zutaten und Schritte vorhanden
- Mengen und Einheiten plausibel
- deutsches Format fuer Mengen und Einheiten
- Schritte logisch sortiert
- Zeiten und Temperaturen plausibel
- Medienverlust wird erkannt

### 4. Gesundheitsampel

Zu pruefen:
- `green`, `yellow`, `red`, `unrated` sauber unterschieden
- jede Entscheidung hat Gruende
- Disclaimer ist immer vorhanden
- unsichere Faelle werden nicht zu selbstsicher bewertet

### 5. Review-Status

Zu pruefen:
- `extracted`
- `needs_review`
- `approved`
- `rejected`

Regeln:
- unklare Kategorie => `needs_review`
- rote Health-Bewertung => `needs_review`
- hohe Unsicherheit => `needs_review`
- klare, gepruefte Inhalte => `approved`

## Testarten

- Schema-Tests fuer Datenmodell
- Regeltests fuer Taxonomie
- Beispieltests fuer Qualitaetschecks
- Entscheidungslogik-Tests fuer Ampel
- Workflow-Tests fuer Review-Status

## Testdaten

Empfohlen:
- 8 bis 12 Beispielrezepte
- bewusst gemischt:
  - gut strukturiert
  - unstrukturiert
  - OCR-rauschig
  - fehlende Einheiten
  - unklare Kategorie
  - problematische Gesundheitsfaelle

## Erfolgsbedingungen fuer Phase 1

- Datenmodell ist stabil und testbar
- Taxonomie bleibt kontrolliert
- Qualitaetschecks liefern nachvollziehbare Findings
- Ampellogik ist eindeutig und vorsichtig genug
- Review-Status folgt deterministischen Regeln
