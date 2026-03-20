# OneNote Desktop Migration UI Rescue Design

Datum: 2026-03-20
Status: Draft
Owner: Tech Lead

## Kontext

Das aktuelle Desktop-MVP ist fachlich und ergonomisch nicht auf dem Niveau eines benutzbaren Windows-Produkts. Die Hauptprobleme sind:

- irreführender Login-Flow mit unnötigen Buttons
- unklare Arbeitsreihenfolge
- keine Windows-typische linke Fokusführung
- kryptische IDs in der UI
- unklare Trennung zwischen Rohdaten, Aufbereitung und Migration
- Pseudo-Analyse statt eines ehrlichen Aufbereitungs-Workflows
- unzureichendes Vertrauen in `Execute`

Zusätzlich wurde ein früherer funktionierender Schritt entfernt: die externe KI-Aufbereitung von exportierten Rezepten zu strukturierten Feldern. Die bestehende lokale Python-Logik kann diesen Schritt nicht stabil ersetzen. Für das MVP wird daher ein ehrlicher Export-/Reimport-Flow als Kern des Produkts wiederhergestellt.

## Ziel

Die Desktop-App soll als lokales Windows-Produkt einen verständlichen, sicheren und überprüfbaren Workflow bieten:

1. OneNote automatisch beim App-Start anmelden
2. Quelle über eine linke Hierarchie `Notebook -> Abschnitte` auswählen
3. rohe OneNote-Seiten sofort als Liste anzeigen
4. gewählten Abschnitt als Sammeldatei plus Bilder exportieren
5. extern erzeugtes JSON wieder importieren
6. angereicherte Einträge einzeln auswählen oder abwählen
7. alle ausgewählten und vollständig aufbereiteten Einträge gesammelt nach OneNote migrieren

## Nicht-Ziele

- keine eingebaute KI-Aufbereitung im MVP
- keine lokale Modell-Inferenz
- keine Cloud-API-Kostenpflicht im MVP
- kein manueller Review-Editor für Feld-für-Feld-Bearbeitung
- keine Einzelaktion `Jetzt migrieren` pro Zeile
- keine Erklärungstexte wie Confidence, Begründungen oder Unsicherheiten im JSON

## Produktprinzipien

- Die App behauptet nichts, was sie nicht leistet.
- Die Oberfläche folgt einem klaren Windows-nahen Arbeitsfluss mit linkem Fokus.
- Primäre Aktionen erscheinen nur im jeweils sinnvollen Kontext.
- Die Seitenliste bleibt stabil sichtbar und wird über den Workflow hinweg angereichert statt ausgetauscht.
- Kryptische technische IDs werden in der UI nicht angezeigt.
- Migration bleibt eine bewusste Sammelaktion am Ende des Flows.

## Nutzerfluss

### 1. App-Start und Anmeldung

Beim Start beginnt die Microsoft-Anmeldung automatisch. Es gibt keinen `Login`-Button und keinen `Complete Login`-Button als Standardbedienung.

Die erste sichtbare Arbeitsseite ist trotzdem `Quelle wählen`. Wenn Microsoft noch Interaktion benötigt, erscheint dort ein klarer Hinweisbanner.

Falls Microsoft einen Device-Code verlangt:

- der Code wird in einem kopierbaren Feld dargestellt
- es gibt eine Aktion `Code kopieren`
- optional kann eine Aktion `Browser öffnen` angeboten werden

Der Login-Hinweis ist ein Zustand der Seite, kein eigener separater Screen.

### 2. Quelle wählen

Die linke Seitenleiste zeigt:

- kompakten Prozesskontext
- eine Hierarchie `Notebook -> Abschnitte`

Sobald ein Abschnitt gewählt ist, lädt die App die rohen OneNote-Seiten und zeigt sie rechts in einer stabilen Liste.

Vor dem Aufbereitungsschritt enthält die Liste rohe Einträge mit diesen Spalten:

- `Auswahl`
- `Quelle`
- `Ziel`
- `Status`
- `Aktion`

Vor JSON-Import ist der Zustand pro Zeile:

- `Status = Roh`
- `Aktion = Aufbereitung ausstehend`

### 3. Export

Oberhalb der rechten Arbeitsliste befinden sich die kontextbezogenen Hauptaktionen:

- `Abschnitt exportieren`
- `Aufbereitetes JSON importieren`
- später `Migration starten`

`Abschnitt exportieren` erzeugt:

- eine Sammeldatei im Markdown-Format
- einen Bilderordner für die zugehörigen Rezeptbilder

Es wird immer genau eine Sammeldatei pro gewähltem Abschnitt erzeugt.

### 4. Externe Aufbereitung

Die App selbst führt im MVP keine KI-Aufbereitung aus. Stattdessen ist der Produktfluss offen dafür ausgelegt, dass die Sammel-Markdown-Datei extern in einem KI-Tool verarbeitet wird.

Bevorzugtes Format:

- Input an externe Modelle: `Markdown`
- Output zurück an die App: schlankes `JSON`

Das JSON enthält nur die für Migration und Auswahl nötigen Felder. Es enthält bewusst nicht:

- keine Begründungen
- keine Confidence-Felder
- keine Unsicherheitslisten

### 5. JSON-Import

Beim Import wird das JSON gegen ein festes App-Schema validiert.

Nach erfolgreichem Import bleiben dieselben Zeilen in der Liste bestehen, werden aber angereichert:

