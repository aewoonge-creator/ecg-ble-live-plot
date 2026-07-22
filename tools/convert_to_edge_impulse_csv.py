#!/usr/bin/env python3
"""
Convert ECG CSV recordings into an Edge Impulse upload-friendly CSV.

Typical inputs supported:
- ECG BLE GUI export:
  time_s,adc_or_sample,input_v,filtered_v,source
- Offline filtered output:
  time_s,raw_voltage,after_notch60,after_notch60_lpf40

Default output:
  timestamp,ecg,label

For HR regression experiments, add a known target:
  timestamp,ecg,hr,label
"""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timedelta
from pathlib import Path


SIGNAL_CANDIDATES = [
    "filtered_v",
    "after_notch60_lpf40",
    "after_lpf40",
    "ecg",
    "input_v",
    "raw_voltage",
    "adc_or_sample",
    "value",
]

TIME_CANDIDATES = ["time_s", "time", "timestamp", "t", "t_s", "ms", "time_ms"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert nRF54L15/ECG CSV data to Edge Impulse Data Acquisition CSV format."
    )
    parser.add_argument("input_csv", type=Path, help="Input CSV saved from GitHub GUI or filtering tools.")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Output CSV path. Default: <input>_edge_impulse.csv next to input.",
    )
    parser.add_argument(
        "--signal-col",
        default="auto",
        help="Signal column to export as ecg. Use 'auto' to pick filtered_v/after_notch60_lpf40/etc.",
    )
    parser.add_argument(
        "--time-col",
        default="auto",
        help="Time column. Use 'auto', a column name, or 'none' to synthesize time from --fs.",
    )
    parser.add_argument("--fs", type=float, default=500.0, help="Sampling rate used when time column is absent.")
    parser.add_argument("--label", default="ecg_recording", help="Label value written to every row.")
    parser.add_argument(
        "--hr",
        type=float,
        default=None,
        help="Optional known heart-rate target in BPM. Add this only when you have a reliable ground truth.",
    )
    parser.add_argument(
        "--start-time",
        default="2026-07-22 00:00:00",
        help="Datetime used for output timestamp column. Format: YYYY-MM-DD HH:MM:SS",
    )
    parser.add_argument(
        "--keep-source",
        action="store_true",
        help="Keep original source column when present.",
    )
    return parser.parse_args()


def normalize_header(name: str) -> str:
    return name.strip().lower().replace(" ", "_")


def pick_column(headers: list[str], requested: str, candidates: list[str], kind: str) -> str | None:
    normalized = {normalize_header(h): h for h in headers}
    if requested and requested.lower() == "none":
        return None
    if requested and requested.lower() != "auto":
        key = normalize_header(requested)
        if key not in normalized:
            raise SystemExit(f"Cannot find {kind} column '{requested}'. Available columns: {', '.join(headers)}")
        return normalized[key]
    for candidate in candidates:
        if candidate in normalized:
            return normalized[candidate]
    return None


def parse_float(value: str, row_num: int, col: str) -> float:
    try:
        return float(str(value).strip())
    except ValueError as exc:
        raise SystemExit(f"Row {row_num}: cannot parse numeric value in column '{col}': {value!r}") from exc


def seconds_from_value(value: str, row_num: int, time_col: str) -> float:
    raw = str(value).strip()
    if not raw:
        raise SystemExit(f"Row {row_num}: empty time value in column '{time_col}'")
    try:
        t = float(raw)
    except ValueError:
        parsed = datetime.fromisoformat(raw)
        return parsed.timestamp()
    if normalize_header(time_col) in {"ms", "time_ms"}:
        return t / 1000.0
    return t


def convert(args: argparse.Namespace) -> Path:
    input_path = args.input_csv
    if not input_path.exists():
        raise SystemExit(f"Input file not found: {input_path}")

    output_path = args.output or input_path.with_name(f"{input_path.stem}_edge_impulse.csv")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    start = datetime.strptime(args.start_time, "%Y-%m-%d %H:%M:%S")

    with input_path.open("r", newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise SystemExit("Input CSV has no header row.")
        headers = reader.fieldnames
        signal_col = pick_column(headers, args.signal_col, SIGNAL_CANDIDATES, "signal")
        time_col = pick_column(headers, args.time_col, TIME_CANDIDATES, "time")
        if signal_col is None:
            raise SystemExit(
                "Could not auto-detect signal column. Use --signal-col. "
                f"Available columns: {', '.join(headers)}"
            )

        out_headers = ["timestamp", "ecg"]
        if args.hr is not None:
            out_headers.append("hr")
        out_headers.append("label")
        source_col = pick_column(headers, "source", [], "source") if args.keep_source else None
        if source_col:
            out_headers.append("source")

        rows_written = 0
        first_time_s = None
        with output_path.open("w", newline="", encoding="utf-8") as out:
            writer = csv.DictWriter(out, fieldnames=out_headers)
            writer.writeheader()
            for row_num, row in enumerate(reader, start=2):
                if not any(str(v).strip() for v in row.values() if v is not None):
                    continue

                ecg = parse_float(row.get(signal_col, ""), row_num, signal_col)
                if time_col is None:
                    relative_s = rows_written / args.fs
                else:
                    current_s = seconds_from_value(row.get(time_col, ""), row_num, time_col)
                    if first_time_s is None:
                        first_time_s = current_s
                    relative_s = current_s - first_time_s

                output_row = {
                    "timestamp": (start + timedelta(seconds=relative_s)).strftime("%Y-%m-%d %H:%M:%S.%f"),
                    "ecg": f"{ecg:.10g}",
                    "label": args.label,
                }
                if args.hr is not None:
                    output_row["hr"] = f"{args.hr:.6g}"
                if source_col:
                    output_row["source"] = row.get(source_col, "")
                writer.writerow(output_row)
                rows_written += 1

    print(f"Wrote {rows_written} rows")
    print(f"Signal column: {signal_col}")
    print(f"Time column: {time_col or f'synthesized from fs={args.fs:g} Hz'}")
    print(f"Output: {output_path}")
    if args.hr is None:
        print("Note: no HR target was added. Use --hr <BPM> only when you have reliable ground truth.")
    return output_path


if __name__ == "__main__":
    convert(parse_args())
