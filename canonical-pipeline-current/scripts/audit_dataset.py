from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


EXPECTED_FIELDS = [
    "admission_date", "discharge_date",
    "art_hyper", "atr_fibril", "ckd", "copd", "diagnosis_icd", "dm", "hf",
    "killip", "mi_localisation", "tlt", "type_acs",
    "bmi", "bp", "bpm", "height", "rr", "smoking", "spo2", "weight",
    "ecg_avb", "ecg_bpm", "ecg_elevation", "ecg_rythm",
    "echo_ef", "echo_lvd", "echo_lvd_2", "echo_mr", "echo_zone",
    "rg_date", "rg_pc",
    "ca_date", "ca_fact", "ca_lad", "rca",
    "card_trop", "crea", "glu", "hb", "ldl", "leucocytes",
    "thrombocytes", "tot_chol",
    "2_aag", "ace_ing_sartan", "anticoagulant", "aspirin", "bb", "statin",
]

CODE_TEXT_FIELDS = {
    "art_hyper", "atr_fibril", "ckd", "copd", "dm", "hf",
    "mi_localisation", "tlt", "type_acs", "smoking",
    "ecg_avb", "ecg_rythm", "echo_mr", "echo_zone", "rg_pc",
}

MED_FIELDS = {
    "2_aag", "ace_ing_sartan", "anticoagulant",
    "aspirin", "bb", "statin"
}

DATE_FIELDS = {
    "admission_date", "discharge_date", "rg_date", "ca_date"
}

NUMERIC_RANGES = {
    "bmi": (8, 100),
    "bpm": (20, 250),
    "height": (80, 250),
    "rr": (5, 80),
    "spo2": (30, 100),
    "weight": (15, 400),
    "ecg_bpm": (20, 300),

    # echo_lvd = КДР ЛЖ
    # echo_lvd_2 = КСР ЛЖ
    "echo_ef": (5, 90),
    "echo_lvd": (20, 100),
    "echo_lvd_2": (10, 80),

    "crea": (10, 2500),
    "glu": (0.5, 60),
    "hb": (20, 250),
    "ldl": (0, 25),
    "leucocytes": (0.1, 150),
    "thrombocytes": (1, 2000),
    "tot_chol": (0.5, 40),
}

MISSING_STRINGS = {
    "",
    "не указано",
    "нет данных",
    "n/a",
    "na",
    "none",
    "null",
}

DATE_FORMATS = (
    "%d/%m/%Y",
    "%d.%m.%Y",
    "%Y-%m-%d",
)


def is_missing(value: Any) -> bool:
    if value is None:
        return True

    if isinstance(value, str):
        return value.strip().lower() in MISSING_STRINGS

    return False


def is_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def parse_date(value: Any) -> datetime | None:
    if is_missing(value) or not isinstance(value, str):
        return None

    text = value.strip()

    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            pass

    return None


def stable_repr(value: Any) -> str:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            allow_nan=False,
        )
    except Exception:
        return repr(value)


def add_issue(
    issues: list[dict[str, str]],
    file_name: str,
    field: str,
    severity: str,
    rule: str,
    value: Any,
    message: str,
) -> None:

    issues.append({
        "file": file_name,
        "field": field,
        "severity": severity,
        "rule": rule,
        "value": stable_repr(value),
        "message": message,
    })


def validate_code_text(
    file_name: str,
    field: str,
    value: Any,
    issues: list[dict[str, str]],
) -> None:

    if not isinstance(value, dict):
        add_issue(
            issues,
            file_name,
            field,
            "ERROR",
            "type",
            value,
            "Ожидался объект {'code': 0/1, 'text': ...}.",
        )
        return

    extra = set(value) - {"code", "text"}
    missing = {"code", "text"} - set(value)

    if missing:
        add_issue(
            issues,
            file_name,
            field,
            "ERROR",
            "code_text_keys",
            value,
            f"Не хватает ключей: {sorted(missing)}.",
        )

    if extra:
        add_issue(
            issues,
            file_name,
            field,
            "WARN",
            "code_text_extra_keys",
            value,
            f"Лишние ключи: {sorted(extra)}.",
        )

    code = value.get("code")
    text = value.get("text")

    if code not in (0, 1):
        add_issue(
            issues,
            file_name,
            field,
            "ERROR",
            "binary_code",
            code,
            "code должен быть только 0 или 1.",
        )

    if not isinstance(text, str):
        add_issue(
            issues,
            file_name,
            field,
            "ERROR",
            "text_type",
            text,
            "text должен быть строкой.",
        )
        return

    if code == 1 and is_missing(text):
        add_issue(
            issues,
            file_name,
            field,
            "ERROR",
            "positive_without_text",
            value,
            "code=1, но подтверждающий текст пустой/«не указано».",
        )


