from health_rules import build_health_assessments


def test_processed_meat_is_marked_red_for_health_review():
    recipe = {
        "zutaten": ["100 g Bacon", "2 Eier"],
        "quality": {"status": "ok"},
        "uncertainty": {"overall": "low"},
    }
    health = build_health_assessments(recipe)
    assert health["assessments"][0]["light"] == "red"
    assert health["assessments"][0]["requires_review"] is True


def test_protective_recipe_can_be_marked_green():
    recipe = {
        "zutaten": ["80 g Haferflocken", "100 g Beeren", "1 Banane"],
        "quality": {"status": "ok"},
        "uncertainty": {"overall": "low"},
    }
    health = build_health_assessments(recipe)
    assert all(item["light"] == "green" for item in health["assessments"])


def test_problematic_or_uncertain_recipe_is_unrated():
    recipe = {
        "zutaten": ["100 g Bacon"],
        "quality": {"status": "problematisch"},
        "uncertainty": {"overall": "high"},
    }
    health = build_health_assessments(recipe)
    assert all(item["light"] == "unrated" for item in health["assessments"])
    assert all(item["requires_review"] is True for item in health["assessments"])
