from __future__ import annotations

import re
from typing import Any, Dict

FIELD_RE = re.compile(r"^\s*(Titel|Gruppe|Kategorie|Portionen|Zeit|Schwierigkeit)\s*:\s*(.*?)\s*$")
INGREDIENTS_HEADER_RE = re.compile(r"^\s*Zutaten\s*:\s*$")
STEPS_HEADER_RE = re.compile(r"^\s*Zubereitung\s*:\s*$")
LIST_PREFIX_RE = re.compile(r"^\s*(?:[-*]|\d+[.)])\s+")


def _clean_list_item(line: str) -> str:
    return LIST_PREFIX_RE.sub("", line).strip()


def parse_structured_recipe(block: str) -> Dict[str, Any]:
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

        match = FIELD_RE.match(line)
        if match:
            label = match.group(1)
            value = match.group(2).strip()
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
