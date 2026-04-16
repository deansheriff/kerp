"""
Fixed Assets import/export service aliases.

The actual importer implementations currently live in
``app.services.finance.import_export.assets`` and are imported here so the
Fixed Assets module can consume them without pulling in Finance API-level couplings.
"""

from app.services.finance.import_export.assets import (
    AssetCategoryImporter,
    AssetImporter,
)

__all__ = ["AssetCategoryImporter", "AssetImporter"]
