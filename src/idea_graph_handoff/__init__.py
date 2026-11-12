"""Пакет «Передача в студию»: превращает граф идеи в доску идей pacage-studio-ide.

Работает кодом, без модели. Пишет в папку идеи файл ``studio-ideas.json`` в формате доски
студии (``{"version": 1, "ideas": [{"title", "description", "scenarios", "pages"}]}``).
В студии его принимает экран «Идеи» → загрузка доски из файла; тот же файл можно положить
в проект студии как ``.studio/ideas.json``, если доски там ещё нет.

Что куда попадает:
- идея студии — корень графа; в описание добавляются границы и допущения;
- сценарии — принятые карточки «требование» (от пакета формализации) с критериями приёмки;
  если требований ещё нет — принятые решения-листья;
- страницы — карточки из веток про интерфейс и карточки вида «страница» / «экран».
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from idea_graph_core import ACCEPTED, DETAIL, ROOT_KIND

__version__ = "0.1.0"

FILE_NAME = "studio-ideas.json"
UI_BRANCH = re.compile(r"интерфейс|экран|страниц|\bui\b|\bux\b", re.IGNORECASE)
PAGE_KINDS = ("страница", "экран")
SKIP_KINDS = ("замечание", "открытый вопрос", "ветка", "граница", "факт", "конкурент", ROOT_KIND)


def _one_line(text: str) -> str:
    return " ".join((text or "").split())


def build(store) -> dict:
    """Собрать доску идей студии из графа."""
    cards = store.cards
    root = cards[store.root_id]
    parents: dict[str, list[str]] = {}
    has_children: set[str] = set()
    for edge in store.edges.values():
        if edge["kind"] == DETAIL:
            parents.setdefault(edge["from"], []).append(edge["to"])
            has_children.add(edge["to"])

    def branch_of(card_id: str) -> str:
        """Название ближайшей ветки над карточкой — в студии это «домен»."""
        seen, todo = set(), [card_id]
        while todo:
            current = todo.pop(0)
            for parent in parents.get(current, []):
                if parent in seen:
                    continue
                seen.add(parent)
                if cards[parent]["kind"] == "ветка":
                    return cards[parent]["title"]
                todo.append(parent)
        return ""

    def is_page(card: dict) -> bool:
        return card["kind"] in PAGE_KINDS or bool(UI_BRANCH.search(branch_of(card["id"])))

    accepted = [c for c in sorted(cards.values(), key=lambda c: int(c["id"][1:]))
                if c["status"] == ACCEPTED and c["kind"] not in SKIP_KINDS]
    requirements = [c for c in accepted if c["kind"] == "требование" and not is_page(c)]
    source = requirements or [c for c in accepted if c["id"] not in has_children and not is_page(c)
                              and c["kind"] not in PAGE_KINDS]
    pages = [c for c in accepted if is_page(c) and (c["kind"] in PAGE_KINDS or c["id"] not in has_children)]

    def acceptance(card: dict) -> list[str]:
        items = (card.get("attrs") or {}).get("formalize.acceptance") or []
        return [str(item) for item in items if str(item).strip()]

    scenarios = [{
        "id": f"ig-{card['id']}", "title": card["title"], "description": _one_line(card.get("body")),
        "acceptance": acceptance(card), "domain": branch_of(card["id"]),
    } for card in source]
    page_items = [{
        "id": f"ig-{card['id']}", "title": card["title"], "name": card["title"],
        "description": _one_line(card.get("body")), "acceptance": acceptance(card),
        "domain": branch_of(card["id"]), "route": "", "calls": [], "blocks": [],
    } for card in pages]

    description = [root.get("body", "").strip()]
    bounds = [c["title"] for c in cards.values() if c["kind"] == "граница" and c["status"] == ACCEPTED]
    if bounds:
        description.append("Чего не делаем: " + "; ".join(bounds) + ".")
    assumptions = [c["title"] for c in cards.values()
                   if isinstance(c.get("decision"), dict) and c["decision"].get("assumption")]
    if assumptions:
        description.append("Допущения (приняты без фактов): " + "; ".join(assumptions) + ".")
    idea_id = "ig-" + root["id"]
    return {
        "version": 1, "activeId": idea_id,
        "ideas": [{
            "id": idea_id, "created_by": "", "title": root["title"],
            "description": "\n\n".join(part for part in description if part),
            "scenarios": scenarios, "pages": page_items,
        }],
    }


def run(ctx) -> dict:
    board = build(ctx.store)
    path = Path(ctx.folder) / FILE_NAME
    path.write_text(json.dumps(board, ensure_ascii=False, indent=2), encoding="utf-8")
    idea = board["ideas"][0]
    skipped = sum(1 for c in ctx.store.cards.values() if c["status"] != ACCEPTED and c["kind"] == "требование")
    summary = (f"Файл {FILE_NAME} записан в папку идеи: сценариев {len(idea['scenarios'])}, "
               f"страниц {len(idea['pages'])}.")
    if skipped:
        summary += f" Не принятых требований пропущено: {skipped}."
    summary += " В студии: экран «Идеи» → загрузить доску из файла."
    return {"outcome": "готово", "summary": summary, "files": [str(path)]}


def manifest() -> dict:
    return {
        "id": "handoff",
        "name": "Передача в студию",
        "description": "Превращает проверенный граф в доску идей pacage-studio-ide: файл studio-ideas.json "
                       "со сценариями, критериями приёмки и страницами.",
        "kind": "code",
        "order": 60,
        "reads": ["идея", "требование", "решение", "граница"],
        "writes": [],
        "asks": False,
        "model_level": "не нужна",
        "outcomes": ["готово"],
        "run": run,
    }
