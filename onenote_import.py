"""
onenote_import.py
Einfaches Tool: parst Rezepte aus einer Textdatei und erstellt OneNote Seiten via Microsoft Graph.
Device Code Flow (interaktiver Login).
"""

import os
import re
import sys
import argparse
import logging
import json
from typing import List, Dict, Any, cast, Callable
import importlib.util
from analysis import analyze_recipes

if importlib.util.find_spec("dotenv") is not None:
    from dotenv import load_dotenv as _load_dotenv
else:
    def _load_dotenv(*_args: Any, **_kwargs: Any) -> bool:
        return False

load_dotenv: Callable[..., bool] = _load_dotenv

# .env Datei laden
load_dotenv()

logging.basicConfig(level=os.environ.get("REZEPTE_LOG_LEVEL", "INFO"))

# Konfiguration via Umgebungsvariablen (alle erforderlich bei Ausführung)
CLIENT_ID = os.environ.get("REZEPTE_CLIENT_ID")
TENANT_ID = os.environ.get("REZEPTE_TENANT_ID")
# Optional: überschreibt TENANT_ID-basierte Authority. Werte: "consumers", "organizations", "common" oder vollständige URL
AUTHORITY_OVERRIDE = os.environ.get("REZEPTE_AUTHORITY")
STANDARD_ABSCHNITT = os.environ.get("REZEPTE_SECTION")
NOTEBOOK_NAME = os.environ.get("REZEPTE_NOTEBOOK")
INPUT_FILE = os.environ.get("REZEPTE_INPUT_FILE")
CATEGORY_MAPPING = os.environ.get("REZEPTE_CATEGORY_MAPPING", "")
SUBCATEGORY_SEPARATOR = os.environ.get("REZEPTE_SUBCATEGORY_SEPARATOR", "/")
USE_SUBCATEGORY_TITLE_PREFIX = os.environ.get("REZEPTE_SUBCATEGORY_TITLE_PREFIX", "1") not in {"0", "false", "False"}
SIMILARITY_THRESHOLD = float(os.environ.get("REZEPTE_SIMILARITY_THRESHOLD", "0.45"))

# Delegated Graph-Scopes: User.Read wird für /me benötigt; Notes.ReadWrite reicht für OneNote des angemeldeten Benutzers
# (Notes.ReadWrite.All ist meist App Permission oder erfordert Admin-Consent – vermeiden wir hier bewusst)
SCOPES = ["User.Read", "Notes.ReadWrite"]
GRAPH_BASE = "https://graph.microsoft.com/v1.0"


def _normalize_label(value: str | None) -> str:
    return (value or "").strip().lower()


def _parse_category_mapping(raw: str) -> Dict[str, str]:
    """
    Parst Kategorie-Mapping aus Umgebungsvariable.

    Unterstützte Formate:
    - JSON: {"süßes":"Dessert","pasta/vegetarisch":"Pasta"}
    - Kurzformat: "süßes=Dessert; pasta/vegetarisch=Pasta"
    """
    if not raw.strip():
        return {}

    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return {
                _normalize_label(cast(str, k)): cast(str, v).strip()
                for k, v in data.items()
                if str(k).strip() and str(v).strip()
            }
    except Exception:
        pass

    mapping: Dict[str, str] = {}
    for part in raw.split(";"):
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        key = _normalize_label(key)
        value = value.strip()
        if key and value:
            mapping[key] = value
    return mapping


def _resolve_target_section_and_title(rezept: Dict[str, Any], default_section: str, mapping: Dict[str, str], separator: str, use_subcategory_title_prefix: bool) -> tuple[str, str]:
    """
    Leitet aus Kategorie + Mapping den Zielabschnitt und optionalen Seitentitel-Präfix ab.

    Beispiele:
    - Kategorie "Asiatisch/Curry" + Mapping "asiatisch=International" -> Abschnitt "International"
    - Kategorie "Asiatisch/Curry" ohne Mapping -> Abschnitt "Asiatisch"
    - Mit Präfix: Seitentitel "[Curry] <Titel>"
    """
    title = cast(str, rezept.get("titel") or "Rezept")
    category_raw = cast(str, rezept.get("kategorie") or "").strip()
    if not category_raw:
        return default_section, title

    if separator and separator in category_raw:
        top, sub = [p.strip() for p in category_raw.split(separator, 1)]
    else:
        top, sub = category_raw, ""

    section = mapping.get(_normalize_label(category_raw))
    if not section:
        section = mapping.get(_normalize_label(top), top or default_section)

    if sub and use_subcategory_title_prefix:
        title = f"[{sub}] {title}"

    return section, title

