# OneNote Desktop Migration MVP Design

## Ziel

Wir bauen ein lokales Windows-Produkt mit grafischer Oberflaeche, das OneNote-Seiten als Quelle einliest, einen Testlauf fuer die Migration anzeigt, einzelne Seiten selektieren laesst und die ausgewaehlten Seiten danach in eine neue Zielstruktur in OneNote uebertraegt.

Der erste MVP ist bewusst produktorientiert:

- keine Konsole
- keine lokalen Dateiimporte
- kein manueller Review-Editor
- kein Hosting
- kein Browser-Server-Zwang

Die Qualitaetssicherung erfolgt ueber einen Testlauf mit transparentem Ergebnisreport vor dem eigentlichen Schreiblauf.

## Produktumfang

### In Scope

- Windows-lokale Desktop-App
- OneNote-Anmeldung in der Oberflaeche
- Auswahl von Quellbereich und Zielbereich in OneNote
- Testlauf ohne Schreibzugriff
- Liste aller gefundenen Seiten mit Status und Zielzuordnung
- Abwahl einzelner Seiten vor der echten Migration
- Echte Migration nur fuer ausgewaehlte Seiten
- Automatisches Anlegen der benoetigten Zielstruktur in OneNote
- Sichtbare Ergebnisse fuer importiert, duplikat, fehler, uebersprungen

### Out of Scope

- lokale Bild-, PDF- oder TXT-Importe
- Web-App oder PWA im ersten MVP
- manueller Rezept-Editor
- Freigabe-Workflow mit Review-Queue
- Multi-User-Betrieb
- Hosting oder Self-Hosting
- vertiefte Gesundheitsbewertung als Entscheidungsgate

## Nutzerfluss

### 1. Start

Die App oeffnet mit einem gefuehrten Startbildschirm. Dort sieht der Nutzer:

- OneNote-Anmeldestatus
- Auswahl fuer Quelle
- Auswahl fuer Ziel
- Schaltflaeche fuer Testlauf

### 2. Testlauf

Nach dem Start des Testlaufs liest die App die ausgewaehlten OneNote-Seiten ein und verarbeitet sie mit der bestehenden Parsing-, Taxonomie-, Qualitaets- und Report-Logik, ohne nach OneNote zu schreiben.

Das Ergebnis ist eine Liste mit Eintraegen pro Seite:

- Quellseite
- erkannter Titel
- Ziel-Hauptkategorie
- Ziel-Unterkategorie
- Status
- Fehler- oder Hinweistext
- Duplikatmarkierung
- Auswahlstatus fuer den spaeteren Schreiblauf

### 3. Seitenauswahl

Nach dem Testlauf kann der Nutzer:

- alle Seiten ausgewaehlt lassen
- einzelne Seiten abwaehlen
- alle Seiten auswaehlen oder abwaehlen
- nach Status filtern, zum Beispiel fehlerhaft oder duplikat

Die App migriert spaeter nur Seiten, die im Testlauf sichtbar und aktiv ausgewaehlt sind.

### 4. Migration

Beim Schreiblauf:

- wird die Zielstruktur in OneNote aufgebaut oder wiederverwendet
- werden nur ausgewaehlte und nicht ausgeschlossene Seiten verarbeitet
- werden Duplikate nicht erneut geschrieben
- werden Fehler pro Seite protokolliert, ohne den gesamten Lauf abzubrechen

### 5. Ergebnis

Nach Abschluss zeigt die App:

- Anzahl erfolgreich migrierter Seiten
- Anzahl uebersprungener Seiten
- Anzahl Duplikate
- Anzahl Fehler
- Zielorte in OneNote pro migrierter Seite

## Technische Architektur

## Architekturentscheidung

Der MVP wird als lokale Python-Desktop-App umgesetzt, nicht als Browser-App.

Begruendung:

- keine Konsole und kein lokaler Server fuer den Nutzer
- direkte Wiederverwendung der vorhandenen Python-Fachlogik
- geringerer Integrationsaufwand als eine lokale Web-App
- schnellerer Weg zu einem benutzbaren Windows-Produkt

## Komponenten

### Desktop UI

Verantwortung:

- Anmeldung starten
- Quelle und Ziel auswaehlen
- Testlauf starten
- Seitenliste anzeigen
- Seitenauswahl verwalten
- Schreiblauf starten
- Ergebnis darstellen

### Import Service

Verantwortung:

- zentraler Einstieg fuer Testlauf und Schreiblauf
- gemeinsame Orchestrierung fuer UI und spaeter weiterhin CLI-Kompatibilitaet
- Rueckgabe eines strukturierten Session-Ergebnisses statt nur Konsolenlogik

