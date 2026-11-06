import csv
import sqlite3
from pathlib import Path

FOLDER = Path(__file__).resolve().parent
CSV_FILE = FOLDER / "pisa_math_by_school_device_time.csv"
DB_FILE = FOLDER / "pisa_v2.db"

# CSV column prefix and the label we want to display
TIME_BANDS = {
    "none": "None",
    "up_to_1h": "Up to 1 hour",
    "1h_to_2h": "1–2 hours",
    "2h_to_3h": "2–3 hours",
    "3h_to_5h": "3–5 hours",
    "5h_to_7h": "5–7 hours",
    "over_7h": "Over 7 hours",
}


def build_db():
    con = sqlite3.connect(DB_FILE)

    try:
        # Create the table and import the CSV together on the first run.
        con.execute("BEGIN IMMEDIATE")

        table_exists = con.execute(
            "SELECT 1 FROM sqlite_master "
            "WHERE type = 'table' AND name = 'pisa_math'"
        ).fetchone()

        if table_exists:
            return

        con.execute("""
            CREATE TABLE pisa_math (
                id INTEGER PRIMARY KEY,
                country TEXT NOT NULL,
                time_band TEXT NOT NULL,
                mean_score REAL NOT NULL,
                standard_error REAL,
                flagged_asterisk INTEGER NOT NULL,
                UNIQUE(country, time_band)
            )
        """)

        with CSV_FILE.open(newline="", encoding="utf-8-sig") as file:
            reader = csv.DictReader(file)

            for row in reader:
                for prefix, label in TIME_BANDS.items():
                    score = row[f"{prefix}_mean"].strip()
                    error = row[f"{prefix}_se"].strip()

                    # A blank score means no result was reported.
                    if score == "":
                        continue

                    con.execute("""
                        INSERT INTO pisa_math
                            (country, time_band, mean_score,
                             standard_error, flagged_asterisk)
                        VALUES (?, ?, ?, ?, ?)
                    """, (
                        row["country"].strip(),
                        label,
                        float(score),
                        float(error) if error else None,
                        int(row["flagged_asterisk"]),
                    ))

        con.commit()

    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def query(sql, values=()):
    con = sqlite3.connect(DB_FILE)
    try:
        return con.execute(sql, values).fetchall()
    finally:
        con.close()


if __name__ == "__main__":
    build_db()

    # Check how many records were imported.
    total = query("SELECT COUNT(*) FROM pisa_math")
    print("Records in database:", total[0][0])

    # Check one result against the original CSV.
    result = query("""
        SELECT country, time_band, mean_score, standard_error
        FROM pisa_math
        WHERE country = ? AND time_band = ?
    """, ("Ireland", "None"))

    for country, band, score, error in result:
        print(f"{country} | {band} | {score} | {error}")