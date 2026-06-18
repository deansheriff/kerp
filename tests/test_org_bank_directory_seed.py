from app.services.settings.bank_directory import _load_bank_rows


def test_default_org_bank_rows_are_unique_by_name_and_sort_code():
    rows = list(_load_bank_rows())

    names = [bank_name.lower() for bank_name, _ in rows]
    sort_codes = [bank_sort_code for _, bank_sort_code in rows]

    assert rows
    assert len(names) == len(set(names))
    assert len(sort_codes) == len(set(sort_codes))
