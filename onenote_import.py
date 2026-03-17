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
from pathlib import Path
import re
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Set, Tuple

from models import HealthAssessment, Ingredient, Recipe, Step
from quality_rules import build_quality_findings, build_quality_suggestions, summarize_quality
from review import derive_blocking_issues, derive_review_status, derive_review_triggers, derive_uncertainty
from health_rules import build_health_assessments
from taxonomy import resolve_categories, resolve_destination_categories
from parsers import parse_freeform_recipe, parse_structured_recipe
from ocr import OCRArtifact, run_ocr_for_artifacts
from sources import build_local_media_source_item, page_to_source_item


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


def _parse_minutes(value: str) -> int | None:
    match = re.search(r"(\d{1,3})", value or "")
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


def _build_recipe_model(recipe_data: Dict[str, Any]) -> Dict[str, Any]:
    title = str(recipe_data.get("titel") or "").strip()
    group = str(recipe_data.get("gruppe") or "").strip()
    category = str(recipe_data.get("kategorie") or "").strip()
    main_category, resolved_subcategory, taxonomy_notes = resolve_categories(group, category)
    target_group, target_category, destination_notes = resolve_destination_categories(group, category)

    model = Recipe(
        recipe_id=f"recipe-{abs(hash(title + group + category + str(recipe_data.get('raw') or '')))}",
        title=title,
        category_main=main_category,
        category_sub=resolved_subcategory,
        group=group,
        servings=str(recipe_data.get("portionen") or "").strip(),
        time_text=str(recipe_data.get("zeit") or "").strip(),
        difficulty=str(recipe_data.get("schwierigkeit") or "").strip(),
        ingredients=[Ingredient(name_raw=str(item).strip()) for item in recipe_data.get("zutaten", []) if str(item).strip()],
        steps=[Step(order=index, text_raw=str(item).strip()) for index, item in enumerate(recipe_data.get("schritte", []), start=1) if str(item).strip()],
        raw=str(recipe_data.get("raw") or ""),
        total_minutes=_parse_minutes(str(recipe_data.get("zeit") or "")),
    )

    legacy = model.to_legacy_dict()
    findings = build_quality_findings(legacy)
    suggestions = build_quality_suggestions(legacy, findings)
    uncertainty = derive_uncertainty(legacy, [], findings)
    all_taxonomy_notes = [*taxonomy_notes, *destination_notes]
    if all_taxonomy_notes:
        uncertainty["reasons"].extend(all_taxonomy_notes)
        if uncertainty["overall"] == "low":
            uncertainty["overall"] = "medium"
    model.quality_status = summarize_quality(findings)
    model.quality_suggestions = suggestions
    health = build_health_assessments({**legacy, "quality": {"status": model.quality_status}, "uncertainty": uncertainty})
    model.health_assessments = [HealthAssessment(**assessment) for assessment in health.get("assessments", [])]
    model.health_disclaimer = str(health.get("disclaimer") or model.health_disclaimer)
    review_status = derive_review_status({**legacy, "uncertainty": uncertainty, "health": health}, [], findings)
    model.review.status = review_status
    model.uncertainty.overall = uncertainty["overall"]
    model.uncertainty.reasons = uncertainty["reasons"]
    model.uncertainty.confidence_by_stage = uncertainty["confidence_by_stage"]

    result = model.to_legacy_dict()
    result["kategorie"] = category
    result["unterkategorie"] = resolved_subcategory
    result["ziel_gruppe"] = target_group
    result["ziel_kategorie"] = target_category
    result["quality"]["findings"] = findings
    result["quality"]["suggestions"] = suggestions
    result["health"] = health
    return result


def rezept_parsen(block: str) -> Dict[str, Any]:
    if any(marker in block for marker in ["Titel:", "Gruppe:", "Kategorie:", "Zutaten:", "Zubereitung:"]):
        recipe = parse_structured_recipe(block)
    else:
        recipe = parse_freeform_recipe(block)
    return _build_recipe_model(recipe)


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
    if not str(recipe.get("hauptkategorie") or "").strip():
        main_category, _, _ = resolve_categories(str(recipe.get("gruppe") or ""), str(recipe.get("kategorie") or ""))
        if not main_category:
            errors.append("Hauptkategorie konnte nicht abgeleitet werden")

    findings = recipe.get("quality", {}).get("findings", [])
    for finding in findings:
        if finding.get("severity") == "error":
            message = str(finding.get("message") or "Qualitaetsproblem")
            if message not in errors:
                errors.append(message)
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
    if recipe.get("hauptkategorie"):
        meta_parts.append(f"Hauptkategorie: {recipe['hauptkategorie']}")
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


