#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass
from datetime import UTC, date, datetime
from html import escape
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlencode
from urllib.request import urlopen


BASE_URL = "https://api.stlouisfed.org/fred/series/observations"
DEFAULT_TITLE = "Gold Pricing: Three-Layer Structure"
DEFAULT_START_DATE = "2025-09-01"
CHART_FILENAME = "gold_pricing_three_layer.svg"
SUMMARY_FILENAME = "gold_pricing_three_layer.json"
DEFAULT_SERIES = (
    {
        "name": "10Y Real Yield (Core)",
        "series_id": "DFII10",
        "color": "#1f77b4",
        "stroke_width": 2.4,
        "dasharray": "",
    },
    {
        "name": "10Y Term Premium (Risk)",
        "series_id": "THREEFYTP10",
        "color": "#d62728",
        "stroke_width": 2.0,
        "dasharray": "8 6",
    },
    {
        "name": "5Y Real Yield (Policy)",
        "series_id": "DFII5",
        "color": "#2ca02c",
        "stroke_width": 1.8,
        "dasharray": "",
    },
)


@dataclass(frozen=True)
class SeriesConfig:
    name: str
    series_id: str
    color: str
    stroke_width: float
    dasharray: str = ""


def iso_today() -> str:
    return datetime.now(UTC).date().isoformat()


def load_windows_user_env(name: str) -> str:
    if os.name != "nt":
        return ""
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment") as key:
            value, _ = winreg.QueryValueEx(key, name)
    except (ImportError, OSError):
        return ""
    return str(value or "").strip()


def load_api_key() -> str:
    env_value = str(os.environ.get("FRED_API_KEY", "")).strip()
    if env_value:
        return env_value
    return load_windows_user_env("FRED_API_KEY")


def load_chart_config() -> dict[str, Any]:
    series = [SeriesConfig(**item) for item in DEFAULT_SERIES]
    start_date = str(os.environ.get("STOCK_WATCH_FRED_START_DATE", DEFAULT_START_DATE)).strip() or DEFAULT_START_DATE
    end_date = str(os.environ.get("STOCK_WATCH_FRED_END_DATE", iso_today())).strip() or iso_today()
    return {
        "title": str(os.environ.get("STOCK_WATCH_FRED_TITLE", DEFAULT_TITLE)).strip() or DEFAULT_TITLE,
        "start_date": start_date,
        "end_date": end_date,
        "series": series,
    }


def default_fetcher(url: str) -> dict[str, Any]:
    with urlopen(url, timeout=15) as response:  # noqa: S310 - FRED endpoint is fixed
        return json.loads(response.read().decode("utf-8"))


def build_series_url(series_id: str, api_key: str, start_date: str, end_date: str) -> str:
    params = urlencode(
        {
            "series_id": series_id,
            "api_key": api_key,
            "file_type": "json",
            "observation_start": start_date,
            "observation_end": end_date,
            "sort_order": "asc",
        }
    )
    return f"{BASE_URL}?{params}"


def fetch_series_points(
    series: SeriesConfig,
    *,
    api_key: str,
    start_date: str,
    end_date: str,
    fetcher: Callable[[str], dict[str, Any]],
) -> dict[date, float]:
    payload = fetcher(build_series_url(series.series_id, api_key, start_date, end_date))
    observations = payload.get("observations", [])
    if not isinstance(observations, list):
        raise ValueError(f"FRED response for {series.series_id} is malformed")
    points: dict[date, float] = {}
    for item in observations:
        if not isinstance(item, dict):
            continue
        raw_value = str(item.get("value", "")).strip()
        raw_date = str(item.get("date", "")).strip()
        if not raw_date or raw_value in {"", "."}:
            continue
        try:
            points[date.fromisoformat(raw_date)] = float(raw_value)
        except ValueError:
            continue
    if not points:
        raise ValueError(f"FRED returned no usable observations for {series.series_id}")
    return points


def align_series(points_by_name: dict[str, dict[date, float]]) -> tuple[list[date], dict[str, list[float]]]:
    date_sets = [set(points.keys()) for points in points_by_name.values() if points]
    if not date_sets:
        return [], {}
    shared_dates = sorted(set.intersection(*date_sets))
    if len(shared_dates) < 2:
        return [], {}
    aligned = {
        name: [points[point_date] for point_date in shared_dates]
        for name, points in points_by_name.items()
    }
    return shared_dates, aligned


