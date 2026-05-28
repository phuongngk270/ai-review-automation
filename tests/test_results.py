from automation.results import (
    CHECK_DEFINITION_ID_TO_CNUM,
    Outcome,
    map_results_to_outcomes,
)
from automation.review import CheckResult


def test_check_table_has_21_entries():
    # The SKILL.md says "22 checks" but C16 is skipped, so C1..C15 + C17..C22 = 21.
    # The 22nd live result ("test") is noise and not mapped.
    assert len(CHECK_DEFINITION_ID_TO_CNUM) == 21


def test_check_table_skips_c16():
    cnums = set(CHECK_DEFINITION_ID_TO_CNUM.values())
    assert "C16" not in cnums
    assert cnums == {f"C{i}" for i in list(range(1, 16)) + list(range(17, 23))}


def test_map_results_to_outcomes_translates_assessments():
    results = [
        CheckResult(check_definition_id="chkdyjqpygoropzx", check_name="W-8IMY", assessment="NOT_APPLICABLE"),
        CheckResult(check_definition_id="chkdlg3d7o6lg5lw", check_name="Tax Form Field Completeness", assessment="PASS"),
    ]
    outcomes = map_results_to_outcomes(results)
    assert outcomes["C5"].sheet_value == "NOT_APPLICABLE"
    assert outcomes["C1"].sheet_value == "PASS"


def test_map_results_skips_unknown_check_id():
    # The "test" noise check id is intentionally excluded from the fixture
    results = [
        CheckResult(check_definition_id="chkd00vn82l30mzp", check_name="test", assessment="UNKNOWN"),
    ]
    outcomes = map_results_to_outcomes(results)
    assert outcomes == {}


def test_outcome_values_are_normalized():
    assert Outcome.from_assessment("PASS").sheet_value == "PASS"
    assert Outcome.from_assessment("FAIL").sheet_value == "FAIL"
    assert Outcome.from_assessment("UNKNOWN").sheet_value == "UNKNOWN"
    assert Outcome.from_assessment("NOT_APPLICABLE").sheet_value == "NOT_APPLICABLE"
    assert Outcome.from_assessment("ERROR").sheet_value == "UNKNOWN"