def validate_medications(
    file_name: str,
    field: str,
    value: Any,
    issues: list[dict[str, str]],
) -> None:

    if value in (0, 1) or is_missing(value) or value == []:
        return

    if not isinstance(value, list):
        add_issue(
            issues,
            file_name,
            field,
            "ERROR",
            "med_type",
            value,
            "Ожидался список препаратов, 0/1 либо «не указано».",
        )
        return

    for i, item in enumerate(value):

        if not isinstance(item, dict):
            add_issue(
                issues,
                file_name,
                field,
                "ERROR",
                "med_item_type",
                item,
                f"Элемент #{i + 1} должен быть объектом.",
            )
            continue

        name = item.get("name")
        prescription = item.get("prescription")

        if not isinstance(name, str) or not name.strip():
            add_issue(
                issues,
                file_name,
                field,
                "ERROR",
                "med_name",
                item,
                f"У препарата #{i + 1} отсутствует name.",
            )

        if prescription is not None and not isinstance(prescription, str):
            add_issue(
                issues,
                file_name,
                field,
                "WARN",
                "med_prescription_type",
                item,
                f"prescription у препарата #{i + 1} не строка.",
            )


def validate_bp(
    file_name: str,
    value: Any,
    issues: list[dict[str, str]],
) -> None:

    if is_missing(value):
        return

    if not isinstance(value, str):
        add_issue(
            issues,
            file_name,
            "bp",
            "ERROR",
            "bp_type",
            value,
            "АД должно быть строкой вида 120/80 или «не указано».",
        )
        return

    m = re.search(r"(\d{2,3})\s*/\s*(\d{2,3})", value)

    if not m:
        add_issue(
            issues,
            file_name,
            "bp",
            "WARN",
            "bp_format",
            value,
            "Не удалось распознать АД как SYS/DIA.",
        )
        return

    sys_bp, dia_bp = map(int, m.groups())

    if not (40 <= sys_bp <= 300 and 20 <= dia_bp <= 200):
        add_issue(
            issues,
            file_name,
            "bp",
            "WARN",
            "bp_range",
            value,
            "АД вне широкого контрольного диапазона.",
        )

    if sys_bp <= dia_bp:
        add_issue(
            issues,
            file_name,
            "bp",
            "WARN",
            "bp_order",
            value,
            "Систолическое АД не больше диастолического.",
        )


def walk_spans(node: Any, path: str = "$"):

    if isinstance(node, dict):

        if "start" in node and "end" in node:
            yield path, node

        for key, value in node.items():
            yield from walk_spans(
                value,
                f"{path}.{key}",
            )

    elif isinstance(node, list):

        for i, value in enumerate(node):
            yield from walk_spans(
                value,
                f"{path}[{i}]",
            )


def validate_evidence(
    result_file: Path,
    evidence_dir: Path | None,
    issues: list[dict[str, str]],
) -> None:

    if evidence_dir is None:
        return

    evidence_file = (
        evidence_dir
        / f"{result_file.stem}.evidence__test.json"
    )

    text_file = (
        evidence_dir
        / "text"
        / f"{result_file.stem}.md"
    )

    if not evidence_file.exists():

        add_issue(
            issues,
            result_file.name,
            "__evidence__",
            "WARN",
            "missing_evidence_file",
            "",
            f"Нет файла {evidence_file.name}.",
        )

        return

    if not text_file.exists():

        add_issue(
            issues,
            result_file.name,
            "__evidence__",
            "WARN",
            "missing_evidence_text",
            "",
            f"Нет evidence__test/text/{text_file.name}.",
        )

        return

    try:
        evidence = json.loads(
            evidence_file.read_text(
                encoding="utf-8-sig"
            )
        )

    except Exception as exc:

        add_issue(
            issues,
            result_file.name,
            "__evidence__",
            "ERROR",
            "invalid_evidence_json",
            "",
            f"Evidence JSON не читается: "
            f"{exc.__class__.__name__}.",
        )

        return

    try:
        text = text_file.read_text(
            encoding="utf-8-sig"
        )

    except Exception as exc:

        add_issue(
            issues,
            result_file.name,
            "__evidence__",
            "ERROR",
            "invalid_evidence_text",
            "",
            f"Evidence text не читается: "
            f"{exc.__class__.__name__}.",
        )

        return

    for span_path, span in walk_spans(evidence):

        start = span.get("start")
        end = span.get("end")

        if not isinstance(start, int) or not isinstance(end, int):

            add_issue(
                issues,
                result_file.name,
                "__evidence__",
                "WARN",
                "span_type",
                span,
                f"{span_path}: start/end должны быть целыми числами.",
            )

            continue

        if (
            start < 0
            or end < start
            or end > len(text)
        ):

            add_issue(
                issues,
                result_file.name,
                "__evidence__",
                "ERROR",
                "span_bounds",
                span,
                f"{span_path}: span [{start}:{end}] "
                f"выходит за границы текста длиной {len(text)}.",
            )

            continue

        quoted = span.get("text")

        if (
            isinstance(quoted, str)
            and quoted
            and quoted != text[start:end]
        ):

            add_issue(
                issues,
                result_file.name,
                "__evidence__",
                "WARN",
                "span_text_mismatch",
                span,
                f"{span_path}: text не совпадает "
                f"с evidence__test/text по start/end.",
            )