def _validate_config(require_graph: bool = True, input_file: str | None = None, **_kwargs: Any) -> None:
    """Validiert erforderliche Konfigurationsvariablen abhängig vom Modus.

    Rückwärtskompatibel für Aufrufe mit Keyword-Argumenten aus älteren/neuen Versionen.
    """
    missing = []

    if not input_file:
        missing.append("REZEPTE_INPUT_FILE/--input-file")

    if require_graph:
        graph_missing = [name for name, value in {
            "REZEPTE_CLIENT_ID": CLIENT_ID,
            # Nur prüfen, wenn keine Authority manuell gesetzt ist
            "REZEPTE_TENANT_ID": (TENANT_ID if not AUTHORITY_OVERRIDE else "ok"),
            "REZEPTE_SECTION": STANDARD_ABSCHNITT,
            "REZEPTE_NOTEBOOK": NOTEBOOK_NAME,
        }.items() if not value]
        missing.extend(graph_missing)

    if missing:
        logging.error("Erforderliche Umgebungsvariablen fehlen: %s", ", ".join(missing))
        raise RuntimeError(f"Umgebungsvariablen erforderlich: {', '.join(missing)}")

# Regex-Patterns für Rezept-Parsing
_CATEGORY_WORDS = r'kategorie'
_INGREDIENTS_WORDS = r'zutaten'
_INSTRUCTIONS_WORDS = r'zubereitung|anleitung'
_PORTIONS_WORDS = r'portionen|servieren'
_TIME_WORDS = r'zeit|dauer|zubereitungszeit'
_DIFFICULTY_WORDS = r'schwierigkeit|schwierigkeitsgrad'
_IMAGES_WORDS = r'bilder|bild|foto|fotos|image|images'
_TITLE_WORDS = r'titel|title'

_HEADER_PATTERN = rf'(?im)^(?:{_CATEGORY_WORDS}|{_INGREDIENTS_WORDS}|{_INSTRUCTIONS_WORDS}|{_PORTIONS_WORDS}|{_TIME_WORDS}|{_DIFFICULTY_WORDS}|{_IMAGES_WORDS})\s*:?\s*$'
_CATEGORY_PATTERN = rf'(?im)^(?:{_CATEGORY_WORDS})\s*:?\s*$'
_INGREDIENTS_PATTERN = rf'(?im)^(?:{_INGREDIENTS_WORDS})\s*:?\s*$'
_INSTRUCTIONS_PATTERN = rf'(?im)^(?:{_INSTRUCTIONS_WORDS})\s*:?\s*$'
_PORTIONS_PATTERN = rf'(?im)^(?:{_PORTIONS_WORDS})\s*:?\s*$'
_TIME_PATTERN = rf'(?im)^(?:{_TIME_WORDS})\s*:?\s*$'
_DIFFICULTY_PATTERN = rf'(?im)^(?:{_DIFFICULTY_WORDS})\s*:?\s*$'
_IMAGES_PATTERN = rf'(?im)^(?:{_IMAGES_WORDS})\s*:?\s*$'
_TITLE_LINE_PATTERN = rf'(?im)^(?:{_TITLE_WORDS})\s*:\s*(.+)$'

def rezepte_aufteilen(text: str) -> List[str]:
    """
    Aufteilen der Rezepte in Blöcke:
    1) Bevorzugt anhand expliziter Titel-Zeilen: "Titel: <Name>" (oder "Title:")
       Jeder solche Eintrag startet einen neuen Rezeptblock.
    2) Fallback: 3+ Leerzeilen zwischen Rezepten.
    """
    # 1) Titelbasierte Aufteilung
    matches = list(re.finditer(_TITLE_LINE_PATTERN, text))
    if matches:
        blocks: List[str] = []
        for i, m in enumerate(matches):
            start = m.start()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            block = text[start:end].strip()
            if block:
                blocks.append(block)
        return blocks

    # 2) Fallback: 3+ Leerzeilen
    teile = [p.strip() for p in re.split(r'(?:\r?\n){3,}', text) if p.strip()]
    return teile

