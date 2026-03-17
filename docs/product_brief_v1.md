# Product Brief v1

## Produktname

Rezept-Migration und Qualitaetspruefung

## Zielbild

Das Produkt migriert bestehende Rezepte aus OneNote in eine klare, stabile Struktur, prueft sie qualitativ und macht sie anschliessend ueber eine Web-App mobil und einfach pflegbar.

Kurzfristig bleibt OneNote wichtig, weil dort die bestehenden Rezepte liegen und der mobile Zugriff auf dem iPhone bereits funktioniert. Mittelfristig wird eine Web-App zur zentralen Arbeitsoberflaeche fuer Review, Korrektur und Neuerfassung. Langfristig kann daraus optional eine iOS-App werden.

## Zielnutzer

- Primaer: der Product Owner selbst
- Spaeter optional: weitere private Nutzer im kleinen Kreis

## Problemstatement

Die vorhandenen Rezepte liegen bereits in OneNote, aber in uneinheitlicher Form:

- strukturierter Text
- freier/unstrukturierter Text
- Text mit Bildern
- Screenshots
- angehaengte PDFs

Der aktuelle Importansatz verarbeitet nur klar strukturierten Text. Das reicht fuer eine technische Migration, aber nicht fuer das eigentliche Ziel:

- Rezepte inhaltlich aufbereiten
- in eine feste Struktur bringen
- Bilder nicht verlieren
- Qualitaet verbessern
- gesundheitlich relevante Hinweise sichtbar machen
- spaeter neue Rezepte komfortabel pflegen

## Erfolgsbild

Ein Rezept ist erst dann "gut migriert", wenn es:

- einer festen Haupt- und Unterkategorie zugeordnet ist
- in eine standardisierte Rezeptstruktur ueberfuehrt wurde
- Mengen und Einheiten im deutschen Format vorliegen
- Zutaten, Schritte, Zeiten und Temperaturen plausibel sind
- Bilder oder gleichwertige Medienreferenzen erhalten bleiben
- qualitative Hinweise und Verbesserungen enthaelt
- eine rezeptbezogene Einschaetzung fuer Prostata- und Brustkrebspatienten bietet

## Muss-Anforderungen

### Migration

- Bestehende OneNote-Rezepte muessen gelesen und verarbeitet werden koennen.
- Unstrukturierte Texte muessen moeglichst automatisch in Rezeptstruktur ueberfuehrt werden.
- Bilder, Screenshots und PDFs duerfen nicht verloren gehen.
- OCR muss verfuegbar sein, um Rezeptinhalte aus Screenshots und PDFs zu extrahieren.

### Zielstruktur

- Es gibt nur wenige feste Hauptkategorien:
  - Dessert
  - Getraenke
  - Hauptgericht
  - Snack
  - Vorspeise
- Unterkategorien sind erlaubt, aber sparsam und kontrolliert.
- Das System darf nicht beliebig neue Hauptkategorien erzeugen.

### Qualitaetspruefung

- Zutaten muessen auf Plausibilitaet zum Rezeptnamen und zu Mengen geprueft werden.
- Die Zubereitungsschritte muessen auf Reihenfolge und Logik geprueft werden.
- Zeiten und Temperaturen muessen auf Plausibilitaet geprueft werden.
- Das System soll moegliche Verbesserungen vorschlagen, z. B. Kraeuter, Gewuerze, Ergaenzungen oder Korrekturen.
- Mengen und Einheiten sollen in ein konsistentes deutsches Format ueberfuehrt werden.

### Gesundheits-Hinweise

- Jedes Rezept soll rezeptbezogene Hinweise fuer Prostata- und Brustkrebspatienten erhalten.
- Das System soll Alternativen oder Ersetzungen vorschlagen, wenn Zutaten problematisch erscheinen.
- Das System soll eine Ampel-Einschaetzung liefern:
  - Gruen: gut geeignet
  - Gelb: gelegentlich / mit Anpassungen
  - Rot: eher ungeeignet
- Diese Hinweise muessen klar als unterstuetzende Empfehlung und nicht als medizinische Beratung gekennzeichnet sein.

### Zugriff und Kosten

- Die Loesung muss mobil auf dem iPhone nutzbar sein.
- Die Loesung soll keine laufenden Hostingkosten verursachen.
- Self-Hosting zuhause ist der bevorzugte Weg.
- Eine Web-App ist gegenueber einer nativen iOS-App zunaechst bevorzugt.

## Soll-Anforderungen

- OneNote bleibt in einer Uebergangsphase Quelle und optional Ziel.
- Die Web-App soll spaeter neue Rezepte erfassen, bearbeiten und reviewen koennen.
- Die Web-App soll sich auf dem iPhone wie eine App nutzen lassen, z. B. ueber Home-Screen/PWA.
- Migrationsergebnisse sollen in einem nachvollziehbaren Review-Workflow sichtbar sein.

## Kann-Anforderungen

- spaetere iOS-App
- automatische Bildverbesserung oder Medienersatz
- weitergehende Analyse, z. B. Naehrwert- oder Stilbewertung
- persoenliche Filter, Favoriten oder Suchfunktionen

## Nicht-Ziele fuer Phase 1

- sofortige native iOS-App
- vollautomatische, fehlerfreie medizinische Bewertung ohne menschliches Review
- oeffentliches Hosting
- komplexe Multi-User-Plattform

## Zielarchitektur auf Produktebene

Das Produkt besteht perspektivisch aus vier Schichten:

1. Import
   - OneNote lesen
   - OCR fuer PDFs und Screenshots
   - Medien extrahieren und referenzieren

2. Strukturierung
   - freie Texte in Rezeptobjekte ueberfuehren
   - Kategorien mappen
   - Mengen normalisieren

3. Qualitaets-Engine
   - Plausibilitaetspruefung
   - Verbesserungsvorschlaege
   - Gesundheits-Hinweise

4. Review- und Pflegeoberflaeche
   - Web-App
   - Korrektur und Freigabe
   - spaetere Neuerfassung

## Vorschlag fuer Unterkategorien

### Getraenke

- Cocktails
- Mocktails
- Kaffee
- Tee
- Smoothies und Saefte

### Hauptgericht

- Pasta
- Fleisch
- Fisch
- Vegetarisch
- Vegan
- Auflaeufe
- Suppen und Eintoepfe
- International

### Dessert

- Kuchen und Gebaeck
- Cremes und Pudding
- Eis
- Fruchtdesserts

### Snack

- Herzhaft
- Suess
- Brot und Gebaeck
- Dips und Kleinigkeiten

### Vorspeise

- Salate
- Suppen
- Antipasti und Kleinigkeiten

## Risiken

- Unstrukturierte Rezepte sind schwer robust zu erkennen.
- Bilder, Screenshots und PDFs koennen inhaltlich schwer zuzuordnen sein.
- Gesundheitliche Hinweise brauchen besonders klare Grenzen, Disclaimers und Review.
- OneNote ist als Quellsystem nuetzlich, aber langfristig nicht ideal als Hauptdatenmodell.

## Offene Entscheidungen

- Soll OneNote langfristig nur Quelle/Migrationsziel bleiben oder spaeter komplett abgeloest werden?
- Wo liegt spaeter die "Quelle der Wahrheit": Web-App oder weiterhin OneNote?
- Wie tief soll die medizinisch-ernaehrungsbezogene Bewertung wirklich gehen?
- Welche OCR-Strategie ist fuer das Self-Hosting auf Heimhardware ausreichend?