def validate_record(
    path: Path,
    data: Any,
    evidence_dir: Path | None,
    issues: list[dict[str, str]],
) -> None:

    file_name = path.name

    if not isinstance(data, dict):

        add_issue(
            issues,
            file_name,
            "__root__",
            "ERROR",
            "root_type",
            data,
            "Корень JSON должен быть объектом.",
        )

        return

    actual = set(data)
    expected = set(EXPECTED_FIELDS)

    missing = sorted(expected - actual)
    extra = sorted(actual - expected)

    if missing:

        add_issue(
            issues,
            file_name,
            "__schema__",
            "ERROR",
            "missing_fields",
            missing,
            f"Отсутствуют поля ({len(missing)}): "
            f"{', '.join(missing)}.",
        )

    if extra:

        add_issue(
            issues,
            file_name,
            "__schema__",
            "ERROR",
            "extra_fields",
            extra,
            f"Лишние поля ({len(extra)}): "
            f"{', '.join(extra)}.",
        )

    if len(data) != 50:

        add_issue(
            issues,
            file_name,
            "__schema__",
            "ERROR",
            "field_count",
            len(data),
            f"В JSON {len(data)} полей вместо 50.",
        )

    for field in CODE_TEXT_FIELDS:

        if field in data:
            validate_code_text(
                file_name,
                field,
                data[field],
                issues,
            )

    for field in MED_FIELDS:

        if field in data:
            validate_medications(
                file_name,
                field,
                data[field],
                issues,
            )

    for field in DATE_FIELDS:

        if field not in data:
            continue

        value = data[field]

        if is_missing(value):
            continue

        if (
            not isinstance(value, str)
            or parse_date(value) is None
        ):

            add_issue(
                issues,
                file_name,
                field,
                "WARN",
                "date_format",
                value,
                "Дата не распознана. "
                "Допустимы DD/MM/YYYY, "
                "DD.MM.YYYY, YYYY-MM-DD.",
            )

    admission = parse_date(
        data.get("admission_date")
    )

    discharge = parse_date(
        data.get("discharge_date")
    )

    if admission and discharge and discharge < admission:

        add_issue(
            issues,
            file_name,
            "discharge_date",
            "ERROR",
            "date_order",
            data.get("discharge_date"),
            "Дата выписки раньше даты поступления.",
        )

    if "killip" in data and not is_missing(data["killip"]):

        killip = data["killip"]

        if (
            not isinstance(killip, int)
            or isinstance(killip, bool)
            or killip not in (1, 2, 3, 4)
        ):

            add_issue(
                issues,
                file_name,
                "killip",
                "WARN",
                "killip_range",
                killip,
                "Killip обычно должен быть "
                "1, 2, 3, 4 либо «не указано».",
            )

    if "ca_fact" in data and not is_missing(data["ca_fact"]):

        value = data["ca_fact"]

        if value not in ("Y", "N", "y", "n", 0, 1):

            add_issue(
                issues,
                file_name,
                "ca_fact",
                "WARN",
                "ca_fact_value",
                value,
                "Ожидалось Y/N (или 0/1).",
            )

    for field in ("ca_lad", "rca"):

        if (
            field in data
            and not is_missing(data[field])
        ):

            value = data[field]

            if (
                not isinstance(value, int)
                or isinstance(value, bool)
                or value not in (0, 1, 2)
            ):

                add_issue(
                    issues,
                    file_name,
                    field,
                    "WARN",
                    "coronary_code",
                    value,
                    "Ожидался код 0/1/2.",
                )

    validate_bp(
        file_name,
        data.get("bp"),
        issues,
    )

    for field, (low, high) in NUMERIC_RANGES.items():

        if (
            field not in data
            or is_missing(data[field])
        ):
            continue

        value = data[field]

        if not is_number(value):

            add_issue(
                issues,
                file_name,
                field,
                "ERROR",
                "numeric_type",
                value,
                "Ожидалось число либо «не указано».",
            )

            continue

        if not (
            low
            <= float(value)
            <= high
        ):

            add_issue(
                issues,
                file_name,
                field,
                "WARN",
                "numeric_range",
                value,
                f"Значение вне широкого "
                f"контрольного диапазона "
                f"[{low}, {high}].",
            )

    lvd = data.get("echo_lvd")
    lvs = data.get("echo_lvd_2")

    if (
        is_number(lvd)
        and is_number(lvs)
        and float(lvs) >= float(lvd)
    ):

        add_issue(
            issues,
            file_name,
            "echo_lvd_2",
            "WARN",
            "echo_lvd_relation",
            lvs,
            "КСР ЛЖ (echo_lvd_2) >= "
            "КДР ЛЖ (echo_lvd); "
            "проверь, не перепутаны ли поля.",
        )

    ca_fact = data.get("ca_fact")

    if str(ca_fact).upper() in {"N", "0"}:

        if not is_missing(data.get("ca_date")):

            add_issue(
                issues,
                file_name,
                "ca_date",
                "WARN",
                "ca_consistency",
                data.get("ca_date"),
                "ca_fact=N/0, но ca_date заполнено.",
            )

    validate_evidence(
        path,
        evidence_dir,
        issues,
    )