def rezept_parsen(block: str) -> Dict[str, Any]:
    """
    Parst einen Rezeptblock in strukturierte Teile:
      - titel
      - kategorie (optional)
      - zutaten (Liste)
      - schritte (Liste)
      - raw (original)
    """
    def _extract_section(start_regex: str, text: str) -> List[str]:
        """Extrahiert einen Abschnitt zwischen zwei Headern."""
        m = re.search(start_regex, text, re.MULTILINE | re.IGNORECASE)
        if not m:
            return []
        start = m.end()
        next_header = re.search(_HEADER_PATTERN, text[start:], re.MULTILINE)
        end = start + next_header.start() if next_header else len(text)
        sec_text = text[start:end].strip()

        def remove_list_prefix(s: str) -> str:
            s = re.sub(r'^\s*[-\*\u2022]\s+', '', s)
            s = re.sub(r'^\s*\d+[.)]\s+', '', s)
            return s.strip()

        return [remove_list_prefix(l) for l in sec_text.splitlines() if l.strip()]

    zeilen = [l.rstrip() for l in block.splitlines()]
    gesamt = "\n".join(zeilen)

    # Titel-Header bevorzugen
    titel = "Unbekannt"
    m_t = re.search(_TITLE_LINE_PATTERN, gesamt)
    if m_t:
        titel = m_t.group(1).strip()
    else:
        # Fallback: erste nicht-leere Zeile
        titel = next((l for l in zeilen if l.strip()), "Unbekannt").strip()

    # Kategorie extrahieren
    kategorie = None
    m = re.search(_CATEGORY_PATTERN, gesamt, re.MULTILINE)
    if m:
        start = m.end()
        next_header = re.search(_HEADER_PATTERN, gesamt[start:], re.MULTILINE)
        end = start + next_header.start() if next_header else len(gesamt)
        sec = gesamt[start:end].strip()
        for zeile in sec.splitlines():
            if zeile.strip():
                kategorie = zeile.strip()
                break

    # Zutaten und Schritte extrahieren
    zutaten = _extract_section(_INGREDIENTS_PATTERN, gesamt)
    schritte = _extract_section(_INSTRUCTIONS_PATTERN, gesamt)
    bilder_roh = _extract_section(_IMAGES_PATTERN, gesamt)
    # Nur http/https-Links zulassen, damit OneNote sie direkt laden kann
    bilder = [b for b in bilder_roh if re.match(r'^https?://', b.strip(), re.I)]

    # Portionen, Zeit und Schwierigkeit extrahieren
    portionen = ""
    m = re.search(_PORTIONS_PATTERN, gesamt, re.MULTILINE | re.IGNORECASE)
    if m:
        start = m.end()
        next_header = re.search(_HEADER_PATTERN, gesamt[start:], re.MULTILINE)
        end = start + next_header.start() if next_header else len(gesamt)
        for zeile in gesamt[start:end].strip().splitlines():
            if zeile.strip():
                portionen = zeile.strip()
                break
    
    zeit = ""
    m = re.search(_TIME_PATTERN, gesamt, re.MULTILINE | re.IGNORECASE)
    if m:
        start = m.end()
        next_header = re.search(_HEADER_PATTERN, gesamt[start:], re.MULTILINE)
        end = start + next_header.start() if next_header else len(gesamt)
        for zeile in gesamt[start:end].strip().splitlines():
            if zeile.strip():
                zeit = zeile.strip()
                break
    
    schwierigkeit = ""
    m = re.search(_DIFFICULTY_PATTERN, gesamt, re.MULTILINE | re.IGNORECASE)
    if m:
        start = m.end()
        next_header = re.search(_HEADER_PATTERN, gesamt[start:], re.MULTILINE)
        end = start + next_header.start() if next_header else len(gesamt)
        for zeile in gesamt[start:end].strip().splitlines():
            if zeile.strip():
                schwierigkeit = zeile.strip()
                break

    # Fallback: wenn keine expliziten Abschnitte, teile nach Leerzeile
    if not zutaten and not schritte:
        rest = "\n".join(zeilen[1:]).strip()
        if rest:
            chunks = re.split(r'\n\s*\n+', rest)
            if len(chunks) >= 1:
                zutaten = [l.strip() for l in chunks[0].splitlines() if l.strip()]
            if len(chunks) >= 2:
                schritte = [l.strip() for l in chunks[1].splitlines() if l.strip()]

    return {
        "titel": titel,
        "kategorie": kategorie,
        "zutaten": zutaten,
        "schritte": schritte,
        "portionen": portionen,
        "zeit": zeit,
        "schwierigkeit": schwierigkeit,
        "bilder": bilder,
        "raw": block
    }

