import sqlite3

DB_PATH = "turbines.db"

# (wind_speed_ms, power_kw) pairs. Cut-in 3, cut-out 25.
TURBINE_2MW = {
    0: 0, 1: 0, 2: 0,
    3: 30, 4: 100, 5: 220, 6: 400, 7: 640, 8: 960,
    9: 1340, 10: 1700, 11: 1900, 12: 1980, 13: 2000,
    14: 2000, 15: 2000, 16: 2000, 17: 2000, 18: 2000,
    19: 2000, 20: 2000, 21: 2000, 22: 2000, 23: 2000,
    24: 2000, 25: 2000,
}

TURBINE_3MW = {
    0: 0, 1: 0, 2: 0,
    3: 40, 4: 120, 5: 280, 6: 520, 7: 870, 8: 1320,
    9: 1860, 10: 2410, 11: 2790, 12: 2960, 13: 3000,
    14: 3000, 15: 3000, 16: 3000, 17: 3000, 18: 3000,
    19: 3000, 20: 3000, 21: 3000, 22: 3000, 23: 3000,
    24: 3000, 25: 3000,
}

TURBINES = {
    "Generic 2MW": TURBINE_2MW,
    "Generic 3MW": TURBINE_3MW,
}


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()

        cur.execute("""
            CREATE TABLE IF NOT EXISTS power_curves (
                turbine_name   TEXT    NOT NULL,
                wind_speed_ms  INTEGER NOT NULL,
                power_kw       REAL    NOT NULL,
                PRIMARY KEY (turbine_name, wind_speed_ms)
            )
        """)

        # Idempotent: clear existing rows for these turbines before reinserting.
        cur.executemany(
            "DELETE FROM power_curves WHERE turbine_name = ?",
            [(name,) for name in TURBINES],
        )

        rows = [
            (name, ws, float(kw))
            for name, curve in TURBINES.items()
            for ws, kw in curve.items()
        ]
        cur.executemany(
            "INSERT INTO power_curves (turbine_name, wind_speed_ms, power_kw) VALUES (?, ?, ?)",
            rows,
        )

        conn.commit()
        print(f"Success: wrote {len(rows)} rows for {len(TURBINES)} turbines to {DB_PATH}.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
