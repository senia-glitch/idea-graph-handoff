import json

import pytest

from ideagraph_core import HUMAN, Store
from ideagraph_handoff import FILE_NAME, build, manifest, run


class Ctx:
    def __init__(self, store, folder):
        self.store, self.folder, self.author, self.state = store, folder, "package:handoff", {}


@pytest.fixture
def store(tmp_path):
    store = Store.create(tmp_path, "Запись к врачу без звонков", "Пациент выбирает время сам")
    store.apply([
        {"op": "add_card", "kind": "ветка", "title": "Функции", "parent": "c1", "ref": "f"},
        {"op": "add_card", "kind": "решение", "title": "Онлайн-запись", "body": "Пациент видит окна", "parent": "@f"},
        {"op": "add_card", "kind": "решение", "title": "Напоминание за сутки", "parent": "@f",
         "decision": {"assumption": True, "by": "decider", "chosen": {"type": "custom", "value": "за сутки"}}},
        {"op": "add_card", "kind": "ветка", "title": "Интерфейс", "parent": "c1", "ref": "ui"},
        {"op": "add_card", "kind": "решение", "title": "Экран расписания врача", "body": "Сетка окон на 14 дней", "parent": "@ui"},
        {"op": "add_card", "kind": "граница", "title": "Мобильное приложение не делаем", "parent": "c1"},
        {"op": "add_card", "kind": "открытый вопрос", "title": "Что при отмене?", "parent": "@f"},
    ], HUMAN)
    return store


def test_decisions_become_scenarios_until_formalized(store):
    idea = build(store)["ideas"][0]
    assert idea["title"] == "Запись к врачу без звонков"
    assert [s["title"] for s in idea["scenarios"]] == ["Онлайн-запись", "Напоминание за сутки"]
    assert idea["scenarios"][0]["domain"] == "Функции" and idea["scenarios"][0]["description"] == "Пациент видит окна"
    assert [p["title"] for p in idea["pages"]] == ["Экран расписания врача"] and idea["pages"][0]["domain"] == "Интерфейс"
    assert "Чего не делаем: Мобильное приложение не делаем." in idea["description"]
    assert "Допущения (приняты без фактов): Напоминание за сутки." in idea["description"]


def test_requirements_win_over_decisions(store, tmp_path):
    store.apply([
        {"op": "add_card", "kind": "требование", "title": "Пациент занимает окно", "body": "Без звонка", "parent": "c3",
         "attrs": {"formalize.acceptance": ["Окно исчезает у других за 5 секунд", " "]}},
    ], HUMAN)
    store.apply([{"op": "add_card", "kind": "требование", "title": "Не принятое", "parent": "c3"}], "package:formalize")
    result = run(Ctx(store, tmp_path))
    board = json.loads((tmp_path / FILE_NAME).read_text(encoding="utf-8"))
    assert board["version"] == 1 and board["activeId"] == board["ideas"][0]["id"]
    scenario = board["ideas"][0]["scenarios"]
    assert [s["title"] for s in scenario] == ["Пациент занимает окно"]
    assert scenario[0]["acceptance"] == ["Окно исчезает у других за 5 секунд"] and scenario[0]["domain"] == "Функции"
    assert "сценариев 1, страниц 1" in result["summary"] and "пропущено: 1" in result["summary"]
    assert manifest()["kind"] == "code"
