from onenote_import import _parse_category_mapping, _resolve_target_section_and_title


def test_parse_category_mapping_json_and_kv():
    m_json = _parse_category_mapping('{"asiatisch":"International","asiatisch/curry":"Currys"}')
    assert m_json["asiatisch"] == "International"
    assert m_json["asiatisch/curry"] == "Currys"

    m_kv = _parse_category_mapping("suppe=Suppen; pasta/vegetarisch=Pasta")
    assert m_kv["suppe"] == "Suppen"
    assert m_kv["pasta/vegetarisch"] == "Pasta"


def test_resolve_section_and_title_with_subcategory_prefix():
    rezept = {"titel": "Rotes Curry", "kategorie": "Asiatisch/Curry"}
    mapping = {"asiatisch": "International"}
    section, title = _resolve_target_section_and_title(rezept, "Inbox", mapping, "/", True)
    assert section == "International"
    assert title == "[Curry] Rotes Curry"


def test_resolve_section_and_title_without_mapping_or_subprefix():
    rezept = {"titel": "Linsensuppe", "kategorie": "Suppen/Vegetarisch"}
    section, title = _resolve_target_section_and_title(rezept, "Inbox", {}, "/", False)
    assert section == "Suppen"
    assert title == "Linsensuppe"
