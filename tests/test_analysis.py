from analysis import analyze_recipe, analyze_recipes


def test_analyze_recipe_detects_missing_fields_and_warnings():
    result = analyze_recipe({"titel": "", "kategorie": "", "zutaten": ["Pancetta"], "schritte": []})
    assert "Titel fehlt oder ist unklar" in result["issues"]
    assert "Kategorie fehlt" in result["warnings"]
    assert any("Verarbeitetes Fleisch" in w for w in result["warnings"])
    assert result["health"]["prostata_krebs"] == "bedingt"


def test_analyze_recipes_summary():
    recipes = [
        {"titel": "Haferfrühstück", "kategorie": "Frühstück", "zutaten": ["80 g Haferflocken", "100 g Beeren"], "schritte": ["Mischen"]},
        {"titel": "", "kategorie": "", "zutaten": [], "schritte": []},
    ]
    report = analyze_recipes(recipes)
    assert report["summary"]["count"] == 2
    assert report["summary"]["total_issues"] >= 1
    assert len(report["items"]) == 2


def test_similar_candidates_detected_for_napoli_like_recipes():
    recipes = [
        {"titel": "Spaghetti Napoli", "kategorie": "Pasta", "zutaten": ["200 g Spaghetti", "Tomatensauce", "Knoblauch"], "schritte": ["Kochen"]},
        {"titel": "Nudeln mit Tomatensosse", "kategorie": "Pasta", "zutaten": ["200 g Nudeln", "Tomatensoße", "Kräuter"], "schritte": ["Kochen"]},
    ]
    report = analyze_recipes(recipes, similarity_threshold=0.35)
    assert report["summary"]["similar_candidates"] == 1
    assert report["similar_candidates"][0]["similarity"] >= 0.35
