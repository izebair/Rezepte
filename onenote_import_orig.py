"""
onenote_import.py
Einfaches Tool: parst Rezepte aus einer Textdatei und erstellt OneNote Seiten via Microsoft Graph.
Device Code Flow (interaktiver Login).
"""

import os
import re
import json
import time
import requests
from msal import PublicClientApplication
from bs4 import BeautifulSoup

# ---------- CONFIG ----------
CLIENT_ID = "<DEINE_CLIENT_ID>"
TENANT_ID = "<DEIN_TENANT_ID>"
SCOPES = ["Notes.ReadWrite"]  # delegated
GRAPH_BASE = "https://graph.microsoft.com/v1.0"
# Ziel: section-id oder section-name (wenn name, wir suchen id)
TARGET_NOTEBOOK = None  # optional: Notebook-Name
TARGET_SECTION = "Rezepte"  # Abschnittsname, in den Seiten erstellt werden
INPUT_FILE = "rezepte.txt"
# ----------------------------

def device_login():
    app = PublicClientApplication(CLIENT_ID, authority=f"https://login.microsoftonline.com/{TENANT_ID}")
    flow = app.initiate_device_flow(scopes=SCOPES)
    if "user_code" not in flow:
        raise ValueError("Device flow konnte nicht gestartet werden.")
    print(flow["message"])
    result = app.acquire_token_by_device_flow(flow)
    if "access_token" in result:
        return result["access_token"]
    raise ValueError("Login fehlgeschlagen: " + json.dumps(result, indent=2))

def find_section_id(token, notebook_name=None, section_name=None):
    headers = {"Authorization": f"Bearer {token}"}
    # Suche alle Notebooks, dann Sections
    r = requests.get(f"{GRAPH_BASE}/me/onenote/notebooks", headers=headers)
    r.raise_for_status()
    notebooks = r.json().get("value", [])
    # Wenn Notebook angegeben, filter
    for nb in notebooks:
        if notebook_name and nb.get("displayName") != notebook_name:
            continue
        # hole sections
        r2 = requests.get(f"{GRAPH_BASE}/me/onenote/notebooks/{nb['id']}/sections", headers=headers)
        r2.raise_for_status()
        for sec in r2.json().get("value", []):
            if sec.get("displayName") == section_name:
                return sec["id"]
    # Falls nicht gefunden: erstelle Section im ersten Notebook
    if not notebooks:
        raise RuntimeError("Keine Notebooks gefunden. Bitte erstelle ein Notebook in OneNote.")
    nb0 = notebooks[0]
    payload = {"displayName": section_name}
    r3 = requests.post(f"{GRAPH_BASE}/me/onenote/notebooks/{nb0['id']}/sections", headers=headers, json=payload)
    r3.raise_for_status()
    return r3.json()["id"]

# Einfache Parserfunktion: trennt Rezepte anhand von Schlüsselwörtern
def split_recipes(text):
    # Splits when a line looks like a recipe title (non-empty line not containing colon and not 'Zutaten' etc.)
    lines = text.splitlines()
    recipes = []
    cur = []
    for ln in lines:
        if ln.strip() == "":
            if cur:
                cur.append(ln)
            continue
        # Heuristik: neue Rezeptüberschrift wenn Zeile keine ':' enthält und nicht ein known header
        if re.match(r'^[A-Za-zÄÖÜäöüß0-9 \-\,\']+$', ln.strip()) and ":" not in ln and ln.strip().lower() not in ("zutaten","zubereitung","portionen","zeit","schwierigkeit","beschreibung"):
            # If current buffer contains a 'Zutaten' or 'Zubereitung', start new recipe
            if any(h.lower() in "\n".join(cur).lower() for h in ("zutaten","zubereitung")):
                recipes.append("\n".join(cur).strip())
                cur = [ln]
            else:
                cur.append(ln)
        else:
            cur.append(ln)
    if cur and any(h.lower() in "\n".join(cur).lower() for h in ("zutaten","zubereitung")):
        recipes.append("\n".join(cur).strip())
    return recipes

