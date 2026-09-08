"""Conservative CSV import: only vessel planning inputs, never tenant/auth data."""
import csv
import io
from .engine.schema import Vessel

COLUMNS = ("name", "imo", "ship_type", "gt", "fuel", "sea_t", "berth_t", "intra_eu_pct", "extra_eu_pct", "alternative", "max_alternative_pct")


def parse_vessels(upload):
    if upload.size > 65536:
        raise ValueError("Use a UTF-8 CSV file no larger than 64 KB (up to 20 vessels).")
    try:
        content = upload.read(65537).decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("Save the file as CSV UTF-8 and try again.") from exc
    reader = csv.DictReader(io.StringIO(content))
    if reader.fieldnames is None or len(reader.fieldnames) != len(COLUMNS) or set(reader.fieldnames) != set(COLUMNS):
        raise ValueError("CSV headers must match the downloadable template exactly.")
    vessels = []
    try:
        for row_number, row in enumerate(reader, start=2):
            if len(vessels) >= 20:
                raise ValueError("Import at most 20 vessels at a time.")
            if None in row or any(value is None for value in row.values()):
                raise ValueError(f"Row {row_number}: wrong number of columns.")
            try:
                vessels.append(Vessel(name=row["name"].strip(), imo=row["imo"].strip(), ship_type=row["ship_type"].strip(), gt=int(row["gt"]), fuel=row["fuel"].strip(), sea_t=float(row["sea_t"]), berth_t=float(row["berth_t"]), intra_share=float(row["intra_eu_pct"]) / 100, extra_share=float(row["extra_eu_pct"]) / 100, alternative=row["alternative"].strip(), max_blend=float(row["max_alternative_pct"]) / 100))
            except (TypeError, ValueError) as exc:
                raise ValueError(f"Row {row_number}: check gross tonnage, consumption and percentage values.") from exc
    except csv.Error as exc:
        raise ValueError("CSV could not be read. Export it again using the template.") from exc
    if not vessels:
        raise ValueError("The CSV has no vessel rows.")
    return vessels
