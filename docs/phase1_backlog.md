# Phase-1-Backlog

## Ziel von Phase 1

Phase 1 definiert das fachliche und technische Fundament fuer die spaetere Migration und Web-App. Ziel ist noch nicht die komplette Loesung, sondern ein belastbares Grundmodell, mit dem wir strukturiert weiterbauen koennen.

## Prioritaet P0

### 1. Ziel-Datenmodell fuer Rezepte definieren

Ergebnis:

- ein standardisiertes Rezeptobjekt
- Felder fuer Titel, Hauptkategorie, Unterkategorie, Zutaten, Schritte, Zeiten, Temperaturen, Bilder, Quellen, OCR-Text, Qualitaetshinweise, Gesundheitsbewertung

Akzeptanzkriterien:

- Das Datenmodell deckt strukturierte und unstrukturierte Quellen ab.
- Das Datenmodell kann Bilder und PDFs referenzieren.
- Das Datenmodell kann Review-Status und Unsicherheiten speichern.

### 2. Feste Taxonomie definieren

Ergebnis:

- finale Liste der Hauptkategorien
- erste Version der Unterkategorien
- Mapping-Regeln fuer freie oder bestehende Kategorien

Akzeptanzkriterien:

- Es gibt genau die 5 Hauptkategorien.
- Unterkategorien sind begrenzt und dokumentiert.
- Neue Kategorien werden nicht frei erzeugt.

### 3. Qualitaetskriterien definieren

Ergebnis:

- Pruefregeln fuer Zutaten, Mengen, Schritte, Reihenfolge, Temperaturen, Zeiten
- Definition, wann ein Rezept "gut", "unsicher" oder "problematisch" ist

Akzeptanzkriterien:

- Regeln sind fuer Entwickler und QA testbar beschrieben.
- Es gibt klar definierte Ausgaben fuer Findings und Verbesserungsvorschlaege.

### 4. Gesundheits- und Ampellogik als Anforderung definieren

Ergebnis:

- erste fachliche Definition fuer Prostata- und Brustkrebs-Hinweise
- Ampellogik mit Disclaimern

Akzeptanzkriterien:

- Es ist klar, was Gruen, Gelb und Rot bedeutet.
- Es ist klar, was ein Hinweis leisten darf und was nicht.
- Medizinische Hinweise sind als unterstuetzende Empfehlung markiert.

## Prioritaet P1

### 5. OneNote-Migrationsquelle analysieren

Ergebnis:

- Liste der vorhandenen OneNote-Inhaltstypen
- Beispielsammlungen fuer Text, Bilder, Screenshots und PDFs
- Datenfluss fuer Extraktion

Akzeptanzkriterien:

- Wir wissen, welche Inhalte sicher extrahiert werden koennen.
- Wir kennen die schwierigsten Sonderfaelle.

### 6. OCR- und Medienstrategie definieren

Ergebnis:

- Entscheidung fuer OCR-Pfad
- Entscheidung, wie Bilder/PDFs gespeichert und verknuepft werden

Akzeptanzkriterien:

- OCR ist lokal und ohne laufende Cloudkosten machbar.
- Medienverlust wird minimiert.

### 7. Zielplattform fuer Self-Hosting festlegen

Ergebnis:

- technischer Entscheid fuer Raspberry Pi / Synology / Mischbetrieb
- erste Betriebsarchitektur fuer lokale Web-App

Akzeptanzkriterien:

- iPhone-Zugriff ist eingeplant.
- keine laufenden Hostinggebuehren noetig.

## Prioritaet P2

### 8. Review-Workflow fuer die Web-App definieren

Ergebnis:

- grober Nutzerfluss fuer Import, Pruefung, Korrektur und Freigabe

Akzeptanzkriterien:

- Unsichere Rezepte koennen sichtbar markiert werden.
- Bilder, OCR-Texte und Verbesserungsvorschlaege sind im Review sichtbar.

### 9. Technische Zielarchitektur fuer Phase 2 beschreiben

Ergebnis:

- erste Architektur fuer Backend, Web-UI, Jobs und Datenablage

Akzeptanzkriterien:

- die Architektur passt zu Self-Hosting und privater Nutzung
- Erweiterung Richtung PWA und spaeter iOS bleibt offen

## Erste Arbeitspakete fuers Team

### BA

- Product Brief v1 verfeinern
- Datenmodell und Qualitaetsanforderungen beschreiben
- Ampellogik und Gesundheits-Hinweise fachlich abgrenzen

### UX/UI

- Informationsarchitektur fuer Haupt- und Unterkategorien
- Nutzerfluss fuer Migration und Review
- erste Web-App-Screens und Review-Mockups

### Backend

- Rezeptdatenmodell entwerfen
- Parser-/Normalizer-Pipeline fuer strukturierte und freie Texte skizzieren
- OneNote-Extraktions- und OCR-Schnittstellen vorbereiten

### QA

- Teststrategie fuer Datenmodell, Kategorisierung und Qualitaetschecks
- Beispieltests fuer korrekte / unsichere / fehlerhafte Rezepte

### DevOps

- lokale Zielplattform fuer Self-Hosting skizzieren
- Basis fuer reproduzierbares Setup und spaetere CI definieren

### Security

- Guardrails fuer Secrets, Reports, OCR-Artefakte und Gesundheitsdaten definieren

## Definition of Done fuer Phase 1

- Product Brief abgestimmt
- Datenmodell dokumentiert
- Taxonomie beschlossen
- Qualitaets- und Ampellogik beschrieben
- Zielplattform und OCR-Richtung entschieden
- Phase-2-Umsetzung kann in konkrete Tasks zerlegt werden
