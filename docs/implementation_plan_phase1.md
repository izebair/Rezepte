# Implementierungsplan Phase 1

## Ziel

Phase 1 soll aus dem bestehenden Import-Skript ein belastbares fachliches Fundament machen, ohne schon die komplette Web-App zu bauen. Wir trennen deshalb zuerst Modell, Taxonomie, Qualitaetslogik und Import-Pipeline sauber heraus.

## Leitprinzipien

- kleine, testbare Schritte
- bestehende CLI nicht unnoetig brechen
- Regeln vor Magie
- Review vor Vollautomation
- Datenmodell zuerst, UI spaeter darauf aufsetzen

## Ziel des ersten Inkrements

Ein erstes Inkrement ist erfolgreich, wenn wir:
- ein internes Rezept-Datenmodell eingefuehrt haben
- feste Haupt- und Unterkategorien erzwingen
- strukturierte und freie Texte in dasselbe Modell ueberfuehren koennen
- erste regelbasierte Qualitaetschecks liefern
- Ergebnisse als Report und Review-Status ausgeben koennen

## Empfohlene Modulstruktur

### 1. `models.py`
Verantwortung:
- Datenklassen oder TypedDicts fuer `Recipe`, `Ingredient`, `Step`, `MediaAsset`, `QualityFinding`, `HealthAssessment`, `ImportRun`

### 2. `taxonomy.py`
Verantwortung:
- Haupt- und Unterkategorien definieren
- Mapping-Regeln fuer alte/freie Kategorien
- Validierung der Taxonomie

### 3. `parsers/structured.py`
Verantwortung:
- bestehendes MVP-Format parsen
- bekannte Felder sicher extrahieren

### 4. `parsers/freeform.py`
Verantwortung:
- freie Texte heuristisch in Rezeptteile zerlegen
- Unsicherheit markieren
- Fallback statt harter Fehler

### 5. `normalization.py`
Verantwortung:
- Mengen und Einheiten normalisieren
- deutsche Formate vereinheitlichen
- Rohwerte und Normalwerte parallel erhalten

### 6. `quality_rules.py`
Verantwortung:
- Pflichtfeldchecks
- Mengen-/Einheitenchecks
- Schrittlogik
- Zeit-/Temperatur-Plausibilitaet
- Medienverlust-Erkennung

### 7. `health_rules.py`
Verantwortung:
- erste vorsichtige Ampellogik
- Ersetzungen und Hinweise
- Disclaimers

### 8. `review.py`
Verantwortung:
- Review-Status ableiten
- Unsicherheit zusammenfassen
- Freigabereife bestimmen

### 9. `sources/onenote.py`
Verantwortung:
- OneNote als Quelle lesen
- Seiten, Medien und Metadaten extrahieren
- spaeter OCR-Einspeisung vorbereiten

### 10. `reporting.py`
Verantwortung:
- Import-Report strukturieren
- Konsole + JSON
- spaeter Anschluss an Review-UI

## Umsetzung in Phasen

## Phase 1A: Fundament im bestehenden CLI-Projekt

### Arbeitspaket A1: Datenmodell einfuehren
- `models.py` anlegen
- bestehende Dict-Strukturen schrittweise abloesen
- Report-Struktur an neues Modell anlehnen

### Arbeitspaket A2: Taxonomie fixieren
- zentrale Listen fuer Haupt- und Unterkategorien
- Mapping fuer bestehende Kategorien
- keine freie Hauptkategorie mehr zulassen

### Arbeitspaket A3: Parser trennen
- strukturierten Parser isolieren
- freien Parser als neuen Pfad vorbereiten
- gemeinsames Ausgabeformat: `Recipe`

### Arbeitspaket A4: erste Qualitaetsregeln
- Pflichtfelder
- Mengen/Einheiten
- Schritte logisch vorhanden
- Zeiten/Temperaturen grob plausibel

### Arbeitspaket A5: Review-Status ableiten
- `extracted`
- `needs_review`
- `approved`
- `rejected`

## Phase 1B: Quellen und OCR vorbereiten

### Arbeitspaket B1: OneNote-Quelle als eigener Layer
- aktuelle OneNote-Ziellogik vom Quellzugriff entkoppeln
- Page-/Attachment-Metadaten modellieren

### Arbeitspaket B2: OCR-Schnittstelle definieren
- noch nicht voll bauen, aber Interface festlegen
- OCR-Text als weitere Quelle einspeisbar machen

### Arbeitspaket B3: Medienreferenzen absichern
- Bilder/PDFs im Modell referenzieren
- Verlust von Medien im Report sichtbar machen

## Phase 1C: Testbarkeit sichern

### Arbeitspaket C1: Modell- und Taxonomie-Tests
- Unit-Tests fuer Datenmodell und Kategorien

### Arbeitspaket C2: Parser-Tests
- strukturierte Rezepte
- freie Texte
- OCR-nahe problematische Texte

### Arbeitspaket C3: Qualitaets- und Review-Tests
- Findings
- Ampellogik
- Review-Status

## Konkrete Reihenfolge fuer die naechste Umsetzung

1. `models.py`
2. `taxonomy.py`
3. `quality_rules.py`
4. `review.py`
5. Umstellung des bestehenden `onenote_import.py` auf das neue Modell
6. Tests fuer Modell, Taxonomie und Regeln
7. danach `freeform`-Parser
8. danach OneNote-Quellzugriff und OCR-Vorbereitung

## Empfohlenes erstes Entwicklungsinkrement

Scope:
- Datenmodell
- Taxonomie
- einfache Qualitaetschecks
- Review-Status
- Tests dafuer

Noch nicht im ersten Inkrement:
- vollwertiger OCR-Flow
- Web-App
- komplexe medizinische Logik
- komplette OneNote-Medienmigration

## Aufgabenverteilung im Team

### Backend / Senior Dev
- Modell, Taxonomie, Regel-Engine, Refactoring des Kernskripts

### QA
- Testmatrix und Unit-Tests fuer Regeln und Statusableitung

### UX/UI
- Review-Zustandslogik und Informationsarchitektur fuer spaetere UI absichern

### BA
- Muss-/Soll-Regeln fuer Qualitaet und Health konkretisieren

### DevOps
- Projektstruktur fuer spaetere App/Services vorbereiten
- reproduzierbares Setup im Blick behalten

### Security
- Guardrails fuer Reports, Quellen, OCR-Artefakte und Health-Hinweise festziehen

## Definition of Done fuer das erste Entwicklungsinkrement

- Rezept-Datenmodell ist im Code verankert
- Taxonomie ist zentral definiert
- mindestens 4 bis 6 Qualitaetsregeln laufen
- Review-Status wird deterministisch gesetzt
- Tests decken Modell, Taxonomie und Regeln ab
- bestehender Dry-Run funktioniert weiter oder besser als vorher