def rezept_zu_html(rezept: Dict[str, Any]) -> str:
    """
    Konvertiert Rezeptdaten zu OneNote-HTML.
    """
    from bs4 import BeautifulSoup

    titel = rezept.get("titel", "Unbekannt")
    zutaten = rezept.get("zutaten", [])
    schritte = rezept.get("schritte", [])
    portionen = rezept.get("portionen", "")
    zeit = rezept.get("zeit", "")
    schwierigkeit = rezept.get("schwierigkeit", "")
    bilder = rezept.get("bilder", [])

    soup = BeautifulSoup("", "html.parser")
    html = soup.new_tag("div")
    
    h1 = soup.new_tag("h1")
    h1.string = titel
    html.append(h1)

    # Meta-Informationen nach Titel
    meta_parts = []
    if portionen:
        meta_parts.append(f"Portionen: {portionen}")
    if zeit:
        meta_parts.append(f"Zeit: {zeit}")
    if schwierigkeit:
        meta_parts.append(f"Schwierigkeit: {schwierigkeit}")
    
    if meta_parts:
        meta = soup.new_tag("p")
        meta.string = " • ".join(meta_parts)
        html.append(meta)

    if zutaten:
        h2 = soup.new_tag("h2")
        h2.string = "Zutaten"
        html.append(h2)
        ul = soup.new_tag("ul")
        for zutat in zutaten:
            li = soup.new_tag("li")
            li.string = zutat
            ul.append(li)
        html.append(ul)

    if schritte:
        h2 = soup.new_tag("h2")
        h2.string = "Zubereitung"
        html.append(h2)
        ol = soup.new_tag("ol")
        for schritt in schritte:
            li = soup.new_tag("li")
            li.string = schritt
            ol.append(li)
        html.append(ol)

    if bilder:
        h2 = soup.new_tag("h2")
        h2.string = "Bilder"
        html.append(h2)
        for url in bilder:
            img = soup.new_tag("img", src=url)
            img.attrs["style"] = "max-width: 100%; height: auto;"
            html.append(img)

    return str(html)

def anmelden() -> Dict[str, Any]:
    """
    Device Login via Microsoft Graph.
    """
    try:
        import msal
    except Exception as e:
        logging.error("msal-Bibliothek erforderlich: %s", e)
        raise

    # Authority bestimmen: entweder explizit via REZEPTE_AUTHORITY (z.B. "consumers", "organizations", "common" oder vollständige URL)
    # oder Tenant-ID verwenden
    if AUTHORITY_OVERRIDE:
        authority = AUTHORITY_OVERRIDE if AUTHORITY_OVERRIDE.startswith("http") else f"https://login.microsoftonline.com/{AUTHORITY_OVERRIDE}"
    else:
        authority = f"https://login.microsoftonline.com/{TENANT_ID}"

    app = msal.PublicClientApplication(client_id=CLIENT_ID, authority=authority)
    flow = app.initiate_device_flow(scopes=SCOPES)
    
    if "user_code" not in flow:
        raise RuntimeError("Device Flow konnte nicht gestartet werden")

    print(flow["message"])
    result = app.acquire_token_by_device_flow(flow)
    
    if "access_token" not in result:
        raise RuntimeError("Anmeldung fehlgeschlagen: %s" % result.get("error_description", str(result)))
    
    # Token validieren durch test-API-Call
    token = result["access_token"]
    import requests
    headers = {"Authorization": f"Bearer {token}"}

    test_r = requests.get(f"{GRAPH_BASE}/me", headers=headers)

    if test_r.status_code != 200:
        try:
            error_data = test_r.json()
            error_msg = error_data.get("error", {}).get("message", str(error_data))
        except Exception:
            error_msg = test_r.text

        logging.error("Token-API-Fehler: %d - %s", test_r.status_code, error_msg)

        # Zusätzliche Hinweise für häufige Fehlerursachen
        if test_r.status_code in (401, 40001):
            logging.error("Fehler 40001/401: Kein gültiges Authentifizierungstoken gesendet oder Token ungültig.")
            logging.error("Prüfe: Authorization-Header, Token-Typ (Delegated vs Application) und ob das Token frisch ist.")
            logging.error("Du kannst das Token in https://jwt.ms einfügen und prüfen, ob 'scp' oder 'roles' die erwarteten Werte enthält.")

        if test_r.status_code == 403:
            logging.error("Insufficient privileges: Das Token hat nicht die erforderlichen Graph-Berechtigungen.")
            logging.error("Für /me wird 'User.Read' benötigt. Für OneNote: 'Notes.ReadWrite' (delegated).")
            logging.error("Wenn du 'Notes.ReadWrite.All' nutzt, ist meist Admin-Consent nötig – besser 'Notes.ReadWrite' verwenden.")

        logging.error("Kurz: Azure Portal → App registrations → API permissions → Delegated: User.Read und Notes.ReadWrite (Consent erteilen).")
        raise RuntimeError(f"Token-Validierung fehlgeschlagen: {test_r.status_code} {error_msg}")

    logging.info("Token erfolgreich validiert für Benutzer: %s", test_r.json().get("userPrincipalName", "unbekannt"))
    return result

