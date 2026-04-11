from __future__ import annotations

from io import BytesIO

import pytest
from starlette.datastructures import FormData
from starlette.datastructures import UploadFile

from app.services.operations.inv_web import OperationsInventoryWebService


def test_extract_uploads_returns_multiple_images() -> None:
    first = UploadFile(
        filename="one.png",
        file=BytesIO(b"one"),
        headers={"content-type": "image/png"},
    )
    second = UploadFile(
        filename="two.webp",
        file=BytesIO(b"two"),
        headers={"content-type": "image/webp"},
    )

    uploads = OperationsInventoryWebService._extract_uploads(
        FormData([("images", first), ("images", second)]),
        "images",
    )

    assert uploads == [first, second]


def test_validate_return_image_uploads_accepts_supported_images() -> None:
    upload = UploadFile(
        filename="evidence.png",
        file=BytesIO(b"image-bytes"),
        headers={"content-type": "image/png"},
    )

    OperationsInventoryWebService._validate_return_image_uploads([upload])


def test_validate_return_image_uploads_rejects_non_images() -> None:
    upload = UploadFile(
        filename="evidence.pdf",
        file=BytesIO(b"pdf-bytes"),
        headers={"content-type": "application/pdf"},
    )

    with pytest.raises(ValueError, match="Only image files are allowed"):
        OperationsInventoryWebService._validate_return_image_uploads([upload])
