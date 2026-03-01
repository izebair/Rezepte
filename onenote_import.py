"""
Importiert Rezepte aus einer TXT-Datei in OneNote.

MVP-Format pro Rezeptblock (durch '---' getrennt):
  Titel: ...
  Gruppe: ...
  Kategorie: ...
  Portionen: ...            (optional)
  Zeit: ...                 (optional)
  Schwierigkeit: ...        (optional)

  Zutaten:
  - ...

  Zubereitung:
  1. ...
"""

from __future__ import annotations

import argparse
import hashlib
import html
import importlib.util
import json
import logging
import os
import re
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Set, Tuple

def load_dotenv(*args: Any, **kwargs: Any) -> bool:
    if importlib.util.find_spec("dotenv") is None:
        return False
    from dotenv import load_dotenv as _load_dotenv
    return _load_dotenv(*args, **kwargs)

load_dotenv()

logging.basicConfig(level=os.environ.get("REZEPTE_LOG_LEVEL", "INFO"))

CLIENT_ID = os.environ.get("REZEPTE_CLIENT_ID")
TENANT_ID = os.environ.get("REZEPTE_TENANT_ID")
AUTHORITY_OVERRIDE = os.environ.get("REZEPTE_AUTHORITY")
NOTEBOOK_NAME = os.environ.get("REZEPTE_NOTEBOOK")
INPUT_FILE = os.environ.get("REZEPTE_INPUT_FILE")

SCOPES = ["User.Read", "Notes.ReadWrite"]
GRAPH_BASE = "https://graph.microsoft.com/v1.0"
TRANSIENT_HTTP_STATUS = {429, 500, 502, 503, 504}
HTTP_TIMEOUT_SECONDS = 30
MAX_RETRIES = 5
FINGERPRINT_PREFIX = "REZEPTE_IMPORT_ID"
FINGERPRINT_RE = re.compile(rf"{FINGERPRINT_PREFIX}:([0-9a-f]{{64}})")

RECIPE_DELIMITER_RE = re.compile(r"(?m)^\s*---\s*$")
FIELD_RE = re.compile(r"^\s*(Titel|Gruppe|Kategorie|Portionen|Zeit|Schwierigkeit)\s*:\s*(.*?)\s*$")
INGREDIENTS_HEADER_RE = re.compile(r"^\s*Zutaten\s*:\s*$")
STEPS_HEADER_RE = re.compile(r"^\s*Zubereitung\s*:\s*$")
LIST_PREFIX_RE = re.compile(r"^\s*(?:[-*]|\d+[.)])\s+")


def _normalize(value: str | None) -> str:
    return (value or "").strip().lower()


def _validate_config(*, require_graph: bool, input_file: str) -> None:
    missing: List[str] = []

    if not input_file:
        missing.append("REZEPTE_INPUT_FILE (oder --input-file)")

    if require_graph:
        if not NOTEBOOK_NAME:
            missing.append("REZEPTE_NOTEBOOK")
        if not CLIENT_ID:
            missing.append("REZEPTE_CLIENT_ID")
        if not TENANT_ID and not AUTHORITY_OVERRIDE:
            missing.append("REZEPTE_TENANT_ID oder REZEPTE_AUTHORITY")

    if missing:
        raise RuntimeError(f"Fehlende Konfiguration: {', '.join(missing)}")


def rezepte_aufteilen(text: str) -> List[str]:
    parts = [p.strip() for p in RECIPE_DELIMITER_RE.split(text) if p.strip()]
    return parts


def _clean_list_item(line: str) -> str:
    return LIST_PREFIX_RE.sub("", line).strip()