def abschnitt_id_finden(token: str, abschnitt_name: str, notebook_name: str | None = None) -> str:
    """
    Findet oder erstellt einen OneNote-Abschnitt (case-insensitiv).
    """
    import requests
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # Abrufen aller Notizbücher
    try:
        r = requests.get(f"{GRAPH_BASE}/me/onenote/notebooks", headers=headers)
        r.raise_for_status()
    except requests.exceptions.HTTPError as e:
        logging.error("Fehler beim Abrufen von Notebooks: %s", e)
        status = getattr(e.response, "status_code", None)
        body = getattr(e.response, "text", "")
        logging.error("Status Code: %s, Response: %s", status, body)
        # Häufige Ursache: 30121 (kein gültiges SharePoint/OneDrive-Lizenz im Tenant)
        try:
            data = e.response.json()
            code = data.get("error", {}).get("code")
            if code == "30121":
                logging.error("Dieser Fehler (30121) bedeutet oft: Der angemeldete Benutzer/Tenant hat keine gültige SharePoint/OneDrive-Lizenz.")
                logging.error("Optionen: ")
                logging.error(" - Melde dich mit einem M365-Konto an, das OneDrive/SharePoint/OneNote lizenziert hat.")
                logging.error(" - Oder setze REZEPTE_AUTHORITY=consumers in .env, um ein persönliches Microsoft-Konto (MSA) zu verwenden – vorausgesetzt die App ist für persönliche Konten freigegeben.")
        except Exception:
            pass
        raise
    
    notizbuecher = r.json().get("value", [])
    
    if not notizbuecher:
        logging.error("Keine OneNote Notebooks gefunden. Überprüfe dass OneNote aktiviert ist und du berechtigt bist.")
        raise RuntimeError("Keine Notebooks gefunden")

    def normalisieren(s):
        return (s or "").strip().lower()

    ziel_abschnitt_norm = normalisieren(abschnitt_name)
    ziel_notebook_norm = normalisieren(notebook_name)

    # Durchsuche Notizbücher
    for nb in notizbuecher:
        if ziel_notebook_norm and normalisieren(nb.get("displayName")) != ziel_notebook_norm:
            continue
        
        r2 = requests.get(f"{GRAPH_BASE}/me/onenote/notebooks/{nb['id']}/sections", headers=headers)
        r2.raise_for_status()
        
        for sec in r2.json().get("value", []):
            if normalisieren(sec.get("displayName")) == ziel_abschnitt_norm:
                return sec.get("id")

    # Nicht gefunden -> erstelle im Notizbuch
    ziel_nb = None
    if ziel_notebook_norm:
        ziel_nb = next((n for n in notizbuecher if normalisieren(n.get("displayName")) == ziel_notebook_norm), None)
        if not ziel_nb:
            # Versuche, das Notebook anzulegen
            cr_nb = requests.post(f"{GRAPH_BASE}/me/onenote/notebooks", headers={**headers, "Content-Type": "application/json"}, json={"displayName": notebook_name})
            try:
                cr_nb.raise_for_status()
                ziel_nb = cr_nb.json()
                logging.info("Notebook erstellt: %s", ziel_nb.get("displayName"))
            except requests.exceptions.HTTPError as e:
                logging.error("Notebook konnte nicht erstellt werden: %s", e)
                raise RuntimeError(f"Notizbuch nicht gefunden und Erstellung fehlgeschlagen: {notebook_name}")
    else:
        if not notizbuecher:
            raise RuntimeError("Keine Notizbücher in OneNote gefunden.")
        ziel_nb = notizbuecher[0]

    payload = {"displayName": abschnitt_name}
    cr = requests.post(f"{GRAPH_BASE}/me/onenote/notebooks/{ziel_nb['id']}/sections", 
                       headers={**headers, "Content-Type": "application/json"}, 
                       json=payload)
    cr.raise_for_status()
    return cr.json().get("id")

