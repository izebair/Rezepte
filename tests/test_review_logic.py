from review import derive_review_status, derive_uncertainty


def test_review_status_rejected_on_validation_errors():
    recipe = {"uncertainty": {"overall": "low"}}
    status = derive_review_status(recipe, ["Pflichtfeld fehlt: Titel"], [])
    assert status == "rejected"


def test_review_status_needs_review_on_warning_findings():
    recipe = {"uncertainty": {"overall": "medium"}}
    findings = [{"severity": "warning", "requires_review": True}]
    status = derive_review_status(recipe, [], findings)
    assert status == "needs_review"


def test_review_status_approved_when_clean():
    recipe = {"uncertainty": {"overall": "low"}}
    status = derive_review_status(recipe, [], [])
    assert status == "approved"


def test_uncertainty_high_when_errors_exist():
    uncertainty = derive_uncertainty({}, ["Fehler"], [])
    assert uncertainty["overall"] == "high"
    assert uncertainty["reasons"]
