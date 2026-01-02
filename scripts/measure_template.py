"""Helper utility for measuring OMR template calibration points.

This placeholder script demonstrates how template measurement tasks can be
structured. Future milestones will integrate with the OpenCV processing in
`src/` to extract precise marker positions.
"""
from __future__ import annotations

import argparse
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Measure template calibration points")
    parser.add_argument("image", type=Path, help="Path to the template scan (PNG)")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.image.exists():
        raise SystemExit(f"Template image not found: {args.image}")

    print("Template measurement helper")
    print("--------------------------------")
    print("Image:", args.image)
    print("Status: Measurement routines will be implemented in Milestone 2.")
    print("For now, inspect the image manually to determine marker coordinates.")


if __name__ == "__main__":
    main()
