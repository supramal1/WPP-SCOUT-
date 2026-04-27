#!/usr/bin/env python3
"""WPP Scout - Google Pixel Campaign Analysis

Scores social media creatives based on objective-aligned metrics,
spend significance, and frequency fatigue. Produces ranked output
with plain-English explanations of why each creative performed well or poorly.
"""

import argparse
import sys
from pathlib import Path

from src.loader import load_data
from src.scorer import score_creatives, score_raw_variants
from src.explainer import generate_explanations
from src.reporter import print_console_report, export_excel, export_looker_csv


def main():
    parser = argparse.ArgumentParser(
        description='Analyze creative performance from social media campaign data.'
    )
    parser.add_argument(
        'input_file',
        help='Path to the Excel file containing campaign data',
    )
    parser.add_argument(
        '-o', '--output',
        default=None,
        help='Output Excel file path (default: creative_analysis_output.xlsx in same directory)',
    )
    parser.add_argument(
        '--min-spend',
        type=float,
        default=500,
        help='Minimum spend threshold for statistical significance (default: €500)',
    )
    parser.add_argument(
        '--min-reach',
        type=int,
        default=10000,
        help='Minimum reach threshold for statistical significance (default: 10,000)',
    )
    parser.add_argument(
        '--looker-csv',
        default=None,
        metavar='PATH',
        help='Also export a flat XLSX for Looker Studio upload (e.g. looker_export.xlsx)',
    )
    parser.add_argument(
        '--brand',
        default='',
        help='Brand name to display in report headers (e.g. "Google Pixel")',
    )
    parser.add_argument(
        '--google-sheets',
        action='store_true',
        help='Export a Google Sheets-friendly XLSX variant intended for upload/import into Google Sheets',
    )
    args = parser.parse_args()

    input_path = Path(args.input_file)
    if not input_path.exists():
        print(f"Error: File not found: {input_path}")
        sys.exit(1)

    if args.output:
        output_path = args.output
    elif args.google_sheets:
        output_path = str(input_path.parent / 'creative_analysis_google_sheets.xlsx')
    else:
        output_path = str(input_path.parent / 'creative_analysis_output.xlsx')

    print(f"Loading data from: {input_path}")
    df_raw, df = load_data(str(input_path))
    print(f"Loaded {len(df)} creative concepts ({len(df_raw)} ad lines) across {df['platform'].nunique()} platforms")

    # Allow custom thresholds
    df['low_confidence'] = (df['spend'] < args.min_spend) | (df['reach'] < args.min_reach)

    print("Scoring creatives...")
    scored = score_creatives(df)

    print("Scoring raw variants (split analysis)...")
    df_raw_scored = score_raw_variants(df_raw)

    # Join cross-platform metadata from agg back onto raw variants
    # so Looker Studio can filter/segment by it
    cp_cols = [c for c in ['creative_name', 'cross_platform', 'platforms_active'] if c in scored.columns]
    if len(cp_cols) > 1:
        cp_map = scored.drop_duplicates('creative_name')[cp_cols]
        df_raw_scored = df_raw_scored.merge(cp_map, on='creative_name', how='left')

    print("Generating explanations...")
    explained = generate_explanations(scored)

    print_console_report(explained, brand=args.brand)
    export_excel(
        explained,
        output_path,
        df_raw=df_raw_scored,
        brand=args.brand,
        target='google_sheets' if args.google_sheets else 'excel',
    )

    if args.looker_csv:
        export_looker_csv(df_raw_scored, args.looker_csv)


if __name__ == '__main__':
    main()
