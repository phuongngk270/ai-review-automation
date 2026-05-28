from pathlib import Path

from automation.combos import Combo, RowMapping, iter_combos, load_combos


def test_loads_67_combos():
    combos = load_combos()
    assert len(combos) == 67
    assert combos[0].profile_name.startswith("C01")


def test_combo_paths_resolve_to_existing_pdfs():
    for combo in load_combos():
        assert combo.sub_doc_path.is_file(), combo.sub_doc_path
        for sd in combo.supporting_doc_paths:
            assert sd.is_file(), sd


def test_combo_has_at_least_one_row_mapping():
    for combo in load_combos():
        assert combo.rows, combo.profile_name
        assert all(isinstance(r, RowMapping) for r in combo.rows)


def test_c04_has_six_rows():
    by_name = {c.profile_name: c for c in load_combos()}
    c04 = by_name["C04-TC-01-PASS"]
    assert {r.row for r in c04.rows} == {5, 13, 19, 28, 48, 81}
    assert {r.cnum for r in c04.rows} == {"C1", "C2", "C4", "C6", "C9", "C17"}