def oneNote_seite_erstellen(token: str, html_inhalt: str, abschnitt_id: str | None = None, page_title: str | None = None) -> Dict[str, Any]:
    """
    Erstellt eine OneNote-Seite mit HTML-Inhalt.

    Hinweis: Beim Senden von application/xhtml+xml erwartet die OneNote-API
    ein vollständiges HTML-Dokument. Wir wrappen deshalb den generierten
    Inhalt (ein <div> mit H1/H2/Listen) in ein minimales HTML-Gerüst.
    """
    import requests

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/xhtml+xml",
    }

    if abschnitt_id:
        url = f"{GRAPH_BASE}/me/onenote/sections/{abschnitt_id}/pages"
    else:
        url = f"{GRAPH_BASE}/me/onenote/pages"

    # Vollständiges Dokument aufbauen. Der Seitentitel kann aus dem ersten <h1>
    # extrahiert werden; ein <title> schadet aber nicht.
    title = page_title or "Rezept"
    full_html = f"""<!DOCTYPE html>
<html>
  <head>
    <meta charset=\"utf-8\" />
    <title>{title}</title>
  </head>
  <body>
    {html_inhalt}
  </body>
</html>"""

    resp = requests.post(url, data=full_html.encode("utf-8"), headers=headers)
    resp.raise_for_status()
    return resp.json()