def value_range(series_values: dict[str, list[float]]) -> tuple[float, float]:
    flat = [value for values in series_values.values() for value in values]
    floor = min(flat)
    ceiling = max(flat)
    if math.isclose(floor, ceiling):
        pad = 1.0 if math.isclose(floor, 0.0) else abs(floor) * 0.1
        return floor - pad, ceiling + pad
    span = ceiling - floor
    pad = span * 0.12
    return floor - pad, ceiling + pad


def render_svg_chart(
    chart_title: str,
    dates: list[date],
    series: list[SeriesConfig],
    series_values: dict[str, list[float]],
) -> str:
    width = 1280
    height = 720
    margin_left = 92
    margin_right = 210
    margin_top = 72
    margin_bottom = 88
    plot_width = width - margin_left - margin_right
    plot_height = height - margin_top - margin_bottom
    y_min, y_max = value_range(series_values)

    def x_position(index: int) -> float:
        if len(dates) == 1:
            return margin_left + plot_width / 2
        return margin_left + (index / (len(dates) - 1)) * plot_width

    def y_position(value: float) -> float:
        if math.isclose(y_max, y_min):
            return margin_top + plot_height / 2
        return margin_top + (y_max - value) / (y_max - y_min) * plot_height

    grid_count = 6
    y_ticks = [y_min + (y_max - y_min) * idx / grid_count for idx in range(grid_count + 1)]
    zero_line = y_position(0.0) if y_min <= 0.0 <= y_max else None

    svg_parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        f'<text x="{margin_left}" y="36" font-size="24" font-family="Arial, sans-serif" font-weight="700" fill="#1f2937">{escape(chart_title)}</text>',
        f'<text x="{margin_left}" y="58" font-size="13" font-family="Arial, sans-serif" fill="#4b5563">{escape(f"Range: {dates[0].isoformat()} to {dates[-1].isoformat()} | Source: FRED")}</text>',
        f'<rect x="{margin_left}" y="{margin_top}" width="{plot_width}" height="{plot_height}" fill="#fcfcfd" stroke="#d1d5db" stroke-width="1"/>',
    ]

    for tick in y_ticks:
        y = y_position(tick)
        svg_parts.append(
            f'<line x1="{margin_left}" y1="{y:.2f}" x2="{margin_left + plot_width}" y2="{y:.2f}" stroke="#e5e7eb" stroke-width="1"/>'
        )
        svg_parts.append(
            f'<text x="{margin_left - 12}" y="{y + 4:.2f}" text-anchor="end" font-size="12" font-family="Arial, sans-serif" fill="#4b5563">{tick:.2f}</text>'
        )

    if zero_line is not None:
        svg_parts.append(
            f'<line x1="{margin_left}" y1="{zero_line:.2f}" x2="{margin_left + plot_width}" y2="{zero_line:.2f}" stroke="#111827" stroke-width="1.2" stroke-dasharray="6 5"/>'
        )

    x_label_indexes = sorted({0, len(dates) - 1, len(dates) // 4, len(dates) // 2, (len(dates) * 3) // 4})
    for idx in x_label_indexes:
        x = x_position(idx)
        svg_parts.append(
            f'<line x1="{x:.2f}" y1="{margin_top + plot_height}" x2="{x:.2f}" y2="{margin_top + plot_height + 6}" stroke="#9ca3af" stroke-width="1"/>'
        )
        svg_parts.append(
            f'<text x="{x:.2f}" y="{margin_top + plot_height + 24}" text-anchor="middle" font-size="12" font-family="Arial, sans-serif" fill="#4b5563">{dates[idx].isoformat()}</text>'
        )

    legend_y = margin_top + 18
    legend_x = margin_left + plot_width + 24
    for idx, series_config in enumerate(series):
        values = series_values[series_config.name]
        point_tokens = [f"{x_position(index):.2f},{y_position(value):.2f}" for index, value in enumerate(values)]
        points_attr = " ".join(point_tokens)
        dash_attr = f' stroke-dasharray="{series_config.dasharray}"' if series_config.dasharray else ""
        svg_parts.append(
            f'<polyline fill="none" stroke="{series_config.color}" stroke-width="{series_config.stroke_width}"{dash_attr} points="{points_attr}"/>'
        )
        last_x = x_position(len(values) - 1)
        last_y = y_position(values[-1])
        svg_parts.append(
            f'<circle cx="{last_x:.2f}" cy="{last_y:.2f}" r="3.4" fill="{series_config.color}"/>'
        )
        svg_parts.append(
            f'<text x="{min(last_x + 8, margin_left + plot_width - 4):.2f}" y="{last_y - 8:.2f}" font-size="11" font-family="Arial, sans-serif" fill="{series_config.color}">{values[-1]:.2f}</text>'
        )

        legend_row_y = legend_y + idx * 28
        svg_parts.append(
            f'<line x1="{legend_x}" y1="{legend_row_y}" x2="{legend_x + 24}" y2="{legend_row_y}" stroke="{series_config.color}" stroke-width="{series_config.stroke_width}"{dash_attr}/>'
        )
        svg_parts.append(
            f'<text x="{legend_x + 34}" y="{legend_row_y + 4}" font-size="12" font-family="Arial, sans-serif" fill="#1f2937">{escape(series_config.name)}</text>'
        )

    svg_parts.extend(
        [
            f'<text x="{margin_left + plot_width / 2:.2f}" y="{height - 22}" text-anchor="middle" font-size="13" font-family="Arial, sans-serif" fill="#374151">Date</text>',
            f'<text x="22" y="{margin_top + plot_height / 2:.2f}" transform="rotate(-90 22 {margin_top + plot_height / 2:.2f})" text-anchor="middle" font-size="13" font-family="Arial, sans-serif" fill="#374151">Yield / Premium (%)</text>',
            "</svg>",
        ]
    )
    return "\n".join(svg_parts) + "\n"


def build_summary_payload(
    *,
    chart_title: str,
    start_date: str,
    end_date: str,
    dates: list[date],
    series: list[SeriesConfig],
    series_values: dict[str, list[float]],
    output_svg_path: Path,
    output_summary_path: Path,
) -> dict[str, Any]:
    latest_values = {
        item.name: {
            "series_id": item.series_id,
            "latest_date": dates[-1].isoformat(),
            "latest_value": round(series_values[item.name][-1], 4),
        }
        for item in series
    }
    return {
        "status": "ok",
        "title": chart_title,
        "requested_start_date": start_date,
        "requested_end_date": end_date,
        "actual_start_date": dates[0].isoformat(),
        "actual_end_date": dates[-1].isoformat(),
        "point_count": len(dates),
        "chart_path": str(output_svg_path),
        "summary_path": str(output_summary_path),
        "latest_values": latest_values,
        "one_line": ", ".join(
            f"{item.name} {latest_values[item.name]['latest_value']:.2f} ({latest_values[item.name]['latest_date']})"
            for item in series
        ),
    }


def skipped_payload(reason: str) -> dict[str, Any]:
    return {
        "status": "skipped",
        "reason": reason,
        "one_line": reason,
    }


def error_payload(message: str) -> dict[str, Any]:
    return {
        "status": "error",
        "error": message,
        "one_line": message,
    }


def generate_gold_pricing_chart(
    workflow_root: Path,
    *,
    fetcher: Callable[[str], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    api_key = load_api_key()
    if not api_key:
        return skipped_payload("FRED_API_KEY is missing, so the macro chart was skipped.")

    config = load_chart_config()
    chart_dir = workflow_root / "macro"
    chart_dir.mkdir(parents=True, exist_ok=True)
    output_svg_path = chart_dir / CHART_FILENAME
    output_summary_path = chart_dir / SUMMARY_FILENAME

    try:
        points_by_name = {
            item.name: fetch_series_points(
                item,
                api_key=api_key,
                start_date=config["start_date"],
                end_date=config["end_date"],
                fetcher=fetcher or default_fetcher,
            )
            for item in config["series"]
        }
        dates, series_values = align_series(points_by_name)
        if len(dates) < 2:
            return skipped_payload("The FRED series did not overlap on enough dates to draw a chart.")
        svg = render_svg_chart(config["title"], dates, config["series"], series_values)
        output_svg_path.write_text(svg, encoding="utf-8")
        payload = build_summary_payload(
            chart_title=config["title"],
            start_date=config["start_date"],
            end_date=config["end_date"],
            dates=dates,
            series=config["series"],
            series_values=series_values,
            output_svg_path=output_svg_path,
            output_summary_path=output_summary_path,
        )
        output_summary_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return payload
    except Exception as exc:
        payload = error_payload(f"Failed to generate FRED macro chart: {exc}")
        output_summary_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return payload

