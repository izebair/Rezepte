from __future__ import annotations

import html
import logging
import re
from typing import Any, Callable, Dict, List, Set

from sources import page_to_source_item

GRAPH_BASE = "https://graph.microsoft.com/v1.0"
DEFAULT_SCOPES = ["User.Read", "Notes.ReadWrite"]
FINGERPRINT_PREFIX = "REZEPTE_IMPORT_ID"
FINGERPRINT_RE = re.compile(rf"{FINGERPRINT_PREFIX}:([0-9a-f]{{64}})")


def _normalize(value: str | None) -> str:
    return (value or "").strip().lower()


class OneNoteService:
    def __init__(
        self,
        token_provider: Callable[[], str],
        *,
        client_id: str | None = None,
        tenant_id: str | None = None,
        authority_override: str | None = None,
        scopes: List[str] | None = None,
        request_with_retry: Callable[..., Any] | None = None,
        msal_module: Any | None = None,
        graph_base: str = GRAPH_BASE,
    ) -> None:
        self._token_provider = token_provider
        self._client_id = client_id
        self._tenant_id = tenant_id
        self._authority_override = authority_override
        self._scopes = list(scopes or DEFAULT_SCOPES)
        self._request_with_retry = request_with_retry
        self._msal_module = msal_module
        self._graph_base = graph_base
        self._auth_app: Any | None = None

    def start_device_flow(self) -> Dict[str, Any]:
        app = self._build_auth_app()
        flow = app.initiate_device_flow(scopes=self._scopes)
        if "user_code" not in flow:
            raise RuntimeError("Device Flow konnte nicht gestartet werden")
        return flow

    def complete_device_flow(self, flow: Dict[str, Any]) -> Dict[str, Any]:
        app = self._auth_app or self._build_auth_app()
        result = app.acquire_token_by_device_flow(flow)
        if "access_token" not in result:
            raise RuntimeError(f"Anmeldung fehlgeschlagen: {result.get('error_description', result)}")
        return result

    def list_notebooks(self) -> List[Dict[str, Any]]:
        return self._iter_graph_collection(f"{self._graph_base}/me/onenote/notebooks")

    def list_section_groups(self, parent_id: str, *, parent_type: str = "notebook") -> List[Dict[str, Any]]:
        if parent_type == "notebook":
            url = f"{self._graph_base}/me/onenote/notebooks/{parent_id}/sectionGroups"
        elif parent_type == "sectionGroup":
            url = f"{self._graph_base}/me/onenote/sectionGroups/{parent_id}/sectionGroups"
        else:
            raise ValueError(f"Unsupported parent_type: {parent_type}")
        return self._iter_graph_collection(url)

    def list_sections(self, parent_id: str, *, parent_type: str = "notebook") -> List[Dict[str, Any]]:
        if parent_type == "notebook":
            url = f"{self._graph_base}/me/onenote/notebooks/{parent_id}/sections?$select=id,displayName"
        elif parent_type == "sectionGroup":
            url = f"{self._graph_base}/me/onenote/sectionGroups/{parent_id}/sections?$select=id,displayName"
        else:
            raise ValueError(f"Unsupported parent_type: {parent_type}")
        return self._iter_graph_collection(url)

    def list_pages(self, section_id: str) -> List[Dict[str, Any]]:
        pages = self._iter_graph_collection(
            f"{self._graph_base}/me/onenote/sections/{section_id}/pages?$select=id,title"
        )
        results: List[Dict[str, Any]] = []
        for page in pages:
            page_id = page.get("id")
            if not isinstance(page_id, str) or not page_id:
                continue
            results.append(
                {
                    "id": page_id,
                    "title": str(page.get("title") or "").strip(),
                    "content": self._graph_get_text(f"{self._graph_base}/me/onenote/pages/{page_id}/content"),
                }
            )
        return results

    def get_page_source_item(self, page: Dict[str, Any]) -> Dict[str, Any]:
        item = page_to_source_item(page)
        item["source_type"] = "onenote_page"
        return item

    def get_page_source_item_by_id(self, page_id: str) -> Dict[str, Any]:
        page = self._graph_get(f"{self._graph_base}/me/onenote/pages/{page_id}?$select=id,title")
        page["content"] = self._graph_get_text(f"{self._graph_base}/me/onenote/pages/{page_id}/content")
        return self.get_page_source_item(page)

    def get_section_source_items(self, section_id: str) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        for page in self.list_pages(section_id):
            items.append(self.get_page_source_item(page))
        return items

    def ensure_target_root(self, notebook_id: str, root_name: str = "Migrated Recipes") -> str:
        return self._ensure_section_group(notebook_id, root_name, parent_type="notebook")

    def ensure_category_group(self, root_group_id: str, group_name: str) -> str:
        return self._ensure_section_group(root_group_id, group_name, parent_type="sectionGroup")

    def ensure_subcategory_section(self, category_group_id: str, section_name: str) -> str:
        sections = self.list_sections(category_group_id, parent_type="sectionGroup")
        for section in sections:
            if _normalize(section.get("displayName")) == _normalize(section_name):
                return str(section["id"])

        created = self._graph_post(
            f"{self._graph_base}/me/onenote/sectionGroups/{category_group_id}/sections",
            {"displayName": section_name},
        )
        logging.info("Abschnitt erstellt: %s", section_name)
        return str(created["id"])

    def load_target_fingerprints(self, target_scope: str | Dict[str, Any], *, target_root_name: str = "Migrated Recipes") -> Set[str]:
        notebook_id = self._resolve_notebook_id(target_scope)
        root_groups = self.list_section_groups(notebook_id, parent_type="notebook")
        root_group_id = ""
        for group in root_groups:
            if _normalize(group.get("displayName")) == _normalize(target_root_name):
                root_group_id = str(group.get("id") or "")
                break
        if not root_group_id:
            return set()

        page_entries: List[Dict[str, Any]] = []
        for category_group in self.list_section_groups(root_group_id, parent_type="sectionGroup"):
            category_group_id = str(category_group.get("id") or "")
            if not category_group_id:
                continue
            category_name = str(category_group.get("displayName") or "").strip()
            for section in self.list_sections(category_group_id, parent_type="sectionGroup"):
                section_id = str(section.get("id") or "")
                if not section_id:
                    continue
                section_name = str(section.get("displayName") or "").strip()
                for page in self._iter_graph_collection(
                    f"{self._graph_base}/me/onenote/sections/{section_id}/pages?$select=id,title"
                ):
                    page_id = page.get("id")
                    if isinstance(page_id, str) and page_id:
                        page_entries.append(
                            {
                                "id": page_id,
                                "section_id": section_id,
                                "path": [target_root_name, category_name, section_name],
                            }
                        )

        target_pages = self._filter_target_root_pages(
            page_entries,
            target_root_name=target_root_name,
            target_root_page_ids={str(page["id"]) for page in page_entries},
        )

        fingerprints: Set[str] = set()
        for page in target_pages:
            page_id = str(page["id"])
            content = self._graph_get_text(f"{self._graph_base}/me/onenote/pages/{page_id}/content")
            fingerprints.update(self._extract_fingerprints(content))
        return fingerprints

    def load_notebook_fingerprints(self, notebook_id: str) -> Set[str]:
        fingerprints: Set[str] = set()
        for section in self.list_all_sections(notebook_id):
            section_id = str(section.get("id") or "")
            if not section_id:
                continue
            for page in self._iter_graph_collection(
                f"{self._graph_base}/me/onenote/sections/{section_id}/pages?$select=id,title"
            ):
                page_id = page.get("id")
                if not isinstance(page_id, str) or not page_id:
                    continue
                content = self._graph_get_text(f"{self._graph_base}/me/onenote/pages/{page_id}/content")
                fingerprints.update(self._extract_fingerprints(content))
        return fingerprints

    def fingerprint_in_notebook(self, notebook_id: str, fingerprint: str) -> bool:
        return fingerprint in self.load_notebook_fingerprints(notebook_id)

    def list_all_sections(self, notebook_id: str) -> List[Dict[str, Any]]:
        sections = list(self.list_sections(notebook_id, parent_type="notebook"))
        for group in self.list_section_groups(notebook_id, parent_type="notebook"):
            group_id = str(group.get("id") or "")
            if not group_id:
                continue
            sections.extend(self._collect_sections_in_group(group_id))
        return sections

    def create_recipe_page(self, section_id: str, html_inhalt: str, *, page_title: str) -> Dict[str, Any]:
        url = f"{self._graph_base}/me/onenote/sections/{section_id}/pages"
        full_html = f"""<!DOCTYPE html>
<html>
  <head>
    <meta charset="utf-8" />
    <title>{html.escape(page_title)}</title>
  </head>
  <body>
    {html_inhalt}
  </body>
</html>"""
        response = self._request(
            "POST",
            url,
            headers={
                **self._auth_headers(),
                "Content-Type": "application/xhtml+xml",
            },
            data=full_html.encode("utf-8"),
        )
        response.raise_for_status()
        return response.json()

    def _filter_target_root_pages(
        self,
        pages: List[Dict[str, Any]],
        *,
        target_root_name: str,
        target_root_page_ids: Set[str],
    ) -> List[Dict[str, Any]]:
        normalized_root = _normalize(target_root_name)
        filtered: List[Dict[str, Any]] = []
        for page in pages:
            page_id = str(page.get("id") or "")
            if page_id not in target_root_page_ids:
                continue
            path = page.get("path")
            if isinstance(path, str):
                segments = [segment.strip() for segment in path.split("/") if segment.strip()]
            elif isinstance(path, list):
                segments = [str(segment).strip() for segment in path if str(segment).strip()]
            else:
                segments = []
            if segments and _normalize(segments[0]) == normalized_root:
                filtered.append(page)
        return filtered

    def _extract_fingerprints(self, content: str) -> Set[str]:
        return set(FINGERPRINT_RE.findall(content or ""))

    def _collect_sections_in_group(self, group_id: str) -> List[Dict[str, Any]]:
        sections = list(self.list_sections(group_id, parent_type="sectionGroup"))
        for child_group in self.list_section_groups(group_id, parent_type="sectionGroup"):
            child_group_id = str(child_group.get("id") or "")
            if not child_group_id:
                continue
            sections.extend(self._collect_sections_in_group(child_group_id))
        return sections

    def _resolve_notebook_id(self, target_scope: str | Dict[str, Any]) -> str:
        if isinstance(target_scope, str):
            return target_scope
        resolved_notebook_id = str(target_scope.get("notebook_id") or target_scope.get("id") or "").strip()
        if resolved_notebook_id:
            return resolved_notebook_id

        notebook_name = str(target_scope.get("notebook_name") or target_scope.get("name") or "").strip()
        if notebook_name:
            for notebook in self.list_notebooks():
                if _normalize(notebook.get("displayName")) == _normalize(notebook_name):
                    resolved_notebook_id = str(notebook.get("id") or "").strip()
                    if resolved_notebook_id:
                        return resolved_notebook_id

        raise RuntimeError("Notebook-ID fehlt fuer OneNote-Zielbereich")

    def _build_auth_app(self) -> Any:
        msal_module = self._msal_module
        if msal_module is None:
            try:
                import msal as imported_msal
            except Exception as exc:
                raise RuntimeError(f"msal nicht verfügbar: {exc}") from exc
            msal_module = imported_msal
        authority = self._resolve_authority()
        self._auth_app = msal_module.PublicClientApplication(client_id=self._client_id, authority=authority)
        return self._auth_app

    def _resolve_authority(self) -> str:
        if self._authority_override:
            if self._authority_override.startswith("http"):
                return self._authority_override
            return f"https://login.microsoftonline.com/{self._authority_override}"
        if not self._tenant_id:
            raise RuntimeError("TENANT_ID oder authority_override fehlt")
        return f"https://login.microsoftonline.com/{self._tenant_id}"

    def _auth_headers(self) -> Dict[str, str]:
        token = self._token_provider()
        if not isinstance(token, str) or not token:
            raise RuntimeError("Kein gültiges access_token erhalten")
        return {"Authorization": f"Bearer {token}"}

    def _graph_get(self, url: str) -> Dict[str, Any]:
        response = self._request("GET", url, headers=self._auth_headers())
        response.raise_for_status()
        return response.json()

    def _graph_post(self, url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        response = self._request(
            "POST",
            url,
            headers={**self._auth_headers(), "Content-Type": "application/json"},
            json=payload,
        )
        response.raise_for_status()
        return response.json()

    def _graph_get_text(self, url: str) -> str:
        response = self._request("GET", url, headers=self._auth_headers())
        response.raise_for_status()
        return response.text

    def _iter_graph_collection(self, url: str) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        next_url: str | None = url
        while next_url:
            data = self._graph_get(next_url)
            values = data.get("value", [])
            if isinstance(values, list):
                items.extend([value for value in values if isinstance(value, dict)])
            next_url = data.get("@odata.nextLink")
            if next_url is not None and not isinstance(next_url, str):
                next_url = None
        return items

    def _ensure_section_group(self, parent_id: str, group_name: str, *, parent_type: str) -> str:
        groups = self.list_section_groups(parent_id, parent_type=parent_type)
        for group in groups:
            if _normalize(group.get("displayName")) == _normalize(group_name):
                return str(group["id"])

        if parent_type == "notebook":
            url = f"{self._graph_base}/me/onenote/notebooks/{parent_id}/sectionGroups"
        elif parent_type == "sectionGroup":
            url = f"{self._graph_base}/me/onenote/sectionGroups/{parent_id}/sectionGroups"
        else:
            raise ValueError(f"Unsupported parent_type: {parent_type}")

        created = self._graph_post(url, {"displayName": group_name})
        logging.info("Abschnittsgruppe erstellt: %s", group_name)
        return str(created["id"])

    def _request(self, method: str, url: str, **kwargs: Any) -> Any:
        if self._request_with_retry is not None:
            return self._request_with_retry(method, url, **kwargs)
        import requests

        return requests.request(method, url, **kwargs)
