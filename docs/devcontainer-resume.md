# DevContainer Resume Guide

## Ziel

Dieser DevContainer setzt die laufende Arbeit im Worktree `feature/onenote-desktop-mvp` fort und bindet die lokale Codex-/superpowers-Konfiguration aus `C:\\Users\\Heiko\\.codex` in den Container ein.

## Was der Container tut

- verwendet Python 3.13
- mountet den aktuellen Worktree als Workspace
- mountet `C:\\Users\\Heiko\\.codex` nach `/home/vscode/.codex`
- setzt `CODEX_HOME=/home/vscode/.codex`
- erstellt im Container den Skill-Link:
  - `/home/vscode/.agents/skills/superpowers -> /home/vscode/.codex/superpowers/skills`
- installiert `requirements.txt`

## So oeffnest du den Stand

1. Oeffne in VS Code genau diesen Ordner:
   - `c:\\Users\\Heiko\\OneDrive\\Dokumente\\Dev\\Python\\Rezepte\\.worktrees\\onenote-desktop-mvp`

2. Starte:
   - `Dev Containers: Reopen in Container`

3. Pruefe im Container:

```bash
pwd
git status --short --branch
ls -la ~/.agents/skills
python -m pytest tests/test_service_contracts.py tests/test_onenote_service.py -v
```

## Chat-Handoff fuer den neuen Container-Chat

Diesen Block am Anfang in den neuen Chat einfuegen:

```text
Wir arbeiten im Worktree /workspaces/onenote-desktop-mvp auf Branch feature/onenote-desktop-mvp.

Spec:
docs/superpowers/specs/2026-03-18-onenote-desktop-migration-mvp-design.md

Plan:
docs/superpowers/plans/2026-03-18-onenote-desktop-migration-mvp.md

Bereits fertig und committed:
- Task 1: service contracts + session models
- Task 2: onenote graph service extraction

Aktueller WIP:
- Task 3: dry-run import service
- geaenderte/uncommittete Dateien:
  - services/import_service.py
  - services/report_service.py
  - tests/test_import_service_dry_run.py
  - onenote_import.py

Zuletzt verifiziert:
- Baseline vor der Umsetzung war gruen
- Task 1 Tests gruen
- Task 2 Tests gruen
- Task 3 Red-Step war bestaetigt

Naechster Schritt:
- Task 3 fertig verifizieren, reviewen und committen
- danach Task 4 Execute-Migration
```

## Wichtiger Hinweis zu Worktrees

Weiterarbeit immer im Worktree:

- `c:\\Users\\Heiko\\OneDrive\\Dokumente\\Dev\\Python\\Rezepte\\.worktrees\\onenote-desktop-mvp`

Nicht im Haupt-Checkout auf `main`, sonst arbeitest du am falschen Stand.