def onenote_pages_laden(token: str, section_id: str) -> List[Dict[str, Any]]:
    headers = {"Authorization": f"Bearer {token}"}
    pages = _iter_graph_collection(f"{GRAPH_BASE}/me/onenote/sections/{section_id}/pages?$select=id,title", headers)
    results: List[Dict[str, Any]] = []
    for page in pages:
        page_id = page.get("id")
        if not isinstance(page_id, str) or not page_id:
            continue
        results.append({
            "id": page_id,
            "title": str(page.get("title") or "").strip(),
            "content": _graph_get_text(f"{GRAPH_BASE}/me/onenote/pages/{page_id}/content", headers),
        })
    return results


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
    <meta charset=\"utf-8\" />
    <title>{html.escape(page_title)}</title>
  </head>
  <body>
    {html_inhalt}
  </body>
</html>"""
    resp = _request_with_retry("POST", url, headers, data=full_html.encode("utf-8"))
    resp.raise_for_status()
    return resp.json()


def _apply_source_context(recipe: Dict[str, Any], source_item: Dict[str, Any] | None) -> Dict[str, Any]:
    if not source_item:
        return recipe
    recipe["media"] = source_item.get("media", [])
    recipe["ocr_text"] = str(source_item.get("ocr_text") or "")
    recipe["source_type"] = str(source_item.get("source_type") or "")
    recipe["ocr_status"] = str(source_item.get("ocr_status") or "")
    recipe["ocr_confidence"] = float(source_item.get("ocr_confidence") or 0.0)
    return recipe


def _parse_and_validate_blocks(blocks: List[str], source_items: List[Dict[str, Any]] | None = None) -> Tuple[List[Dict[str, Any]], List[Tuple[int, Dict[str, Any], List[str]]]]:
    valid: List[Dict[str, Any]] = []
    invalid: List[Tuple[int, Dict[str, Any], List[str]]] = []

    for idx, block in enumerate(blocks, start=1):
        recipe = rezept_parsen(block)
        source_item = source_items[idx - 1] if source_items and idx - 1 < len(source_items) else None
        recipe = _apply_source_context(recipe, source_item)
        findings = build_quality_findings(recipe)
        suggestions = build_quality_suggestions(recipe, findings)
        uncertainty = derive_uncertainty(recipe, [], findings)
        recipe["quality"]["findings"] = findings
        recipe["quality"]["suggestions"] = suggestions
        recipe["quality"]["status"] = summarize_quality(findings)
        recipe["uncertainty"] = uncertainty
        recipe["health"] = build_health_assessments(recipe)
        recipe["review"]["status"] = derive_review_status(recipe, [], findings)
        errors = rezept_validieren(recipe)
        if errors:
            invalid.append((idx, recipe, errors))
        else:
            valid.append(recipe)

    return valid, invalid


def _parse_and_validate(text: str) -> Tuple[List[Dict[str, Any]], List[Tuple[int, Dict[str, Any], List[str]]]]:
    return _parse_and_validate_blocks(rezepte_aufteilen(text))


def _write_run_report(path: str, report: Dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as report_file:
        json.dump(report, report_file, ensure_ascii=False, indent=2)


def _sanitize_report_path(value: str) -> str:
    path_value = str(value or "").strip()
    if not path_value:
        return ""
    return Path(path_value).name or path_value


def _sanitize_report_error(value: str, *, max_length: int = 160) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    text = re.sub(r"https?://\S+", "[url]", text)
    text = re.sub(r"Bearer\s+\S+", "Bearer [redacted]", text, flags=re.IGNORECASE)
    text = re.sub(r"(?i)(access[_-]?token|refresh[_-]?token|authorization)=([^\s&]+)", r"\1=[redacted]", text)
    if len(text) > max_length:
        text = text[: max_length - 1].rstrip() + "…"
    return text


def _extract_health_light(recipe: Dict[str, Any], condition: str) -> str:
    assessments = recipe.get("health", {}).get("assessments", [])
    for assessment in assessments:
        if isinstance(assessment, dict) and str(assessment.get("condition") or "") == condition:
            return str(assessment.get("light") or "")
    return ""



def _build_media_summary(recipe: Dict[str, Any]) -> Dict[str, Any]:
    media = recipe.get("media", []) or []
    images = 0
    pdfs = 0
    ocr_done = 0
    ocr_pending = 0
    ocr_failed = 0

    for item in media:
        if not isinstance(item, dict):
            continue
        media_type = str(item.get("type") or "")
        ocr_status = str(item.get("ocr_status") or "")
        if media_type == "image":
            images += 1
        elif media_type == "pdf":
            pdfs += 1
        if ocr_status == "done":
            ocr_done += 1
        elif ocr_status in {"pending", "disabled", "empty", ""}:
            ocr_pending += 1
        elif ocr_status:
            ocr_failed += 1

    return {
        "images": images,
        "pdfs": pdfs,
        "ocr_done": ocr_done,
        "ocr_pending": ocr_pending,
        "ocr_failed": ocr_failed,
    }


def _build_confidence_summary(recipe: Dict[str, Any]) -> Dict[str, Any]:
    uncertainty = recipe.get("uncertainty", {}) or {}
    confidence_by_stage = uncertainty.get("confidence_by_stage", {}) if isinstance(uncertainty, dict) else {}
    return {
        "overall": uncertainty.get("overall", "low") if isinstance(uncertainty, dict) else "low",
        "ocr": recipe.get("ocr_confidence", confidence_by_stage.get("ocr", 0.0)),
        "parsing": confidence_by_stage.get("parsing", 0.0),
        "taxonomy": confidence_by_stage.get("taxonomy", 0.0),
        "health": confidence_by_stage.get("health", 0.0),
    }
def _build_report_item(
    recipe: Dict[str, Any],
    *,
    status: str,
    title: str | None = None,
    group: str | None = None,
    category: str | None = None,
    fingerprint: str | None = None,
    reasons: List[str] | None = None,
    page_id: str | None = None,
    error: str | None = None,
) -> Dict[str, Any]:
    item: Dict[str, Any] = {
        "title": title if title is not None else recipe.get("titel", ""),
        "group": group if group is not None else recipe.get("gruppe", ""),
        "target_group": recipe.get("ziel_gruppe", recipe.get("hauptkategorie", "")),
        "main_category": recipe.get("hauptkategorie", ""),
        "category": category if category is not None else recipe.get("kategorie", ""),
        "target_category": recipe.get("ziel_kategorie", recipe.get("unterkategorie", "")),
        "status": status,
        "source_type": recipe.get("source_type", ""),
        "ocr_status": recipe.get("ocr_status", ""),
        "ocr_confidence": recipe.get("ocr_confidence", 0.0),
        "review_status": recipe.get("review", {}).get("status"),
        "quality_status": recipe.get("quality", {}).get("status"),
        "health_prostate": _extract_health_light(recipe, "prostate_cancer"),
        "health_breast": _extract_health_light(recipe, "breast_cancer"),
        "review_triggers": derive_review_triggers(recipe, reasons or [], recipe.get("quality", {}).get("findings", [])),
        "blocking_issues": derive_blocking_issues(recipe, reasons or [], recipe.get("quality", {}).get("findings", [])),
        "media_summary": _build_media_summary(recipe),
        "confidence_summary": _build_confidence_summary(recipe),
    }
    if fingerprint is not None:
        item["fingerprint"] = fingerprint
    if reasons is not None:
        item["reasons"] = reasons
    if page_id is not None:
        item["page_id"] = page_id
    if error is not None:
        item["error"] = _sanitize_report_error(error)
    return item



def _build_queue_summary(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    status_counts: Dict[str, int] = {}
    review_status_counts: Dict[str, int] = {}
    quality_status_counts: Dict[str, int] = {}
    source_type_counts: Dict[str, int] = {}
    trigger_counts: Dict[str, int] = {}
    blocker_count = 0
    needs_review_count = 0
    media_present_count = 0
    health_red_count = 0
    health_yellow_count = 0
    health_unrated_count = 0
    ocr_pending_count = 0
    ocr_failed_count = 0

    for item in items:
        status = str(item.get("status") or "")
        if status:
            status_counts[status] = status_counts.get(status, 0) + 1

        review_status = str(item.get("review_status") or "")
        if review_status:
            review_status_counts[review_status] = review_status_counts.get(review_status, 0) + 1
            if review_status == "needs_review":
                needs_review_count += 1

        quality_status = str(item.get("quality_status") or "")
        if quality_status:
            quality_status_counts[quality_status] = quality_status_counts.get(quality_status, 0) + 1

        source_type = str(item.get("source_type") or "unknown")
        source_type_counts[source_type] = source_type_counts.get(source_type, 0) + 1

        triggers = item.get("review_triggers", []) or []
        for trigger in triggers:
            trigger_name = str(trigger)
            trigger_counts[trigger_name] = trigger_counts.get(trigger_name, 0) + 1

        blocking_issues = item.get("blocking_issues", []) or []
        if blocking_issues:
            blocker_count += 1

        for health_key in ("health_prostate", "health_breast"):
            light = str(item.get(health_key) or "")
            if light == "red":
                health_red_count += 1
            elif light == "yellow":
                health_yellow_count += 1
            elif light == "unrated":
                health_unrated_count += 1

        media_summary = item.get("media_summary", {}) if isinstance(item, dict) else {}
        media_count = int(media_summary.get("images", 0) or 0) + int(media_summary.get("pdfs", 0) or 0)
        if media_count > 0:
            media_present_count += 1

        ocr_status = str(item.get("ocr_status") or "")
        if media_count > 0:
            if ocr_status in {"pending", "disabled", "empty", ""}:
                ocr_pending_count += 1
            elif ocr_status and ocr_status != "done":
                ocr_failed_count += 1

    return {
        "total_items": len(items),
        "status_counts": status_counts,
        "review_status_counts": review_status_counts,
        "quality_status_counts": quality_status_counts,
        "source_type_counts": source_type_counts,
        "trigger_counts": trigger_counts,
        "blocker_count": blocker_count,
        "needs_review_count": needs_review_count,
        "media_present_count": media_present_count,
        "health_red_count": health_red_count,
        "health_yellow_count": health_yellow_count,
        "health_unrated_count": health_unrated_count,
        "ocr_pending_count": ocr_pending_count,
        "ocr_failed_count": ocr_failed_count,
    }


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Rezepte in OneNote importieren")
    parser.add_argument("--dry-run", action="store_true", help="Keine OneNote-Änderungen, nur Validierung und Routing-Vorschau")
    parser.add_argument("--input-file", help="Überschreibt REZEPTE_INPUT_FILE")
    parser.add_argument("--report-file", default="import_report.json", help="JSON-Berichtspfad für den Lauf")
    parser.add_argument("--check-fingerprint", help="Prüft, ob ein Fingerprint bereits im Notebook existiert")
    parser.add_argument("--list-import-meta", action="store_true", help="Listet gefundene Import-Fingerprints im Notebook")
    parser.add_argument("--source-type", choices=["file", "onenote-section"], default="file", help="Quelle fuer den Importlauf")
    parser.add_argument("--source-section-id", help="OneNote-Section-ID fuer den Lesezugriff")
    parser.add_argument("--ocr", action="store_true", help="Lokale OCR fuer Bild-/PDF-Quellen aktivieren")
    args = parser.parse_args(argv)

    input_file = args.input_file or INPUT_FILE or ""
    metadata_mode = bool(args.check_fingerprint) or bool(args.list_import_meta)
    source_is_onenote = args.source_type == "onenote-section"
    require_graph = (not args.dry_run) or metadata_mode or source_is_onenote
    require_input = (not metadata_mode) and not source_is_onenote

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

    source_items: List[Dict[str, Any]] | None = None
    if source_is_onenote:
        if not args.source_section_id:
            logging.error("--source-section-id ist erforderlich fuer --source-type onenote-section")
            return 2
        token = anmelden().get("access_token")
        if not isinstance(token, str):
            logging.error("Kein gültiges access_token erhalten")
            return 1
        pages = onenote_pages_laden(token, args.source_section_id)
        source_items = []
        blocks: List[str] = []
        for page in pages:
            item = page_to_source_item(page)
            item["source_type"] = "onenote_page"
            source_items.append(item)
            title = str(item.get("title") or "").strip()
            body_text = str(item.get("text") or "").strip()
            blocks.append((f"{title}\n\n{body_text}" if title and body_text and not body_text.lower().startswith(title.lower()) else (title or body_text)).strip())
        valid, invalid = _parse_and_validate_blocks(blocks, source_items)
    else:
        suffix = Path(input_file).suffix.lower()
        media_suffixes = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".pdf"}
        if suffix in media_suffixes and not args.ocr:
            logging.error("Bild- und PDF-Dateien erfordern aktuell --ocr fuer die Verarbeitung: %s", input_file)
            return 2
        if args.ocr and suffix in media_suffixes:
            artifact = OCRArtifact(media_id="file-1", media_type=("pdf" if suffix == ".pdf" else "image"), ref=input_file)
            ocr_results = run_ocr_for_artifacts([artifact])
            merged_text, source_item = build_local_media_source_item(input_file, ocr_results)
            valid, invalid = _parse_and_validate_blocks([merged_text], [source_item])
        else:
            with open(input_file, "r", encoding="utf-8") as f:
                text = f.read()
            valid, invalid = _parse_and_validate(text)
    report: Dict[str, Any] = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "mode": "dry-run" if args.dry_run else "import",
        "input_file": _sanitize_report_path(input_file),
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
        report["items"].append(_build_report_item(recipe, status="invalid", title=title, reasons=errors))

    if args.dry_run:
        for recipe in valid:
            fp = rezept_fingerprint(recipe)
            logging.info(
                "OK: %s -> Hauptkategorie='%s' | Gruppe='%s' | Kategorie='%s' | Zutaten=%d | Schritte=%d [fp=%s]",
                recipe["titel"],
                recipe.get("hauptkategorie", ""),
                recipe["gruppe"],
                recipe["kategorie"],
                len(recipe["zutaten"]),
                len(recipe["schritte"]),
                fp,
            )
            report["items"].append(_build_report_item(recipe, status="dry_run_ok", fingerprint=fp))
        report["queue_summary"] = _build_queue_summary(report["items"])
        _write_run_report(args.report_file, report)
        logging.info("Dry-Run beendet: %d gültig, %d ungültig", len(valid), len(invalid))
        logging.info("Report geschrieben: %s", args.report_file)
        return 0

    if not valid:
        logging.error("Keine gültigen Rezepte zum Import vorhanden.")
        report["queue_summary"] = _build_queue_summary(report["items"])
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
        group_name = str(recipe.get("ziel_gruppe") or recipe["gruppe"])
        category_name = str(recipe.get("ziel_kategorie") or recipe.get("unterkategorie") or recipe["kategorie"])
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
            report["items"].append(_build_report_item(recipe, status="duplicate", group=group_name, category=category_name, fingerprint=fingerprint))
            continue

        try:
            html_inhalt = rezept_zu_html(recipe, fingerprint=fingerprint)
            response = oneNote_seite_erstellen(token, section_id, html_inhalt, page_title=str(recipe["titel"]))
            imported_count += 1
            section_fingerprint_cache[section_id].add(fingerprint)
            logging.info("Seite erstellt: %s (%s) [fp=%s]", recipe["titel"], response.get("id"), fingerprint)
            report["items"].append(_build_report_item(recipe, status="imported", group=group_name, category=category_name, fingerprint=fingerprint, page_id=response.get("id")))
        except Exception as exc:
            report["summary"]["errors"] += 1
            logging.exception("Importfehler bei '%s': %s", recipe["titel"], exc)
            report["items"].append(_build_report_item(recipe, status="error", group=group_name, category=category_name, fingerprint=fingerprint, error=str(exc)))
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






