def main(argv=None):
    category_mapping = _parse_category_mapping(CATEGORY_MAPPING)

    parser = argparse.ArgumentParser(description="Rezepte in OneNote importieren")
    parser.add_argument("--dry-run", action="store_true", help="Nicht auf OneNote API aufrufen; nur parsen")
    parser.add_argument("--analyze-only", action="store_true", help="Nur Rezeptanalyse ausführen und keinen OneNote-Import starten")
    parser.add_argument("--analysis-report", default="analysis_report.json", help="Pfad für Analysebericht (JSON)")
    parser.add_argument("--import-policy", choices=["allow-duplicates", "skip-similar-or-unfit"], default="allow-duplicates", help="Importverhalten bei Analysefunden")
    parser.add_argument("--skip-log", default="skip_log.json", help="Pfad für Skip-Log (JSON)")
    parser.add_argument("--input-file", help="Überschreibt REZEPTE_INPUT_FILE")
    parser.add_argument("--abschnitt-id", help="OneNote-Abschnitt-ID (optional)")
    args = parser.parse_args(argv)

    # Eingabedatei aus .env laden
    eingabedatei = cast(str, args.input_file or INPUT_FILE)
    require_graph = not args.dry_run and not args.analyze_only
    _validate_config(require_graph, eingabedatei)

    if not os.path.isfile(eingabedatei):
        logging.error("Eingabedatei nicht gefunden: %s", eingabedatei)
        sys.exit(2)

    with open(eingabedatei, "r", encoding="utf-8") as f:
        text = f.read()
    
    bloecke = rezepte_aufteilen(text)
    rezepte = [rezept_parsen(b) for b in bloecke]

    analysis_report = analyze_recipes(rezepte, similarity_threshold=SIMILARITY_THRESHOLD)
    try:
        with open(args.analysis_report, "w", encoding="utf-8") as af:
            json.dump(analysis_report, af, ensure_ascii=False, indent=2)
        logging.info("Analysebericht geschrieben: %s", args.analysis_report)
    except Exception as e:
        logging.warning("Analysebericht konnte nicht geschrieben werden: %s", e)

    if args.analyze_only:
        summary = analysis_report.get("summary", {})
        logging.info(
            "Analyse abgeschlossen: %s Rezepte, Ø Score %s, Issues=%s, Warnings=%s",
            summary.get("count", 0),
            summary.get("average_quality_score", 0),
            summary.get("total_issues", 0),
            summary.get("total_warnings", 0),
        )
        return 0

    skip_indices = set()
    skip_reasons: List[Dict[str, Any]] = []
    if args.import_policy == "skip-similar-or-unfit":
        for idx, item in enumerate(analysis_report.get("items", [])):
            if item.get("issues"):
                skip_indices.add(idx)
                skip_reasons.append({"index": idx, "titel": item.get("titel"), "reason": "analysis_issues", "details": item.get("issues", [])})

        # Bei ähnlichen Paaren das zweite Rezept überspringen
        for pair in analysis_report.get("similar_candidates", []):
            idx_b = pair.get("index_b")
            if isinstance(idx_b, int):
                skip_indices.add(idx_b)
                skip_reasons.append({"index": idx_b, "titel": pair.get("titel_b"), "reason": "similar_recipe", "details": pair})

        try:
            with open(args.skip_log, "w", encoding="utf-8") as sf:
                json.dump({"policy": args.import_policy, "skipped": skip_reasons}, sf, ensure_ascii=False, indent=2)
            logging.info("Skip-Log geschrieben: %s", args.skip_log)
        except Exception as e:
            logging.warning("Skip-Log konnte nicht geschrieben werden: %s", e)

    if args.dry_run:
        for idx, r in enumerate(rezepte):
            resolved_section, resolved_title = _resolve_target_section_and_title(
                r,
                cast(str, STANDARD_ABSCHNITT),
                category_mapping,
                SUBCATEGORY_SEPARATOR,
                USE_SUBCATEGORY_TITLE_PREFIX,
            )
            logging.info("Rezept geparst: %s — Kategorie=%s — %d Zutaten, %d Schritte", 
                        r["titel"], r.get("kategorie"), len(r["zutaten"]), len(r["schritte"]))
            will_skip = idx in skip_indices
            logging.info("Ablagevorschau: Abschnitt=%s — Seitentitel=%s — Skip=%s", resolved_section, resolved_title, will_skip)
        return 0

    # Anmelden
    token_res = anmelden()
    token = token_res.get("access_token")
    
    if not isinstance(token, str):
        logging.error("Keine gültiges access_token erhalten")
        return 1

    # Abschnitt-Cache
    abschnitt_cache: Dict[str, str] = {}
    
    for idx, r in enumerate(rezepte):
        if idx in skip_indices:
            logging.warning("Rezept übersprungen (%s): %s", args.import_policy, r.get("titel"))
            continue

        # Zielabschnitt: explizite ID oder per Kategorie
        if args.abschnitt_id:
            abs_id = args.abschnitt_id
            page_title = cast(str, r.get("titel") or "Rezept")
        else:
            abs_name, page_title = _resolve_target_section_and_title(
                r,
                cast(str, STANDARD_ABSCHNITT),
                category_mapping,
                SUBCATEGORY_SEPARATOR,
                USE_SUBCATEGORY_TITLE_PREFIX,
            )
            if abs_name not in abschnitt_cache:
                abschnitt_cache[abs_name] = abschnitt_id_finden(token, abs_name, NOTEBOOK_NAME)
            abs_id = abschnitt_cache[abs_name]

        html = rezept_zu_html(r)
        try:
            resp = oneNote_seite_erstellen(token, html, abs_id, page_title=page_title)
            logging.info("Seite erstellt für %s: %s", r["titel"], resp.get("id"))
        except Exception as e:
            logging.exception("Fehler beim Erstellen der Seite für %s: %s", r["titel"], e)
        
        # Kleines Delay um Throttling (HTTP 429) zu vermeiden
        try:
            import time
            time.sleep(0.4)
        except Exception:
            pass

    return 0

if __name__ == "__main__":
    sys.exit(main())