# Extrahiere Felder aus Rezepttext
def parse_recipe_block(block):
    # Suche Felder anhand von Kopfzeilen
    fields = {"Titel": "", "Beschreibung": "", "Kategorie": "", "Zutaten": "", "Zubereitung": "", "Portionen": "", "Zeit": "", "Schwierigkeit": ""}
    # Titel: erste nicht-leere Zeile
    lines = [l for l in block.splitlines()]
    if lines:
        fields["Titel"] = lines[0].strip()
    # Regex für headers
    for header in ["Kategorie","Zutaten","Zubereitung","Portionen","Zeit","Schwierigkeit","Beschreibung"]:
        m = re.search(rf"{header}\s*(?:\n|:)(.*?)(?=\n[A-ZÄÖÜ][a-zäöüß ]+?:|\Z)", block, flags=re.S|re.I)
        if m:
            fields[header] = m.group(1).strip()
    # Fallback: if Zutaten not found, try to find bullet lists
    return fields

# Erzeuge HTML nach deiner Vorlage
def recipe_to_onenote_html(r):
    soup = BeautifulSoup("", "html.parser")
    body = soup.new_tag("div")
    # Titel
    h1 = soup.new_tag("h1")
    h1.string = r.get("Titel","Rezept")
    body.append(h1)
    # Beschreibung
    if r.get("Beschreibung"):
        p = soup.new_tag("p")
        p.string = r["Beschreibung"]
        body.append(p)
    # Zutaten
    h2 = soup.new_tag("h2"); h2.string = "Zutaten"
    body.append(h2)
    if r.get("Zutaten"):
        ul = soup.new_tag("ul")
        for line in r["Zutaten"].splitlines():
            line = line.strip(" •-")
            if line:
                li = soup.new_tag("li"); li.string = line
                ul.append(li)
        body.append(ul)
    # Zubereitung
    h2b = soup.new_tag("h2"); h2b.string = "Zubereitung"
    body.append(h2b)
    if r.get("Zubereitung"):
        ol = soup.new_tag("ol")
        # split by numbered steps or newlines
        steps = re.split(r'\n\d+\.\s*', "\n"+r["Zubereitung"])
        for s in steps:
            s = s.strip()
            if s:
                li = soup.new_tag("li"); li.string = s
                ol.append(li)
        body.append(ol)
    # Meta
    meta = soup.new_tag("p")
    meta.string = f"Portionen: {r.get('Portionen','-')}  •  Zeit: {r.get('Zeit','-')}  •  Schwierigkeit: {r.get('Schwierigkeit','-')}"
    body.append(meta)
    soup.append(body)
    html = str(soup)
    return html

def create_onenote_page(token, section_id, title, html_content):
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/xhtml+xml"
    }
    # OneNote expects a full HTML document; minimal wrapper
    html = f"""<!DOCTYPE html><html><head><title>{title}</title></head><body>{html_content}</body></html>"""
    url = f"{GRAPH_BASE}/me/onenote/sections/{section_id}/pages"
    r = requests.post(url, headers=headers, data=html.encode('utf-8'))
    if r.status_code not in (200,201):
        print("Fehler beim Erstellen der Seite:", r.status_code, r.text)
    else:
        print("Seite erstellt:", title)

def main():
    token = device_login()
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        text = f.read()
    blocks = split_recipes(text)
    print(f"Gefundene Rezepte: {len(blocks)}")
    section_cache = {}
    for b in blocks:
        parsed = parse_recipe_block(b)
        # Nutze Kategorie-Header falls vorhanden, sonst DEFAULT TARGET_SECTION
        section_name = parsed.get("Kategorie") or TARGET_SECTION
        if section_name not in section_cache:
            section_cache[section_name] = find_section_id(token, notebook_name=TARGET_NOTEBOOK, section_name=section_name)
        section_id = section_cache[section_name]
        html = recipe_to_onenote_html(parsed)
        create_onenote_page(token, section_id, parsed.get("Titel","Rezept"), html)
        time.sleep(0.5)

if __name__ == "__main__":
    main()