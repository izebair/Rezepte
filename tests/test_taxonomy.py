from taxonomy import is_valid_main_category, is_valid_subcategory, resolve_categories


def test_resolve_categories_maps_group_and_subcategory():
    main_category, sub_category, notes = resolve_categories("Hauptgerichte", "Pasta")
    assert main_category == "Hauptgericht"
    assert sub_category == "Pasta"
    assert notes == []


def test_resolve_categories_maps_backen_to_dessert():
    main_category, sub_category, notes = resolve_categories("Backen", "Kuchen")
    assert main_category == "Dessert"
    assert sub_category == "Kuchen & Gebaeck"
    assert notes == []


def test_taxonomy_validation_helpers():
    assert is_valid_main_category("Dessert")
    assert not is_valid_main_category("Beliebig")
    assert is_valid_subcategory("Hauptgericht", "Pasta")
    assert not is_valid_subcategory("Getraenke", "Pasta")