- Zielpfad
- Migrationsfähigkeit
- Bildreferenzen
- Fehler- oder Fehlstellenstatus

Statuswerte im MVP:

- `Roh`
- `Fehlt noch`
- `Bereit`
- `Duplikat`
- `Fehler`

Wenn keine gültige Zielzuordnung vorliegt, wird dies nutzerfreundlich als `Fehlt noch` dargestellt.

### 6. Auswahl

Die Auswahl muss pro Zeile möglich sein. Das ist Pflichtfunktion.

Erlaubte Interaktionen:

- einzelne Zeile auswählen
- einzelne Zeile abwählen
- Komfortaktion `Alle auswählen`

Nicht vorgesehen:

- prominentes `Select None`
- Einzelaktion `Jetzt migrieren`

### 7. Migration

`Migration starten` verarbeitet ausschließlich:

- aktuell ausgewählte
- vollständig aufbereitete
- nicht blockierte

Einträge gesammelt in einem Lauf.

Die Migration wird als letzte bewusste Hauptaktion angeboten, nicht früher im Ablauf.

## Informationsarchitektur

### Linke Seitenleiste

Die linke Seite enthält:

- App-/Flow-Kontext
- Notebook-Liste
- expandierbare Abschnittsliste

Die linke Seite ist die primäre Navigations- und Fokuszone.

### Rechte Arbeitsfläche

Die rechte Seite enthält:

- kontextbezogene Aktionsleiste
- optionalen Login-Hinweis
- Seitenliste
- spätere Status- und Ergebnisrückmeldungen

### Sichtbare Namensgebung

UI-Labels zeigen nur sprechende Namen:

- Notebook-Namen
- Abschnittsnamen
- Seitentitel

Technische IDs dürfen intern genutzt, aber nicht in sichtbaren Beschriftungen angezeigt werden.

## Bilder

Rezeptbilder werden im MVP:

- separat exportiert
- im JSON referenziert
- beim Import in die neue OneNote-Seite mit übernommen

Die Sammel-Markdown-Datei kann Bildverweise enthalten, aber die Bilder werden nicht vorab per OCR in den Haupttext eingearbeitet.

## Datenmodell für den Aufbereitungsschritt

### Export

Pro gewähltem Abschnitt:

- `section_export.md`
- Ordner mit zugehörigen Bilddateien

### Import

Ein schlankes JSON pro Exportlauf mit Einträgen, die mindestens diese Informationen enthalten:

- Referenz zur Quellseite
- normalisierter Rezepttitel
- Ziel-Hauptkategorie
- Ziel-Unterkategorie
- Bildreferenzen
- migrationsrelevanter Status

Die konkrete Schema-Definition wird im Umsetzungsplan und in den Contracts spezifiziert.

## Fehlerbehandlung

- Fehlgeschlagener Login blockiert Migration, aber nicht die Anzeige der Arbeitsseite.
- Fehlende Microsoft-Bestätigung wird als Hinweisbanner auf `Quelle wählen` dargestellt.
- Ungültiges JSON wird als Importfehler mit klarer Fehlermeldung ausgewiesen.
- Einträge ohne gültige Zielzuordnung erscheinen als `Fehlt noch`.
- Duplikate bleiben sichtbar, aber sind nicht migrierbar.
- `Migration starten` bleibt deaktiviert, bis es mindestens einen ausgewählten und vollständig aufbereiteten Eintrag gibt.

## UX-Leitlinien

- Segoe UI / Windows-nahe Desktop-Anmutung
- klare visuelle Hierarchie mit linker Navigation
- keine überladene Toolbar mit konkurrierenden Primäraktionen
- deutlich erkennbare Primäraktion nur für den aktuellen Schritt
- kopierbare Codes und Texte, wo Nutzer Daten zwischen App und Browser übertragen müssen
- Statusbezeichnungen in nutzerfreundlicher Sprache
- keine Entwicklerbegriffe im Hauptfluss

## Teststrategie

### Produktverhalten

- Auto-Login startet beim App-Start
- `Quelle wählen` bleibt erste Arbeitsseite
- Login-Hinweis erscheint bei ausstehender Microsoft-Bestätigung
- Device-Code ist kopierbar

### Quellauswahl

- Hierarchie `Notebook -> Abschnitte` wird korrekt geladen
- sichtbare Labels enthalten keine IDs
- Auswahl eines Abschnitts lädt rohe OneNote-Seiten

### Export/Import

- Export erzeugt eine Sammel-Markdown-Datei plus Bilderordner
- JSON-Import validiert gegen das App-Schema
- dieselben Rohzeilen werden nach Import angereichert

### Auswahl und Migration

- einzelne Zeilen können ausgewählt und abgewählt werden
- `Alle auswählen` wirkt nur auf zulässige Einträge
- `Migration starten` verarbeitet alle ausgewählten und vollständigen Einträge gesammelt
- unvollständige oder fehlerhafte Einträge bleiben ausgeschlossen

## Empfehlung

Die App wird nicht weiter als scheinbar autonome Aufbereitungs-KI ausgebaut. Stattdessen wird der frühere funktionierende externe KI-Schritt bewusst und produktgerecht in einen ehrlichen Wizard-basierten Desktop-Flow integriert.

Das ist für das MVP:

- verständlicher
- sicherer
- vertrauenswürdiger
- realistischer auf der vorhandenen Hardware