def rezept_parsen(block: str) -> Dict[str, Any]:
    recipe: Dict[str, Any] = {
        "titel": "",
        "gruppe": "",
        "kategorie": "",
        "portionen": "",
        "zeit": "",
        "schwierigkeit": "",
        "zutaten": [],
        "schritte": [],
        "raw": block,
    }

    section: str | None = None
    for raw_line in block.splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            continue

        if INGREDIENTS_HEADER_RE.match(line):
            section = "zutaten"
            continue
        if STEPS_HEADER_RE.match(line):
            section = "schritte"
            continue

        m = FIELD_RE.match(line)
        if m:
            label = m.group(1)
            value = m.group(2).strip()
            if label == "Titel":
                recipe["titel"] = value
            elif label == "Gruppe":
                recipe["gruppe"] = value
            elif label == "Kategorie":
                recipe["kategorie"] = value
            elif label == "Portionen":
                recipe["portionen"] = value
            elif label == "Zeit":
                recipe["zeit"] = value
            elif label == "Schwierigkeit":
                recipe["schwierigkeit"] = value
            continue

        if section == "zutaten":
            item = _clean_list_item(line)
            if item:
                recipe["zutaten"].append(item)
        elif section == "schritte":
            step = _clean_list_item(line)
            if step:
                recipe["schritte"].append(step)

    return recipe


