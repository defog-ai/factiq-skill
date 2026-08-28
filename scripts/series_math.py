#!/usr/bin/env python3
"""Deterministic arithmetic on fetched FactIQ results — no in-context math.

Reads a saved payload JSON object from `run_sql` / `get_series` and prints a
computed table.
Use this instead of computing growth rates, shares, or unit conversions in
your own tokens: the script's arithmetic is exact and repeatable.

Subcommands:
  yoy      year-over-year % change (same month/quarter, previous year)
  ytd      calendar year-to-date cumulative total + YoY % vs prior-year YTD
  share    each group's % share of the per-period total (needs --group-col)
  index    rebase each group to 100 at one YYYY, YYYY-Qn, or YYYY-MM period
  merge    concatenate several files into one long table, tagging each row
           with a label and optionally rescaling values (unit alignment)

Examples:
  python3 "{plugin_root}/scripts/series_math.py" yoy --file cn_imports.json
  python3 "{plugin_root}/scripts/series_math.py" share --file by_reporter.json --group-col reporter
  python3 "{plugin_root}/scripts/series_math.py" index --file trend.json --base 2022-01 --group-col reporter
  # India is US$ Million, Korea US$ Thousand -> align both to US$ Million:
  python3 "{plugin_root}/scripts/series_math.py" merge --input india=india.json \
      --input korea=korea.json:0.001

Here {plugin_root} is the absolute directory containing the plugin manifests.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from datetime import date, datetime
from decimal import Decimal, DecimalException, InvalidOperation, localcontext

TIME_HINTS = ("time", "month", "date", "t", "period", "quarter", "year")
MAX_FIXED_DIGITS = 10_000


def fail(message: str, code: int = 1) -> None:
    print(json.dumps({"error": message}), file=sys.stderr)
    sys.exit(code)


def _reject_constant(value: str) -> None:
    raise ValueError(f"invalid numeric constant {value}")


def load_table(path: str) -> tuple[list[str], list[list]]:
    try:
        with open(path, encoding="utf-8") as f:
            payload = json.load(f, parse_float=Decimal, parse_constant=_reject_constant)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        fail(f"cannot read payload {path}: {exc}")
    if (
        not isinstance(payload, dict)
        or "columns" not in payload
        or "results" not in payload
    ):
        fail(
            f"{path} is not a FactIQ payload (expected an object with 'columns' and "
            "'results')"
        )
    columns = payload["columns"]
    rows = payload["results"]
    if not isinstance(columns, list) or not isinstance(rows, list):
        fail(f"{path} columns and results must both be JSON arrays")
    if not columns or any(
        not isinstance(column, str) or not column.strip() for column in columns
    ):
        fail(f"{path} columns must be non-empty strings")
    if len(set(columns)) != len(columns):
        fail(f"{path} contains duplicate column names: {columns}")
    clean_rows = []
    for index, row in enumerate(rows, start=1):
        if not isinstance(row, (list, tuple)):
            fail(f"{path} result row {index} is not an array")
        if len(row) != len(columns):
            fail(
                f"{path} result row {index} has {len(row)} values for {len(columns)} columns"
            )
        clean_rows.append(list(row))
    return list(columns), clean_rows


def pick_col(
    columns: list[str], requested: str | None, hints: tuple[str, ...], kind: str
) -> int:
    if requested:
        if requested not in columns:
            fail(f"--{kind}-col '{requested}' not in columns {columns}")
        return columns.index(requested)
    for hint in hints:
        if hint in columns:
            return columns.index(hint)
    fail(f"cannot guess the {kind} column in {columns} — pass --{kind}-col")
    raise AssertionError  # unreachable


def pick_value_col(columns: list[str], requested: str | None, taken: set[int]) -> int:
    if requested:
        if requested not in columns:
            fail(f"--value-col '{requested}' not in columns {columns}")
        index = columns.index(requested)
        if index in taken:
            fail(f"--value-col '{requested}' is also used as the time or group column")
        return index
    numericish = [i for i, c in enumerate(columns) if i not in taken]
    if len(numericish) == 1:
        return numericish[0]
    fail(f"cannot guess the value column in {columns} — pass --value-col")
    raise AssertionError  # unreachable


def parse_period(text) -> tuple[int, int, str]:
    s = str(text).strip()
    quarter = re.fullmatch(r"([0-9]{4})-?[Qq]([1-4])", s)
    if quarter:
        year, period = map(int, quarter.groups())
        if year == 0:
            fail(f"year must be at least 0001 in '{text}'")
        return year, period, "quarter"
    full_date = re.fullmatch(r"([0-9]{4})-(0[1-9]|1[0-2])-([0-9]{2})", s)
    if full_date:
        year, month, day = map(int, full_date.groups())
        try:
            date(year, month, day)
        except ValueError:
            fail(f"cannot parse a date out of '{text}' — invalid calendar date")
        return year, month, "month"
    timestamp = re.fullmatch(r"([0-9]{4})-(0[1-9]|1[0-2])-([0-9]{2})[T ].+", s)
    if timestamp:
        try:
            parsed = datetime.fromisoformat(s.replace("Z", "+00:00"))
        except ValueError:
            fail(f"cannot parse a date out of '{text}' — invalid ISO timestamp")
        return parsed.year, parsed.month, "month"
    month_only = re.fullmatch(r"([0-9]{4})-(0[1-9]|1[0-2])", s)
    if month_only:
        year, month = map(int, month_only.groups())
        if year == 0:
            fail(f"year must be at least 0001 in '{text}'")
        return year, month, "month"
    year_only = re.fullmatch(r"([0-9]{4})", s)
    if year_only:
        year = int(year_only.group(1))
        if year == 0:
            fail(f"year must be at least 0001 in '{text}'")
        return year, 1, "year"
    fail(
        f"cannot parse period '{text}' — expected YYYY, YYYY-Qn, YYYY-MM, or an ISO date"
    )
    raise AssertionError  # unreachable


def as_decimal(value, context: str) -> Decimal:
    if isinstance(value, bool) or value is None:
        fail(f"non-numeric value {value!r} in {context}")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        fail(f"non-numeric value {value!r} in {context}")
    if not result.is_finite():
        fail(f"non-finite value {value!r} in {context}")
    ensure_fixed_size(result, context)
    return result


def fixed_digit_count(value: Decimal) -> int:
    """Return the number of digits needed by format(value, "f")."""
    if value == 0:
        return 1
    _, digits, exponent = value.as_tuple()
    if exponent >= 0:
        return len(digits) + exponent
    return max(len(digits) + exponent, 1) - exponent


def ensure_fixed_size(value: Decimal, context: str) -> None:
    if fixed_digit_count(value) > MAX_FIXED_DIGITS:
        fail(
            f"numeric value in {context} is too large for safe fixed-point output; "
            "rescale it before using series_math.py"
        )


def format_cell(value) -> str:
    if isinstance(value, Decimal):
        ensure_fixed_size(value, "output")
        if value == 0:
            return "0"
        text = format(value, "f")
        if "." in text:
            text = text.rstrip("0").rstrip(".")
        return text
    return "" if value is None else str(value)


def emit(header: list[str], rows: list[list]) -> None:
    # Format every value before writing the header so a bad later cell cannot
    # leave a caller with a partial table that looks usable.
    formatted_rows = [[format_cell(value) for value in row] for row in rows]
    writer = csv.writer(sys.stdout, delimiter="\t", lineterminator="\n")
    writer.writerow(header)
    writer.writerows(formatted_rows)


def split_rows(args, columns, rows):
    """Return ({group: [(year, period, label, value)]}, frequency)."""
    if not rows:
        fail(f"cannot run {args.command} on a payload with no rows")
    t_idx = pick_col(columns, args.time_col, TIME_HINTS, "time")
    if args.group_col and args.group_col not in columns:
        fail(f"--group-col '{args.group_col}' not in columns {columns}")
    g_idx = columns.index(args.group_col) if args.group_col else None
    if g_idx == t_idx:
        fail("--group-col and --time-col must identify different columns")
    v_idx = pick_value_col(
        columns, args.value_col, {t_idx} | ({g_idx} if g_idx is not None else set())
    )
    groups: dict[str, list] = {}
    group_identities: dict[str, tuple[str, str]] = {}
    frequency: str | None = None
    seen: set[tuple[str, int, int]] = set()
    for row in rows:
        year, period, kind = parse_period(row[t_idx])
        if frequency is None:
            frequency = kind
        elif kind != frequency:
            fail(
                f"mixed time frequencies in one payload: found both {frequency} and {kind}"
            )
        if g_idx is not None:
            raw_key = row[g_idx]
            key = str(raw_key)
            identity = (type(raw_key).__name__, repr(raw_key))
            previous_identity = group_identities.get(key)
            if previous_identity is not None and previous_identity != identity:
                fail(
                    f"group values with different JSON types both render as {key!r}; "
                    "use one consistent type in the group column"
                )
            group_identities[key] = identity
        else:
            key = ""
        period_key = (key, year, period)
        if period_key in seen:
            fail(
                f"duplicate period {row[t_idx]!r} for group '{key or '(all)'}'; "
                "aggregate duplicate rows or pass the correct --group-col"
            )
        seen.add(period_key)
        display = re.split(r"[T ]", str(row[t_idx]).strip(), maxsplit=1)[0]
        groups.setdefault(key, []).append(
            (year, period, display, as_decimal(row[v_idx], f"row {row}"))
        )
    for series in groups.values():
        series.sort()
    return groups, frequency


def arithmetic_precision(groups: dict[str, list]) -> int:
    """Choose enough Decimal precision for exact sums and stable ratios."""
    values = [value for series in groups.values() for *_, value in series]
    nonzero_values = [value for value in values if value]
    if not nonzero_values:
        return 28
    highest_place = max(value.adjusted() for value in nonzero_values)
    lowest_place = min(value.as_tuple().exponent for value in nonzero_values)
    required = max(28, highest_place - lowest_place + 16)
    if required > 10_000:
        fail(
            "numeric range is too wide for safe decimal arithmetic; rescale the "
            "values before using series_math.py"
        )
    return required


def exact_product(value, factor: Decimal, context: str) -> Decimal:
    left = as_decimal(value, context)
    ensure_fixed_size(factor, f"scale factor for {context}")
    required = max(28, len(left.as_tuple().digits) + len(factor.as_tuple().digits) + 2)
    if required > 10_000:
        fail(f"numeric value in {context} is too large for safe decimal arithmetic")
    with localcontext() as decimal_context:
        decimal_context.prec = required
        product = left * factor
    ensure_fixed_size(product, f"scaled value in {context}")
    return product


def cmd_yoy(args) -> None:
    columns, rows = load_table(args.file)
    groups, _ = split_rows(args, columns, rows)
    out = []
    with localcontext() as context:
        context.prec = arithmetic_precision(groups)
        for key, series in sorted(groups.items()):
            prior = {(y, m): v for y, m, _, v in series}
            for y, m, t, v in series:
                prev = prior.get((y - 1, m))
                pct = (v / prev - 1) * 100 if prev not in (None, 0) else None
                out.append(
                    ([key] if args.group_col else [])
                    + [t, v, "" if pct is None else round(pct, 4)]
                )
    header = ([args.group_col] if args.group_col else []) + ["time", "value", "yoy_pct"]
    emit(header, out)


def cmd_ytd(args) -> None:
    columns, rows = load_table(args.file)
    groups, _ = split_rows(args, columns, rows)
    out = []
    with localcontext() as context:
        context.prec = arithmetic_precision(groups)
        for key, series in sorted(groups.items()):
            cum: dict[tuple[int, int], Decimal] = {}
            running: dict[int, Decimal] = {}
            for y, m, t, v in series:
                running[y] = running.get(y, Decimal(0)) + v
                cum[(y, m)] = running[y]
            for y, m, t, v in series:
                prev = cum.get((y - 1, m))
                current_periods = {p for yy, p, _, _ in series if yy == y and p <= m}
                prior_periods = {p for yy, p, _, _ in series if yy == y - 1 and p <= m}
                expected_periods = set(range(1, m + 1))
                comparable = current_periods == prior_periods == expected_periods
                pct = (
                    (cum[(y, m)] / prev - 1) * 100
                    if comparable and prev not in (None, 0)
                    else None
                )
                out.append(
                    ([key] if args.group_col else [])
                    + [t, cum[(y, m)], "" if pct is None else round(pct, 4)]
                )
    header = ([args.group_col] if args.group_col else []) + [
        "time",
        "ytd_value",
        "ytd_yoy_pct",
    ]
    emit(header, out)


def cmd_share(args) -> None:
    if not args.group_col:
        fail("share needs --group-col (whose share of the per-period total)")
    columns, rows = load_table(args.file)
    groups, _ = split_rows(args, columns, rows)
    totals: dict[tuple[int, int], Decimal] = {}
    out = []
    with localcontext() as context:
        context.prec = arithmetic_precision(groups)
        for series in groups.values():
            for y, period, _, v in series:
                totals[(y, period)] = totals.get((y, period), Decimal(0)) + v
        for key, series in sorted(groups.items()):
            for y, period, t, v in series:
                total = totals[(y, period)]
                share = v / total * 100 if total else None
                out.append([key, t, v, "" if share is None else round(share, 4)])
    emit([args.group_col, "time", "value", "share_pct"], out)


def cmd_index(args) -> None:
    by, bm, base_frequency = parse_period(args.base)
    columns, rows = load_table(args.file)
    groups, frequency = split_rows(args, columns, rows)
    if frequency is not None and frequency != base_frequency:
        fail(
            f"base period {args.base} is {base_frequency}, but the payload is {frequency}"
        )
    out = []
    with localcontext() as context:
        context.prec = arithmetic_precision(groups)
        for key, series in sorted(groups.items()):
            base = next((v for y, m, _, v in series if (y, m) == (by, bm)), None)
            if base in (None, 0):
                fail(
                    f"group '{key or '(all)'}' has no usable value at base {args.base}"
                )
            for _, _, t, v in series:
                out.append(
                    ([key] if args.group_col else []) + [t, round(v / base * 100, 4)]
                )
    header = ([args.group_col] if args.group_col else []) + [
        "time",
        f"index_{args.base}=100",
    ]
    emit(header, out)


def pick_merge_value_col(columns: list[str], requested: str | None) -> int:
    if requested:
        if requested not in columns:
            fail(f"--value-col '{requested}' not in columns {columns}")
        return columns.index(requested)
    candidates = [
        index
        for index, name in enumerate(columns)
        if name == "value"
        or name == "ytd_value"
        or name.startswith("total_")
        or name.endswith("_value")
    ]
    if len(candidates) == 1:
        return candidates[0]
    fail(f"cannot identify one value column in {columns} — pass --value-col")
    raise AssertionError  # unreachable


def parse_merge_input(spec: str) -> tuple[str, str, Decimal, bool]:
    """Parse label=path[:factor], preserving existing paths containing colons."""
    if "=" not in spec:
        fail(f"--input must be label=path[:factor], got '{spec}'")
    label, rest = spec.split("=", 1)
    if not label.strip() or not rest:
        fail(f"--input needs a non-empty label and path, got '{spec}'")
    if label != label.strip() or any(char in label for char in "\t\r\n"):
        fail(
            f"--input label must not have leading/trailing or control whitespace: '{label}'"
        )

    factor = Decimal(1)
    factor_supplied = False
    path = rest
    # Prefer an existing path verbatim, since ':' is legal in POSIX file names.
    # Otherwise a numeric final segment is the optional scale factor. This also
    # supports payload files without a .json extension.
    if ":" in rest and not os.path.exists(rest):
        possible_path, factor_s = rest.rsplit(":", 1)
        try:
            possible_factor = Decimal(factor_s)
        except InvalidOperation:
            possible_factor = None
            if possible_path and os.path.exists(possible_path):
                fail(f"scale factor in --input {spec!r} is not a number")
        if possible_factor is not None:
            if not possible_path:
                fail(f"--input needs a non-empty path, got '{spec}'")
            if not possible_factor.is_finite():
                fail(f"non-finite value {factor_s!r} in --input {spec}")
            if possible_factor <= 0:
                fail(f"scale factor in --input {spec!r} must be greater than zero")
            ensure_fixed_size(possible_factor, f"scale factor in --input {spec}")
            path, factor, factor_supplied = possible_path, possible_factor, True
    return label, path, factor, factor_supplied


def cmd_merge(args) -> None:
    out = []
    header: list[str] | None = None
    scale_idx: int | None = None
    labels: set[str] = set()
    parsed_inputs = []
    for spec in args.input:
        label, path, factor, factor_supplied = parse_merge_input(spec)
        if label in labels:
            fail(f"duplicate --input label '{label}'")
        labels.add(label)
        parsed_inputs.append((label, path, factor, factor_supplied))

    validate_values = args.value_col is not None or any(
        factor_supplied for *_, factor_supplied in parsed_inputs
    )
    for label, path, factor, _ in parsed_inputs:
        columns, rows = load_table(path)
        if "source" in columns:
            fail(
                f"{path} already has a 'source' column; rename it before merge so "
                "the input label column is unambiguous"
            )
        if header is None:
            header = ["source"] + columns
        elif columns != header[1:]:
            fail(f"{path} columns {columns} differ from first file's {header[1:]}")
        if scale_idx is None and validate_values:
            scale_idx = pick_merge_value_col(columns, args.value_col)
        for row in rows:
            merged = list(row)
            if validate_values:
                assert scale_idx is not None
                merged[scale_idx] = exact_product(
                    merged[scale_idx], factor, f"{path} row {row}"
                )
            out.append([label] + merged)
    emit(header or ["source"], out)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="command", required=True)

    def add_common(p: argparse.ArgumentParser) -> None:
        p.add_argument(
            "--file", required=True, help="payload JSON (columns/results shape)"
        )
        p.add_argument("--time-col", help="time column (default: guessed)")
        p.add_argument("--value-col", help="value column (default: guessed)")
        p.add_argument(
            "--group-col", help="column that splits rows into series (e.g. reporter)"
        )

    for name, fn in (("yoy", cmd_yoy), ("ytd", cmd_ytd), ("share", cmd_share)):
        p = sub.add_parser(name)
        add_common(p)
        p.set_defaults(fn=fn)

    p_index = sub.add_parser("index")
    add_common(p_index)
    p_index.add_argument(
        "--base", required=True, help="base period YYYY, YYYY-Qn, or YYYY-MM (=100)"
    )
    p_index.set_defaults(fn=cmd_index)

    p_merge = sub.add_parser("merge")
    p_merge.add_argument(
        "--input",
        action="append",
        required=True,
        help="label=path[:factor] — repeat per file; factor rescales values (unit alignment)",
    )
    p_merge.add_argument(
        "--value-col",
        help="column to rescale (default: value, total_*, or *_value when unambiguous)",
    )
    p_merge.set_defaults(fn=cmd_merge)

    args = parser.parse_args()
    try:
        args.fn(args)
    except DecimalException as exc:
        fail(f"decimal arithmetic failed: {exc}")


if __name__ == "__main__":
    main()
