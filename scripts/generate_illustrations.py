#!/usr/bin/env python3
"""
Generate UI illustrations for DotMac ERP using Google Gemini API.

Usage:
    python scripts/generate_illustrations.py --api-key YOUR_KEY
    # or set GEMINI_API_KEY env var
    GEMINI_API_KEY=your_key python scripts/generate_illustrations.py

Generates consistent illustrations for empty states, module selector,
login page, and error pages. Saves to static/img/illustrations/.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from pathlib import Path

from google import genai
from google.genai import types

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "static" / "img" / "illustrations"

# Consistent brand style prefix for all prompts
STYLE_PREFIX = (
    "Minimal flat illustration, clean vector style, soft gradients. "
    "Primary color: teal (#0d9488). Accent color: warm gold (#d97706). "
    "Secondary: soft slate gray (#94a3b8). "
    "White/transparent background. No text, no words, no labels, no watermarks. "
    "Subtle shadow beneath main element. "
    "Modern, professional, friendly — like Notion or Linear empty states. "
    "Simple composition, centered subject, plenty of negative space. "
)

# Each illustration: (filename, prompt_suffix, description)
ILLUSTRATIONS: list[tuple[str, str, str]] = [
    (
        "empty-invoices.png",
        "A single elegant document page with a subtle teal checkmark, "
        "floating slightly above a soft shadow. A small gold coin beside it. "
        "Conveys: no invoices yet, ready to create one.",
        "Empty state: No invoices",
    ),
    (
        "empty-transactions.png",
        "A minimalist bank card with gentle teal gradient, "
        "with three small horizontal lines suggesting transaction rows that fade out. "
        "A subtle sparkle on the card corner. "
        "Conveys: no transactions yet.",
        "Empty state: No transactions",
    ),
    (
        "empty-employees.png",
        "Three abstract person silhouettes (head + shoulders) in varying sizes, "
        "the center one teal, flanking ones in light slate gray. "
        "Gentle overlap. Conveys: no team members added yet.",
        "Empty state: No employees",
    ),
    (
        "empty-inventory.png",
        "An open cardboard box viewed from slight above angle, "
        "with a teal glow inside suggesting emptiness with potential. "
        "A small gold tag hanging from the side. "
        "Conveys: empty warehouse, ready to stock.",
        "Empty state: No inventory items",
    ),
    (
        "empty-claims.png",
        "A receipt or expense slip with a dotted outline, "
        "a small teal circular arrow suggesting submission flow. "
        "A tiny gold coin stack beside it. "
        "Conveys: no expense claims submitted.",
        "Empty state: No expense claims",
    ),
    (
        "empty-search.png",
        "A magnifying glass with teal-tinted lens, "
        "looking at empty space with subtle dotted circles radiating outward. "
        "Conveys: search returned no results.",
        "Empty state: No search results",
    ),
    (
        "getting-started.png",
        "A small teal rocket launching upward from a gold launchpad, "
        "with a gentle curved trail. Minimal cloud wisps. "
        "Conveys: getting started, first launch, onboarding.",
        "Onboarding: Getting started",
    ),
    (
        "error-404.png",
        "A compass with the needle pointing to a question mark, "
        "teal compass body with gold needle and accents. "
        "Slightly tilted. Conveys: lost, page not found.",
        "Error: 404 page not found",
    ),
    (
        "empty-reports.png",
        "A minimal bar chart with three bars of different heights, "
        "in teal with the tallest bar having a gold accent cap. "
        "A subtle grid behind. Conveys: no report data yet.",
        "Empty state: No reports",
    ),
    (
        "empty-approvals.png",
        "A clipboard with a single checkbox, unchecked, "
        "with a teal pen resting diagonally across it. "
        "Gold clip at the top. Conveys: no pending approvals.",
        "Empty state: No pending approvals",
    ),
]


def generate_illustration(
    client: genai.Client,
    filename: str,
    prompt_suffix: str,
    description: str,
    output_dir: Path,
    model: str = "gemini-2.5-flash-preview-05-20",
) -> bool:
    """Generate a single illustration and save it."""
    output_path = output_dir / filename

    if output_path.exists():
        logger.info("  SKIP %s (already exists)", filename)
        return True

    full_prompt = STYLE_PREFIX + prompt_suffix

    logger.info("  Generating %s — %s", filename, description)

    try:
        response = client.models.generate_content(
            model=model,
            contents=[full_prompt],
            config=types.GenerateContentConfig(
                response_modalities=["TEXT", "IMAGE"],
            ),
        )

        for part in response.candidates[0].content.parts:
            if part.inline_data is not None:
                image = part.as_image()
                image.save(str(output_path))
                logger.info(
                    "  SAVED %s (%s bytes)", filename, output_path.stat().st_size
                )
                return True

        logger.warning("  WARN %s — no image in response", filename)
        return False

    except Exception as e:
        logger.error("  FAIL %s — %s", filename, e)
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate DotMac ERP illustrations")
    parser.add_argument("--api-key", default=os.environ.get("GEMINI_API_KEY", ""))
    parser.add_argument("--model", default="gemini-2.5-flash-preview-05-20")
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    parser.add_argument("--only", help="Generate only this filename")
    parser.add_argument("--force", action="store_true", help="Overwrite existing files")
    args = parser.parse_args()

    if not args.api_key:
        logger.error("Set GEMINI_API_KEY or pass --api-key")
        sys.exit(1)

    args.output_dir.mkdir(parents=True, exist_ok=True)

    client = genai.Client(api_key=args.api_key)

    illustrations = ILLUSTRATIONS
    if args.only:
        illustrations = [(f, p, d) for f, p, d in ILLUSTRATIONS if f == args.only]
        if not illustrations:
            logger.error("No illustration named '%s'", args.only)
            sys.exit(1)

    if args.force:
        for filename, _, _ in illustrations:
            path = args.output_dir / filename
            if path.exists():
                path.unlink()

    logger.info(
        "Generating %d illustrations → %s\n", len(illustrations), args.output_dir
    )

    success = 0
    for i, (filename, prompt_suffix, description) in enumerate(illustrations):
        if generate_illustration(
            client, filename, prompt_suffix, description, args.output_dir, args.model
        ):
            success += 1

        # Rate limiting — be polite to the free tier
        if i < len(illustrations) - 1:
            time.sleep(2)

    logger.info("\nDone: %d/%d generated", success, len(illustrations))


if __name__ == "__main__":
    main()
