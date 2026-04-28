from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

from app.services.finance.import_export.assets import AssetImporter


def test_asset_importer_generates_sequence_number_ignoring_file_value(
    import_config, mock_db, monkeypatch
):
    importer = AssetImporter(
        mock_db,
        import_config,
        uuid4(),
        uuid4(),
        uuid4(),
        uuid4(),
    )

    monkeypatch.setattr(
        "app.services.finance.import_export.assets.SequenceService.get_next_number",
        lambda db, organization_id, sequence_type: "DT-AST-0007",
    )
    monkeypatch.setattr(
        importer._category_importer,
        "get_category_id",
        lambda category_name: uuid4(),
    )
    monkeypatch.setattr(importer, "_resolve_location_id", lambda raw_location: None)

    asset = importer.create_entity(
        {
            "asset_name": "Workstation",
            "asset_number": "Dotmac/OE/BM001",
            "category_name": "Computers",
        }
    )

    assert asset.asset_number == "DT-AST-0007"
    assert asset.asset_name == "Workstation"


def test_asset_importer_duplicate_check_uses_serial_number(import_config, mock_db):
    existing = MagicMock()
    mock_db.execute.return_value.scalar_one_or_none.return_value = existing

    importer = AssetImporter(
        mock_db,
        import_config,
        uuid4(),
        uuid4(),
        uuid4(),
        uuid4(),
    )

    result = importer.check_duplicate({"Serial Number": "8CC9491MB2"})

    assert result == existing


def test_asset_importer_import_rows_handles_uppercase_category_header(
    import_config, mock_db, monkeypatch
):
    importer = AssetImporter(
        mock_db,
        import_config,
        uuid4(),
        uuid4(),
        uuid4(),
        uuid4(),
    )

    monkeypatch.setattr(
        "app.services.finance.import_export.assets.SequenceService.get_next_number",
        lambda db, organization_id, sequence_type: "DT-AST-0008",
    )
    monkeypatch.setattr(
        importer._category_importer,
        "ensure_categories",
        lambda rows: None,
    )
    get_category_id = MagicMock(return_value=uuid4())
    monkeypatch.setattr(importer._category_importer, "get_category_id", get_category_id)
    monkeypatch.setattr(importer, "_resolve_location_id", lambda raw_location: None)

    result = importer.import_rows(
        [
            {
                "ASSET NAME": "All in one Desktop",
                "ASSET CATEGORY": "Computers & Laptops",
                "SERIAL NUMBER": "8CC9491MB2",
                "STATUS": "In use",
            }
        ]
    )

    assert result.imported_count == 1
    get_category_id.assert_called_once_with("Computers & Laptops")


def test_asset_importer_create_entity_assigns_employee_by_email(
    import_config, mock_db, monkeypatch
):
    importer = AssetImporter(
        mock_db,
        import_config,
        uuid4(),
        uuid4(),
        uuid4(),
        uuid4(),
    )
    employee_id = uuid4()
    department_id = uuid4()

    monkeypatch.setattr(
        "app.services.finance.import_export.assets.SequenceService.get_next_number",
        lambda db, organization_id, sequence_type: "DT-AST-0009",
    )
    monkeypatch.setattr(
        importer._category_importer,
        "get_category_id",
        lambda category_name: uuid4(),
    )
    monkeypatch.setattr(importer, "_resolve_location_id", lambda raw_location: None)
    monkeypatch.setattr(
        importer,
        "_resolve_department_id",
        lambda **kwargs: department_id,
    )
    monkeypatch.setattr(
        importer,
        "_resolve_employee_id",
        lambda **kwargs: employee_id,
    )

    asset = importer.create_entity(
        {
            "asset_name": "Workstation",
            "category_name": "Computers",
            "department_name": "Admin",
            "assign_to": "ada@example.com",
        }
    )

    assert asset.custodian_employee_id == employee_id


