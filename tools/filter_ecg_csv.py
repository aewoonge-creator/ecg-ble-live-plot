from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path


Coeff = tuple[float, float, float, float, float]


def parse_float(text: str) -> float | None:
    try:
        return float(text.strip())
    except ValueError:
        return None


def read_numeric_csv(path: Path, skiprows: int | None) -> list[list[float]]:
    rows: list[list[float]] = []
    with path.open("r", newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        for row_index, row in enumerate(reader):
            if skiprows is not None and row_index < skiprows:
                continue
            values = [parse_float(cell) for cell in row]
            numeric = [v for v in values if v is not None]
            if numeric:
                rows.append(numeric)

    if not rows:
        raise ValueError(f"No numeric rows found in {path}")
    return rows


def column(rows: list[list[float]], col: int) -> list[float]:
    out: list[float] = []
    for row in rows:
        if col >= len(row):
            raise ValueError(f"CSV row has only {len(row)} numeric columns; requested column {col}")
        out.append(row[col])
    return out


def make_time(rows: list[list[float]], time_col: int | None, fs: float | None) -> tuple[list[float], float]:
    if time_col is not None:
        t = column(rows, time_col)
        t0 = t[0]
        t = [v - t0 for v in t]
        diffs = [t[i + 1] - t[i] for i in range(len(t) - 1) if t[i + 1] > t[i]]
        if not diffs:
            raise ValueError("Could not estimate sampling rate from time column")
        diffs_sorted = sorted(diffs)
        dt = diffs_sorted[len(diffs_sorted) // 2]
        return t, 1.0 / dt

    if fs is None:
        raise ValueError("No time column was provided. Use --fs, for example --fs 500")
    return [i / fs for i in range(len(rows))], fs


def adc_to_voltage(
    x: list[float],
    adc_bits: int | None,
    adc_vref: float | None,
    adc_center: float | None,
    afe_gain: float,
    signed_adc: bool,
) -> list[float]:
    if adc_bits is None or adc_vref is None:
        return x

    gain = max(afe_gain, 1e-12)
    if signed_adc:
        full_scale = 2 ** (adc_bits - 1)
        return [v / full_scale * adc_vref / gain for v in x]

    full_scale = 2**adc_bits - 1
    center = adc_center if adc_center is not None else 2 ** (adc_bits - 1)
    return [(v - center) / full_scale * adc_vref / gain for v in x]


def mean(x: list[float]) -> float:
    return sum(x) / len(x)


def biquad_filter(x: list[float], coeff: Coeff) -> list[float]:
    b0, b1, b2, a1, a2 = coeff
    y: list[float] = []
    x1 = x2 = 0.0
    y1 = y2 = 0.0
    for x0 in x:
        y0 = b0 * x0 + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2
        y.append(y0)
        x2, x1 = x1, x0
        y2, y1 = y1, y0
    return y


def forward_backward(x: list[float], coeff: Coeff) -> list[float]:
    y = biquad_filter(x, coeff)
    y = list(reversed(y))
    y = biquad_filter(y, coeff)
    return list(reversed(y))


def biquad_coeff(kind: str, fs: float, f0: float, q: float) -> Coeff:
    if not 0 < f0 < fs / 2:
        raise ValueError(f"{kind} frequency must be between 0 and Nyquist; got {f0:g} Hz at fs={fs:g} Hz")

    w0 = 2.0 * math.pi * f0 / fs
    c = math.cos(w0)
    alpha = math.sin(w0) / (2.0 * q)

    if kind == "lowpass":
        b0 = (1.0 - c) / 2.0
        b1 = 1.0 - c
        b2 = (1.0 - c) / 2.0
    elif kind == "highpass":
        b0 = (1.0 + c) / 2.0
        b1 = -(1.0 + c)
        b2 = (1.0 + c) / 2.0
    elif kind == "notch":
        b0 = 1.0
        b1 = -2.0 * c
        b2 = 1.0
    else:
        raise ValueError(f"Unsupported filter kind: {kind}")

    a0 = 1.0 + alpha
    a1 = -2.0 * c
    a2 = 1.0 - alpha
    return b0 / a0, b1 / a0, b2 / a0, a1 / a0, a2 / a0


def filter_ecg(raw_v: list[float], fs: float, hpf_hz: float, notch_hz: float, notch_q: float, lpf_hz: float, keep_dc: bool) -> tuple[list[float], list[float], list[float]]:
    x = raw_v[:] if keep_dc else [v - mean(raw_v) for v in raw_v]

    after_hpf = forward_backward(x, biquad_coeff("highpass", fs, hpf_hz, 1 / math.sqrt(2)))
    after_notch = forward_backward(after_hpf, biquad_coeff("notch", fs, notch_hz, notch_q))
    after_lpf = forward_backward(after_notch, biquad_coeff("lowpass", fs, lpf_hz, 1 / math.sqrt(2)))
    return after_hpf, after_notch, after_lpf


def write_csv(path: Path, t: list[float], raw_v: list[float], after_hpf: list[float], after_notch: list[float], after_lpf: list[float]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["time_s", "raw_voltage", "after_hpf", "after_hpf_notch", "after_hpf_notch_lpf"])
        for values in zip(t, raw_v, after_hpf, after_notch, after_lpf):
            writer.writerow([f"{v:.10g}" for v in values])


def points_for_svg(t: list[float], y: list[float], x0: int, y0: int, width: int, height: int, max_points: int = 2500) -> str:
    step = max(1, len(t) // max_points)
    tt = t[::step]
    yy = y[::step]

    t_min, t_max = min(tt), max(tt)
    y_min, y_max = min(yy), max(yy)
    if y_max == y_min:
        y_max = y_min + 1.0

    pts = []
    for tx, vy in zip(tt, yy):
        px = x0 + (tx - t_min) / (t_max - t_min) * width if t_max != t_min else x0
        py = y0 + height - (vy - y_min) / (y_max - y_min) * height
        pts.append(f"{px:.1f},{py:.1f}")
    return " ".join(pts)


def write_svg(path: Path, t: list[float], raw_v: list[float], after_hpf: list[float], after_notch: list[float], after_lpf: list[float]) -> None:
    width = 1200
    panel_h = 185
    margin = 54
    total_h = margin * 2 + panel_h * 4
    series = [
        ("Raw / ADC converted", raw_v, "#2563eb"),
        ("After HPF", after_hpf, "#9333ea"),
        ("After HPF + 60 Hz notch", after_notch, "#16a34a"),
        ("After HPF + 60 Hz notch + 40 Hz LPF", after_lpf, "#dc2626"),
    ]

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{total_h}" viewBox="0 0 {width} {total_h}">',
        '<rect width="100%" height="100%" fill="white"/>',
        '<style>text{font-family:Arial,sans-serif;font-size:17px;fill:#111827}.sig{fill:none;stroke-width:1.4}</style>',
    ]

    for i, (title, y, color) in enumerate(series):
        y_top = margin + i * panel_h
        x_left = 70
        plot_w = width - 120
        plot_h = panel_h - 52
        lines.append(f'<text x="{x_left}" y="{y_top - 14}">{title}</text>')
        lines.append(f'<rect x="{x_left}" y="{y_top}" width="{plot_w}" height="{plot_h}" fill="#f9fafb" stroke="#d1d5db"/>')
        pts = points_for_svg(t, y, x_left, y_top, plot_w, plot_h)
        lines.append(f'<polyline class="sig" stroke="{color}" points="{pts}"/>')
        lines.append(f'<text x="{x_left}" y="{y_top + plot_h + 26}">time: {t[0]:.3g}s to {t[-1]:.3g}s</text>')

    lines.append("</svg>")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Filter ECG CSV data with HPF, 60 Hz notch, and 40 Hz LPF. No external Python packages required.")
    parser.add_argument("csv", type=Path, help="Input CSV file")
    parser.add_argument("--time-col", type=int, default=0, help="0-based time column. Use -1 if there is no time column.")
    parser.add_argument("--value-col", type=int, default=1, help="0-based ADC/voltage column")
    parser.add_argument("--fs", type=float, default=None, help="Sampling rate when there is no time column")
    parser.add_argument("--skiprows", type=int, default=None, help="Header rows to skip. Default: auto-detect numeric rows")
    parser.add_argument("--adc-bits", type=int, default=None, help="ADC bit depth, e.g. 12")
    parser.add_argument("--adc-vref", type=float, default=None, help="ADC reference voltage, e.g. 3.3")
    parser.add_argument("--adc-center", type=float, default=None, help="Unsigned ADC center count, e.g. 2048")
    parser.add_argument("--afe-gain", type=float, default=1.0, help="Analog front-end gain")
    parser.add_argument("--signed-adc", action="store_true", help="Use signed ADC conversion")
    parser.add_argument("--hpf", type=float, default=0.5, help="High-pass cutoff frequency")
    parser.add_argument("--notch", type=float, default=60.0, help="Notch frequency")
    parser.add_argument("--notch-q", type=float, default=30.0, help="Notch Q factor")
    parser.add_argument("--lpf", type=float, default=40.0, help="Low-pass cutoff frequency")
    parser.add_argument("--output-dir", type=Path, default=Path("outputs"))
    parser.add_argument("--keep-dc", action="store_true", help="Do not subtract mean before filtering")
    args = parser.parse_args()

    rows = read_numeric_csv(args.csv, args.skiprows)
    time_col = None if args.time_col < 0 else args.time_col
    t, fs = make_time(rows, time_col, args.fs)

    raw_input = column(rows, args.value_col)
    raw_v = adc_to_voltage(raw_input, args.adc_bits, args.adc_vref, args.adc_center, args.afe_gain, args.signed_adc)

    after_hpf, after_notch, after_lpf = filter_ecg(
        raw_v,
        fs,
        hpf_hz=args.hpf,
        notch_hz=args.notch,
        notch_q=args.notch_q,
        lpf_hz=args.lpf,
        keep_dc=args.keep_dc,
    )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    out_base = f"{args.csv.stem}_hpf{args.hpf:g}_notch{args.notch:g}_lpf{args.lpf:g}"
    out_csv = args.output_dir / f"{out_base}.csv"
    out_svg = args.output_dir / f"{out_base}.svg"

    write_csv(out_csv, t, raw_v, after_hpf, after_notch, after_lpf)
    write_svg(out_svg, t, raw_v, after_hpf, after_notch, after_lpf)

    print(f"fs = {fs:.3f} Hz")
    print(f"rows = {len(raw_v)}")
    print(f"Saved CSV : {out_csv}")
    print(f"Saved SVG : {out_svg}")


if __name__ == "__main__":
    main()