def rezept_validieren(recipe: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    if not str(recipe.get("titel") or "").strip():
        errors.append("Pflichtfeld fehlt: Titel")
    if not str(recipe.get("gruppe") or "").strip():
        errors.append("Pflichtfeld fehlt: Gruppe")
    if not str(recipe.get("kategorie") or "").strip():
        errors.append("Pflichtfeld fehlt: Kategorie")
    if not recipe.get("zutaten"):
        errors.append("Pflichtfeld fehlt: Zutaten")
    if not recipe.get("schritte"):
        errors.append("Pflichtfeld fehlt: Zubereitung")
    return errors


def rezept_fingerprint(recipe: Dict[str, Any]) -> str:
    parts = [
        str(recipe.get("titel") or "").strip().lower(),
        str(recipe.get("gruppe") or "").strip().lower(),
        str(recipe.get("kategorie") or "").strip().lower(),
        "|".join(str(x).strip().lower() for x in recipe.get("zutaten", [])),
        "|".join(str(x).strip().lower() for x in recipe.get("schritte", [])),
    ]
    canonical = "\n".join(parts)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def rezept_zu_html(recipe: Dict[str, Any], fingerprint: str | None = None) -> str:
    title = html.escape(str(recipe.get("titel") or "Rezept"))
    ingredients_html = "".join(
        f"<li>{html.escape(str(ingredient))}</li>" for ingredient in recipe.get("zutaten", [])
    )
    steps_html = "".join(
        f"<li>{html.escape(str(step))}</li>" for step in recipe.get("schritte", [])
    )

    meta_parts: List[str] = []
    if recipe.get("portionen"):
        meta_parts.append(f"Portionen: {recipe['portionen']}")
    if recipe.get("zeit"):
        meta_parts.append(f"Zeit: {recipe['zeit']}")
    if recipe.get("schwierigkeit"):
        meta_parts.append(f"Schwierigkeit: {recipe['schwierigkeit']}")
    meta_html = f"<p>{html.escape(' | '.join(meta_parts))}</p>" if meta_parts else ""

    marker_html = ""
    if fingerprint:
        marker_value = html.escape(f"{FINGERPRINT_PREFIX}:{fingerprint}")
        marker_html = f"<p style=\"display:none;color:transparent;font-size:1px;\">{marker_value}</p>"

    return (
        "<div>"
        f"<h1>{title}</h1>"
        f"{meta_html}"
        "<h2>Zutaten</h2>"
        f"<ul>{ingredients_html}</ul>"
        "<h2>Zubereitung</h2>"
        f"<ol>{steps_html}</ol>"
        f"{marker_html}"
        "</div>"
    )


def anmelden() -> Dict[str, Any]:
    try:
        import msal
    except Exception as exc:
        raise RuntimeError(f"msal nicht verfügbar: {exc}") from exc

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
        raise RuntimeError(f"Anmeldung fehlgeschlagen: {result.get('error_description', result)}")
    return result


def _calculate_retry_delay(attempt: int, response: Any | None = None) -> float:
    retry_after = None
    if response is not None:
        retry_after = response.headers.get("Retry-After")
    if retry_after:
        try:
            return max(0.0, float(retry_after))
        except ValueError:
            pass
    # 1.0, 2.0, 4.0, 8.0 ...
    return min(20.0, 2 ** (attempt - 1))


def _request_with_retry(method: str, url: str, headers: Dict[str, str], **kwargs: Any) -> Any:
    import requests

    last_error: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.request(method, url, headers=headers, timeout=HTTP_TIMEOUT_SECONDS, **kwargs)
            if response.status_code in TRANSIENT_HTTP_STATUS:
                if attempt == MAX_RETRIES:
                    response.raise_for_status()
                delay = _calculate_retry_delay(attempt, response)
                logging.warning(
                    "Temporärer Graph-Fehler %s bei %s %s (Versuch %d/%d). Warte %.1fs und versuche erneut.",
                    response.status_code,
                    method,
                    url,
                    attempt,
                    MAX_RETRIES,
                    delay,
                )
                time.sleep(delay)
                continue

            response.raise_for_status()
            return response
        except requests.exceptions.Timeout as exc:
            last_error = exc
            if attempt == MAX_RETRIES:
                break
            delay = _calculate_retry_delay(attempt)
            logging.warning(
                "Timeout bei %s %s (Versuch %d/%d). Warte %.1fs und versuche erneut.",
                method,
                url,
                attempt,
                MAX_RETRIES,
                delay,
            )
            time.sleep(delay)
        except requests.exceptions.ConnectionError as exc:
            last_error = exc
            if attempt == MAX_RETRIES:
                break
            delay = _calculate_retry_delay(attempt)
            logging.warning(
                "Verbindungsfehler bei %s %s (Versuch %d/%d). Warte %.1fs und versuche erneut.",
                method,
                url,
                attempt,
                MAX_RETRIES,
                delay,
            )
            time.sleep(delay)
        except requests.exceptions.HTTPError as exc:
            last_error = exc
            response = getattr(exc, "response", None)
            status = getattr(response, "status_code", None)
            if status not in TRANSIENT_HTTP_STATUS or attempt == MAX_RETRIES:
                raise
            delay = _calculate_retry_delay(attempt, response)
            logging.warning(
                "HTTP-Fehler %s bei %s %s (Versuch %d/%d). Warte %.1fs und versuche erneut.",
                status,
                method,
                url,
                attempt,
                MAX_RETRIES,
                delay,
            )
            time.sleep(delay)

    if last_error is not None:
        raise last_error
    raise RuntimeError(f"Anfrage fehlgeschlagen ohne verwertbare Fehlermeldung: {method} {url}")


def _graph_get(url: str, headers: Dict[str, str]) -> Dict[str, Any]:
    resp = _request_with_retry("GET", url, headers)
    resp.raise_for_status()
    return resp.json()


def _graph_post(url: str, headers: Dict[str, str], payload: Dict[str, Any]) -> Dict[str, Any]:
    resp = _request_with_retry(
        "POST",
        url,
        {**headers, "Content-Type": "application/json"},
        json=payload,
    )
    resp.raise_for_status()
    return resp.json()


def _graph_get_text(url: str, headers: Dict[str, str]) -> str:
    resp = _request_with_retry("GET", url, headers)
    resp.raise_for_status()
    return resp.text


def _iter_graph_collection(url: str, headers: Dict[str, str]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    next_url: str | None = url
    while next_url:
        data = _graph_get(next_url, headers)
        values = data.get("value", [])
        if isinstance(values, list):
            items.extend([v for v in values if isinstance(v, dict)])
        next_url = data.get("@odata.nextLink")
        if next_url is not None and not isinstance(next_url, str):
            next_url = None
    return items


def notebook_id_finden_oder_erstellen(token: str, notebook_name: str) -> str:
    headers = {"Authorization": f"Bearer {token}"}
    data = _graph_get(f"{GRAPH_BASE}/me/onenote/notebooks", headers)
    notebooks = data.get("value", [])

    for nb in notebooks:
        if _normalize(nb.get("displayName")) == _normalize(notebook_name):
            return str(nb["id"])

    created = _graph_post(f"{GRAPH_BASE}/me/onenote/notebooks", headers, {"displayName": notebook_name})
    logging.info("Notebook erstellt: %s", notebook_name)
    return str(created["id"])


def section_group_id_finden_oder_erstellen(token: str, notebook_id: str, group_name: str) -> str:
    headers = {"Authorization": f"Bearer {token}"}
    data = _graph_get(f"{GRAPH_BASE}/me/onenote/notebooks/{notebook_id}/sectionGroups", headers)
    groups = data.get("value", [])

    for group in groups:
        if _normalize(group.get("displayName")) == _normalize(group_name):
            return str(group["id"])

    created = _graph_post(
        f"{GRAPH_BASE}/me/onenote/notebooks/{notebook_id}/sectionGroups",
        headers,
        {"displayName": group_name},
    )
    logging.info("Abschnittsgruppe erstellt: %s", group_name)
    return str(created["id"])


def section_id_finden_oder_erstellen(token: str, section_group_id: str, section_name: str) -> str:
    headers = {"Authorization": f"Bearer {token}"}
    data = _graph_get(f"{GRAPH_BASE}/me/onenote/sectionGroups/{section_group_id}/sections", headers)
    sections = data.get("value", [])

    for section in sections:
        if _normalize(section.get("displayName")) == _normalize(section_name):
            return str(section["id"])

    created = _graph_post(
        f"{GRAPH_BASE}/me/onenote/sectionGroups/{section_group_id}/sections",
        headers,
        {"displayName": section_name},
    )
    logging.info("Abschnitt erstellt: %s", section_name)
    return str(created["id"])


def _extract_fingerprints(content: str) -> Set[str]:
    return set(FINGERPRINT_RE.findall(content or ""))


def section_fingerprints_laden(token: str, section_id: str) -> Set[str]:
    headers = {"Authorization": f"Bearer {token}"}
    pages = _iter_graph_collection(f"{GRAPH_BASE}/me/onenote/sections/{section_id}/pages?$select=id,title", headers)
    fingerprints: Set[str] = set()
    for page in pages:
        page_id = page.get("id")
        if not isinstance(page_id, str) or not page_id:
            continue
        content = _graph_get_text(f"{GRAPH_BASE}/me/onenote/pages/{page_id}/content", headers)
        fingerprints.update(_extract_fingerprints(content))
    return fingerprints


def notebook_sections_laden(token: str, notebook_id: str) -> List[Dict[str, Any]]:
    headers = {"Authorization": f"Bearer {token}"}
    return _iter_graph_collection(f"{GRAPH_BASE}/me/onenote/notebooks/{notebook_id}/sections?$select=id,displayName", headers)


def fingerprint_in_notebook(token: str, notebook_id: str, fingerprint: str) -> bool:
    for section in notebook_sections_laden(token, notebook_id):
        section_id = section.get("id")
        if not isinstance(section_id, str) or not section_id:
            continue
        fingerprints = section_fingerprints_laden(token, section_id)
        if fingerprint in fingerprints:
            return True
    return False


def notebook_fingerprints_laden(token: str, notebook_id: str) -> Set[str]:
    all_fingerprints: Set[str] = set()
    for section in notebook_sections_laden(token, notebook_id):
        section_id = section.get("id")
        if not isinstance(section_id, str) or not section_id:
            continue
        all_fingerprints.update(section_fingerprints_laden(token, section_id))
    return all_fingerprints


def oneNote_seite_erstellen(token: str, section_id: str, html_inhalt: str, page_title: str) -> Dict[str, Any]:
    url = f"{GRAPH_BASE}/me/onenote/sections/{section_id}/pages"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/xhtml+xml",
    }
    full_html = f"""<!DOCTYPE html>
<html>
  <head>
    <meta charset="utf-8" />
    <title>{page_title}</title>
  </head>
  <body>
    {html_inhalt}
  </body>
</html>"""
    resp = _request_with_retry("POST", url, headers, data=full_html.encode("utf-8"))
    resp.raise_for_status()
    return resp.json()


def _parse_and_validate(text: str) -> Tuple[List[Dict[str, Any]], List[Tuple[int, Dict[str, Any], List[str]]]]:
    valid: List[Dict[str, Any]] = []
    invalid: List[Tuple[int, Dict[str, Any], List[str]]] = []

    blocks = rezepte_aufteilen(text)
    for idx, block in enumerate(blocks, start=1):
        recipe = rezept_parsen(block)
        errors = rezept_validieren(recipe)
        if errors:
            invalid.append((idx, recipe, errors))
        else:
            valid.append(recipe)

    return valid, invalid


def _write_run_report(path: str, report: Dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as report_file:
        json.dump(report, report_file, ensure_ascii=False, indent=2)


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Rezepte in OneNote importieren")
    parser.add_argument("--dry-run", action="store_true", help="Keine OneNote-Änderungen, nur Validierung und Routing-Vorschau")
    parser.add_argument("--input-file", help="Überschreibt REZEPTE_INPUT_FILE")
    parser.add_argument("--report-file", default="import_report.json", help="JSON-Berichtspfad für den Lauf")
    parser.add_argument("--check-fingerprint", help="Prüft, ob ein Fingerprint bereits im Notebook existiert")
    parser.add_argument("--list-import-meta", action="store_true", help="Listet gefundene Import-Fingerprints im Notebook")
    args = parser.parse_args(argv)

    input_file = args.input_file or INPUT_FILE or ""
    metadata_mode = bool(args.check_fingerprint) or bool(args.list_import_meta)
    require_graph = (not args.dry_run) or metadata_mode
    require_input = not metadata_mode

    try:
        _validate_config(require_graph=require_graph, input_file=(input_file if require_input else "ok"))
    except RuntimeError as exc:
        logging.error(str(exc))
        return 2

    if require_input and not os.path.isfile(input_file):
        logging.error("Eingabedatei nicht gefunden: %s", input_file)
        return 2

    if metadata_mode:
        token = anmelden().get("access_token")
        if not isinstance(token, str):
            logging.error("Kein gültiges access_token erhalten")
            return 1

        notebook_id = notebook_id_finden_oder_erstellen(token, str(NOTEBOOK_NAME))
        if args.check_fingerprint:
            fp = args.check_fingerprint.strip().lower()
            exists = fingerprint_in_notebook(token, notebook_id, fp)
            if exists:
                logging.info("Fingerprint gefunden: %s", fp)
            else:
                logging.info("Fingerprint nicht gefunden: %s", fp)
            return 0

        fingerprints = sorted(notebook_fingerprints_laden(token, notebook_id))
        logging.info("Gefundene Fingerprints: %d", len(fingerprints))
        for fp in fingerprints:
            print(fp)
        return 0

    with open(input_file, "r", encoding="utf-8") as f:
        text = f.read()

    valid, invalid = _parse_and_validate(text)
    report: Dict[str, Any] = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "mode": "dry-run" if args.dry_run else "import",
        "input_file": input_file,
        "summary": {
            "total_blocks": len(valid) + len(invalid),
            "valid": len(valid),
            "invalid": len(invalid),
            "imported": 0,
            "duplicates": 0,
            "errors": 0,
        },
        "items": [],
    }

    for idx, recipe, errors in invalid:
        title = recipe.get("titel") or f"Block {idx}"
        logging.warning("Rezept NICHT importierbar: %s", title)
        for err in errors:
            logging.warning("  - %s", err)
        report["items"].append(
            {
                "title": title,
                "group": recipe.get("gruppe", ""),
                "category": recipe.get("kategorie", ""),
                "status": "invalid",
                "reasons": errors,
            }
        )

    if args.dry_run:
        for recipe in valid:
            fp = rezept_fingerprint(recipe)
            logging.info(
                "OK: %s -> Gruppe='%s' | Kategorie='%s' | Zutaten=%d | Schritte=%d [fp=%s]",
                recipe["titel"],
                recipe["gruppe"],
                recipe["kategorie"],
                len(recipe["zutaten"]),
                len(recipe["schritte"]),
                fp,
            )
            report["items"].append(
                {
                    "title": recipe["titel"],
                    "group": recipe["gruppe"],
                    "category": recipe["kategorie"],
                    "status": "dry_run_ok",
                    "fingerprint": fp,
                }
            )
        _write_run_report(args.report_file, report)
        logging.info("Dry-Run beendet: %d gültig, %d ungültig", len(valid), len(invalid))
        logging.info("Report geschrieben: %s", args.report_file)
        return 0

    if not valid:
        logging.error("Keine gültigen Rezepte zum Import vorhanden.")
        _write_run_report(args.report_file, report)
        logging.info("Report geschrieben: %s", args.report_file)
        return 1

    token = anmelden().get("access_token")
    if not isinstance(token, str):
        logging.error("Kein gültiges access_token erhalten")
        return 1

    notebook_id = notebook_id_finden_oder_erstellen(token, str(NOTEBOOK_NAME))
    group_cache: Dict[str, str] = {}
    section_cache: Dict[Tuple[str, str], str] = {}
    section_fingerprint_cache: Dict[str, Set[str]] = {}

    imported_count = 0
    skipped_duplicates = 0
    for recipe in valid:
        group_name = str(recipe["gruppe"])
        category_name = str(recipe["kategorie"])
        fingerprint = rezept_fingerprint(recipe)

        if group_name not in group_cache:
            group_cache[group_name] = section_group_id_finden_oder_erstellen(token, notebook_id, group_name)
        group_id = group_cache[group_name]

        section_key = (group_id, category_name)
        if section_key not in section_cache:
            section_cache[section_key] = section_id_finden_oder_erstellen(token, group_id, category_name)
        section_id = section_cache[section_key]

        if section_id not in section_fingerprint_cache:
            section_fingerprint_cache[section_id] = section_fingerprints_laden(token, section_id)

        if fingerprint in section_fingerprint_cache[section_id]:
            skipped_duplicates += 1
            logging.info("Duplikat übersprungen: %s (%s)", recipe["titel"], fingerprint)
            report["items"].append(
                {
                    "title": recipe["titel"],
                    "group": group_name,
                    "category": category_name,
                    "status": "duplicate",
                    "fingerprint": fingerprint,
                }
            )
            continue

        try:
            html = rezept_zu_html(recipe, fingerprint=fingerprint)
            response = oneNote_seite_erstellen(token, section_id, html, page_title=str(recipe["titel"]))
            imported_count += 1
            section_fingerprint_cache[section_id].add(fingerprint)
            logging.info("Seite erstellt: %s (%s) [fp=%s]", recipe["titel"], response.get("id"), fingerprint)
            report["items"].append(
                {
                    "title": recipe["titel"],
                    "group": group_name,
                    "category": category_name,
                    "status": "imported",
                    "page_id": response.get("id"),
                    "fingerprint": fingerprint,
                }
            )
        except Exception as exc:
            report["summary"]["errors"] += 1
            logging.exception("Importfehler bei '%s': %s", recipe["titel"], exc)
            report["items"].append(
                {
                    "title": recipe["titel"],
                    "group": group_name,
                    "category": category_name,
                    "status": "error",
                    "fingerprint": fingerprint,
                    "error": str(exc),
                }
            )
        time.sleep(0.3)

    report["summary"]["imported"] = imported_count
    report["summary"]["duplicates"] = skipped_duplicates
    _write_run_report(args.report_file, report)

    logging.info(
        "Import abgeschlossen: %d importiert, %d Duplikate übersprungen, %d verworfen",
        imported_count,
        skipped_duplicates,
        len(invalid),
    )
    logging.info("Report geschrieben: %s", args.report_file)
    return 0


if __name__ == "__main__":
    sys.exit(main())