def test_asset_importer_resolve_department_name_is_case_insensitive(
    import_config, mock_db
):
    importer = AssetImporter(
        mock_db,
        import_config,
        uuid4(),
        uuid4(),
        uuid4(),
        uuid4(),
    )
    department_id = uuid4()
    importer._department_lookup_loaded = True
    importer._department_by_normalized_name = {
        "human resources": [(department_id, "Human Resources")]
    }

    resolved = importer._resolve_department_id(department_name="  HUMAN   resources ")

    assert resolved == department_id


def test_asset_importer_department_name_suggests_closest_match(import_config, mock_db):
    importer = AssetImporter(
        mock_db,
        import_config,
        uuid4(),
        uuid4(),
        uuid4(),
        uuid4(),
    )
    importer._department_lookup_loaded = True
    importer._department_by_normalized_name = {
        "admin": [(uuid4(), "Admin")],
        "finance": [(uuid4(), "Finance")],
    }

    try:
        importer._resolve_department_id(department_name="Admins")
    except ValueError as exc:
        message = str(exc)
    else:
        raise AssertionError("Expected ValueError for unknown department")

    assert 'Department "Admins" not found.' in message
    assert "Did you mean: Admin?" in message


def test_asset_importer_department_name_rejects_ambiguous_match(import_config, mock_db):
    importer = AssetImporter(
        mock_db,
        import_config,
        uuid4(),
        uuid4(),
        uuid4(),
        uuid4(),
    )
    importer._department_lookup_loaded = True
    importer._department_by_normalized_name = {
        "finance and admin": [
            (uuid4(), "Finance & Admin"),
            (uuid4(), "Finance and Admin"),
        ]
    }

    try:
        importer._resolve_department_id(department_name="Finance and Admin")
    except ValueError as exc:
        message = str(exc)
    else:
        raise AssertionError("Expected ValueError for ambiguous department")

    assert 'Ambiguous department "Finance and Admin"' in message


def test_asset_importer_resolve_employee_by_email_and_department(
    import_config, mock_db
):
    importer = AssetImporter(
        mock_db,
        import_config,
        uuid4(),
        uuid4(),
        uuid4(),
        uuid4(),
    )
    employee_id = uuid4()
    department_id = uuid4()
    importer._employee_lookup_loaded = True
    importer._employee_by_email = {
        "ada@example.com": [(employee_id, "Ada Lovelace", str(department_id))]
    }

    resolved = importer._resolve_employee_id(
        employee_email="Ada@example.com",
        department_id=department_id,
    )

    assert resolved == employee_id


def test_asset_importer_import_rows_reports_department_suggestion_error(
    import_config, mock_db, monkeypatch
):
    importer = AssetImporter(
        mock_db,
        import_config,
        uuid4(),
        uuid4(),
        uuid4(),
        uuid4(),
    )

    monkeypatch.setattr(
        "app.services.finance.import_export.assets.SequenceService.get_next_number",
        lambda db, organization_id, sequence_type: "DT-AST-0010",
    )
    monkeypatch.setattr(
        importer._category_importer, "ensure_categories", lambda rows: None
    )
    monkeypatch.setattr(
        importer._category_importer,
        "get_category_id",
        lambda category_name: uuid4(),
    )
    monkeypatch.setattr(importer, "_resolve_location_id", lambda raw_location: None)
    monkeypatch.setattr(
        importer,
        "_resolve_department_id",
        lambda **kwargs: (_ for _ in ()).throw(
            ValueError('Department "Admins" not found. Did you mean: Admin?')
        ),
    )

    result = importer.import_rows(
        [
            {
                "Asset Name": "Laptop",
                "Asset Category": "Computers",
                "Department": "Admins",
            }
        ]
    )

    assert result.imported_count == 0
    assert result.error_count == 1
    assert (
        'Department "Admins" not found. Did you mean: Admin?'
        in result.errors[0].message
    )