### OneNote Service

Verantwortung:

- Authentifizierung
- Laden von Notebooks, Abschnittsgruppen, Abschnitten und Seiten
- Abruf von Seiteninhalt
- Anlegen der Zielstruktur
- Schreiben neuer Zielseiten
- Duplikatpruefung

### Migration Session

Verantwortung:

- Haelt Testlauf-Ergebnisse im Speicher
- enthaelt pro Seite die selektierbare Migrationseinheit
- entkoppelt Testlauf und Schreiblauf

### Report Builder

Verantwortung:

- Erzeugt pro Seite ein UI-taugliches Ergebnisobjekt
- liefert Summen und Status
- bereitet Meldungen fuer Ansicht und spaetere Exportfunktion auf

## Datenmodell fuer den MVP

Die bestehende Rezept- und Reportlogik bleibt die fachliche Basis. Fuer die UI kommt ein eigenes Session-Modell dazu.

### MigrationPageCandidate

Pflichtfelder:

- `source_page_id`
- `source_page_title`
- `selected`
- `status`
- `recognized_title`
- `target_main_category`
- `target_subcategory`
- `duplicate`
- `messages[]`
- `fingerprint`

### MigrationSessionResult

Pflichtfelder:

- `session_id`
- `mode` mit `dry_run` oder `execute`
- `source_scope`
- `target_scope`
- `items[]`
- `summary`

## Fehlerbehandlung

- Fehlende Anmeldung blockiert den Lauf vor dem Start.
- Ungueltige Quell- oder Zielauswahl blockiert den Lauf vor dem Start.
- Fehler auf Einzelseitenebene werden gesammelt und sichtbar gemacht.
- Einzelne Seitenfehler beenden den Testlauf nicht.
- Einzelne Schreibfehler beenden die Gesamtmigration nicht.
- Duplikate werden klar markiert und standardmaessig nicht erneut geschrieben.

## Teststrategie

Der MVP stützt sich auf zwei Ebenen:

### 1. Bestehende Fachtests weiter nutzen

Die vorhandenen Tests fuer Parsing, OCR-Metadaten, Review-Logik, Qualitaetsregeln und Report-Zusammenfassungen bleiben der Kern fuer die Fachsicherheit.

### 2. Neue MVP-Akzeptanztests

Es werden gezielt Tests fuer den neuen Produktfluss ergaenzt:

- Testlauf aus OneNote erzeugt sichtbare Seitenliste mit Zielzuordnung
- Abgewaehlte Seiten werden im Schreiblauf nicht migriert
- Zielstruktur wird in OneNote korrekt angelegt oder wiederverwendet
- Duplikate werden erkannt und nicht erneut geschrieben
- Gemischte Laeufe mit gueltigen, fehlerhaften und uebersprungenen Seiten bleiben stabil

## Risiken und Gegenmassnahmen

### Grosse Orchestrierungsdatei

Aktuell liegt viel Fach- und Ablauflogik in `onenote_import.py`.

Gegenmassnahme:

- Orchestrierung in Services aufteilen
- CLI spaeter nur noch als duenne Huellschicht weiterfuehren

### Authentifizierungsfluss ist terminalnah

Die aktuelle OneNote-Anmeldung ist auf das bisherige Skript zugeschnitten.

Gegenmassnahme:

- Auth in eine UI-faehige Serviceschicht auslagern
- Rueckmeldungen fuer Dialoge statt Konsolentext bereitstellen

### Unsichere Seiteninhalte

Nicht jede OneNote-Seite wird robust parsebar sein.

Gegenmassnahme:

- Testlauf vor Schreiblauf verpflichtend
- sichtbare Status- und Fehlerliste
- gezielte Abwahl problematischer Seiten

## Definition of Done fuer den MVP

Der MVP ist erreicht, wenn:

- die App unter Windows ohne Terminal benutzbar ist
- OneNote als Quelle in der Oberflaeche ausgewaehlt werden kann
- ein Testlauf ohne Schreibzugriff moeglich ist
- die Testlauf-Ergebnisse pro Seite sichtbar sind
- Seiten fuer den Schreiblauf abwaehlbar sind
- die Migration nur fuer ausgewaehlte Seiten startet
- die neue Zielstruktur in OneNote angelegt oder wiederverwendet wird
- Ergebnisse pro Seite und als Gesamtsumme sichtbar sind
- die Kernpfade durch automatisierte Tests abgesichert sind
