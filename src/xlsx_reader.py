import posixpath
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

import pandas as pd


MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"

HEADER_ALIASES = {
    "creative name",
    "creative",
    "ad name",
    "ad name in platform",
    "platform",
    "objective",
    "spend",
    "spends",
    "impressions",
    "reach",
    "format",
    "placement",
    "campaign",
    "creative efficiency index",
    "performance score",
}


def _normalise_header(value) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().replace("\n", " ")).lower()


def _column_index(cell_ref: str) -> int:
    letters = re.sub(r"[^A-Z]", "", cell_ref.upper())
    index = 0
    for letter in letters:
        index = index * 26 + (ord(letter) - ord("A") + 1)
    return max(index - 1, 0)


def _cell_value(cell: ET.Element, shared_strings: list[str]):
    cell_type = cell.attrib.get("t")
    if cell_type == "inlineStr":
        return "".join(
            text.text or ""
            for text in cell.findall(f".//{{{MAIN_NS}}}is/{{{MAIN_NS}}}t")
        )

    value_node = cell.find(f"{{{MAIN_NS}}}v")
    if value_node is None:
        return None

    raw = value_node.text or ""
    if cell_type == "s":
        try:
            return shared_strings[int(raw)]
        except (IndexError, ValueError):
            return raw
    if cell_type == "b":
        return raw == "1"
    try:
        number = float(raw)
        return int(number) if number.is_integer() else number
    except ValueError:
        return raw


def _read_shared_strings(zip_file: zipfile.ZipFile) -> list[str]:
    try:
        source = zip_file.open("xl/sharedStrings.xml")
    except KeyError:
        return []

    strings = []
    with source:
        for _, item in ET.iterparse(source, events=("end",)):
            if item.tag == f"{{{MAIN_NS}}}si":
                strings.append(
                    "".join(text.text or "" for text in item.findall(f".//{{{MAIN_NS}}}t"))
                )
                item.clear()
    return strings


def _sheet_paths(zip_file: zipfile.ZipFile) -> dict[str, str]:
    workbook = ET.fromstring(zip_file.read("xl/workbook.xml"))
    rels = ET.fromstring(zip_file.read("xl/_rels/workbook.xml.rels"))
    rel_targets = {
        rel.attrib["Id"]: rel.attrib["Target"]
        for rel in rels.findall(f"{{{PKG_REL_NS}}}Relationship")
    }

    paths = {}
    for sheet in workbook.findall(f".//{{{MAIN_NS}}}sheet"):
        rel_id = sheet.attrib.get(f"{{{REL_NS}}}id")
        target = rel_targets.get(rel_id, "")
        if target.startswith("/"):
            path = target.lstrip("/")
        else:
            path = posixpath.normpath(posixpath.join("xl", target))
        paths[sheet.attrib["name"]] = path
    return paths


def read_xlsx_sheet_rows(filepath: str, sheet_name: str) -> list[list]:
    """Read actual worksheet XML rows without trusting workbook dimensions."""
    with zipfile.ZipFile(filepath) as zip_file:
        paths = _sheet_paths(zip_file)
        if sheet_name not in paths:
            raise ValueError(
                f"Sheet '{sheet_name}' not found. Available sheets: {', '.join(paths)}"
            )

        shared_strings = _read_shared_strings(zip_file)
        rows: list[list] = []
        expected_row_number = 1
        with zip_file.open(paths[sheet_name]) as source:
            for _, row in ET.iterparse(source, events=("end",)):
                if row.tag != f"{{{MAIN_NS}}}row":
                    continue

                row_number = int(row.attrib.get("r", expected_row_number))
                while expected_row_number < row_number:
                    rows.append([])
                    expected_row_number += 1

                values = {}
                max_col = 0
                for cell in row.findall(f"{{{MAIN_NS}}}c"):
                    cell_ref = cell.attrib.get("r", "")
                    col_index = _column_index(cell_ref)
                    values[col_index] = _cell_value(cell, shared_strings)
                    max_col = max(max_col, col_index + 1)
                rows.append([values.get(index) for index in range(max_col)])
                expected_row_number = row_number + 1
                row.clear()
        return rows


def detect_header_row(rows: list[list], scan_rows: int = 10) -> int:
    best_index = 0
    best_score = -1
    for index, row in enumerate(rows[:scan_rows]):
        values = [_normalise_header(value) for value in row]
        non_empty = sum(1 for value in values if value)
        alias_hits = sum(1 for value in values if value in HEADER_ALIASES)
        partial_hits = sum(
            1
            for value in values
            if any(alias and alias in value for alias in HEADER_ALIASES)
        )
        score = alias_hits * 4 + partial_hits * 2 + min(non_empty, 10)
        if score > best_score:
            best_score = score
            best_index = index
    return best_index


def rows_to_dataframe(rows: list[list], header_row: int | None = None) -> tuple[pd.DataFrame, int | None]:
    if not rows:
        return pd.DataFrame(), None

    header_index = int(header_row) - 1 if header_row is not None else detect_header_row(rows)
    if header_index < 0 or header_index >= len(rows):
        return pd.DataFrame(), None

    raw_headers = rows[header_index]
    headers = [
        str(value).strip().replace("\n", " ") if value is not None else ""
        for value in raw_headers
    ]
    data_rows = rows[header_index + 1 :]
    if not headers or not data_rows:
        return pd.DataFrame(), header_index + 1

    width = len(headers)
    padded_rows = [
        (list(row) + [None] * (width - len(row)))[:width] for row in data_rows
    ]
    df = pd.DataFrame(padded_rows, columns=headers)
    df = df.dropna(how="all")
    empty_cols = [col for col in df.columns if not str(col).strip()]
    if empty_cols:
        df = df.drop(columns=empty_cols)
    return df, header_index + 1


def read_xlsx_sheet_dataframe(
    filepath: str, sheet_name: str, header_row: int | None = None
) -> tuple[pd.DataFrame, int | None]:
    rows = read_xlsx_sheet_rows(filepath, sheet_name)
    return rows_to_dataframe(rows, header_row=header_row)