def main() -> int:

    parser = argparse.ArgumentParser(
        description="Fast audit of result__test JSON + evidence__test."
    )

    parser.add_argument(
        "--result__test-dir",
        type=Path,
        default=Path("result__test"),
    )

    parser.add_argument(
        "--evidence__test-dir",
        type=Path,
        default=Path("evidence__test"),
    )

    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("audit"),
    )

    args = parser.parse_args()

    result_dir = args.result_dir

    evidence_dir = (
        args.evidence_dir
        if args.evidence_dir.exists()
        else None
    )

    out_dir = args.out_dir

    out_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    files = sorted(
        result_dir.glob("*.json")
    )

    issues: list[dict[str, str]] = []

    file_status: dict[
        str,
        dict[str, int]
    ] = {}

    value_stats: dict[
        str,
        Counter[str]
    ] = {
        field: Counter()
        for field in EXPECTED_FIELDS
    }

    content_hashes: defaultdict[
        str,
        list[str]
    ] = defaultdict(list)

    readable = 0
    unreadable = 0

    for path in files:

        before = len(issues)

        try:

            raw = path.read_text(
                encoding="utf-8-sig"
            )

            data = json.loads(raw)

            readable += 1

        except Exception as exc:

            unreadable += 1

            add_issue(
                issues,
                path.name,
                "__root__",
                "ERROR",
                "invalid_json",
                "",
                f"JSON не читается: "
                f"{exc.__class__.__name__}: {exc}",
            )

            data = None

        if isinstance(data, dict):

            validate_record(
                path,
                data,
                evidence_dir,
                issues,
            )

            canonical = json.dumps(
                data,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )

            digest = hashlib.sha256(
                canonical.encode("utf-8")
            ).hexdigest()

            content_hashes[digest].append(
                path.name
            )

            for field in EXPECTED_FIELDS:

                if field in data:

                    value_stats[field][
                        stable_repr(data[field])
                    ] += 1

                else:

                    value_stats[field][
                        "<MISSING FIELD>"
                    ] += 1

        file_issues = issues[before:]

        errors = sum(
            i["severity"] == "ERROR"
            for i in file_issues
        )

        warns = sum(
            i["severity"] == "WARN"
            for i in file_issues
        )

        file_status[path.name] = {
            "ERROR": errors,
            "WARN": warns,
        }

    for digest, names in content_hashes.items():

        if len(names) > 1:

            for name in names:

                add_issue(
                    issues,
                    name,
                    "__dataset__",
                    "WARN",
                    "duplicate_json",
                    names,
                    f"Полностью идентичный итоговый "
                    f"JSON у {len(names)} файлов: "
                    f"{', '.join(names[:10])}"
                    + (
                        " ..."
                        if len(names) > 10
                        else ""
                    ),
                )

    for name in file_status:

        file_status[name] = {

            "ERROR": sum(
                i["file"] == name
                and i["severity"] == "ERROR"
                for i in issues
            ),

            "WARN": sum(
                i["file"] == name
                and i["severity"] == "WARN"
                for i in issues
            ),
        }

    issue_path = (
        out_dir
        / "audit_report.csv"
    )

    with issue_path.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=[
                "file",
                "field",
                "severity",
                "rule",
                "value",
                "message",
            ],
            delimiter=";",
        )

        writer.writeheader()

        writer.writerows(
            sorted(
                issues,
                key=lambda x: (
                    0
                    if x["severity"] == "ERROR"
                    else 1,
                    x["file"],
                    x["field"],
                    x["rule"],
                ),
            )
        )

    status_path = (
        out_dir
        / "audit_file_status.csv"
    )

    with status_path.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=[
                "file",
                "status",
                "errors",
                "warnings",
            ],
            delimiter=";",
        )

        writer.writeheader()

        for name in sorted(file_status):

            counts = file_status[name]

            status = (
                "ERROR"
                if counts["ERROR"]
                else (
                    "WARN"
                    if counts["WARN"]
                    else "OK"
                )
            )

            writer.writerow({
                "file": name,
                "status": status,
                "errors": counts["ERROR"],
                "warnings": counts["WARN"],
            })

    stats_path = (
        out_dir
        / "audit_field_stats.csv"
    )

    with stats_path.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=[
                "field",
                "observed",
                "unique_values",
                "most_common_value",
                "most_common_count",
                "missing_like_count",
            ],
            delimiter=";",
        )

        writer.writeheader()

        for field in EXPECTED_FIELDS:

            counter = value_stats[field]

            observed = sum(
                counter.values()
            )

            most_common_value = ""
            most_common_count = 0

            if counter:

                most_common_value, most_common_count = (
                    counter.most_common(1)[0]
                )

            missing_like = 0

            for raw_value, count in counter.items():

                if raw_value in (
                    '""',
                    '"не указано"',
                    '"нет данных"',
                    "null",
                    "<MISSING FIELD>",
                ):

                    missing_like += count

            writer.writerow({
                "field": field,
                "observed": observed,
                "unique_values": len(counter),
                "most_common_value": most_common_value,
                "most_common_count": most_common_count,
                "missing_like_count": missing_like,
            })

    error_files = sum(
        v["ERROR"] > 0
        for v in file_status.values()
    )

    warn_only_files = sum(
        v["ERROR"] == 0
        and v["WARN"] > 0
        for v in file_status.values()
    )

    ok_files = sum(
        v["ERROR"] == 0
        and v["WARN"] == 0
        for v in file_status.values()
    )

    rule_counts = Counter(
        (
            i["severity"],
            i["rule"],
        )
        for i in issues
    )

    summary = {

        "result_dir": str(result_dir),

        "evidence_dir": (
            str(evidence_dir)
            if evidence_dir
            else None
        ),

        "json_files_found": len(files),

        "readable_json": readable,

        "unreadable_json": unreadable,

        "files_ok": ok_files,

        "files_warn_only": warn_only_files,

        "files_with_errors": error_files,

        "issues_total": len(issues),

        "errors_total": sum(
            i["severity"] == "ERROR"
            for i in issues
        ),

        "warnings_total": sum(
            i["severity"] == "WARN"
            for i in issues
        ),

        "top_rules": [
            {
                "severity": sev,
                "rule": rule,
                "count": count,
            }
            for (
                sev,
                rule
            ), count
            in rule_counts.most_common(20)
        ],
    }

    (
        out_dir
        / "audit_summary.json"
    ).write_text(
        json.dumps(
            summary,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(
        json.dumps(
            summary,
            ensure_ascii=False,
            indent=2,
        )
    )

    print()

    print(
        f"Report: {issue_path}"
    )

    print(
        f"File status: {status_path}"
    )

    print(
        f"Field stats: {stats_path}"
    )

    print(
        f"Summary: "
        f"{out_dir / 'audit_summary.json'}"
    )

    return 1 if unreadable else 0


if __name__ == "__main__":
    raise SystemExit(main())