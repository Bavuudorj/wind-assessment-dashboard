import sqlite3

DB_PATH = "turbines.db"


def main() -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS saved_projects (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                project_name   TEXT    NOT NULL,
                latitude       REAL    NOT NULL,
                longitude      REAL    NOT NULL,
                turbine_model  TEXT    NOT NULL,
                aep_mwh        REAL    NOT NULL
            )
        """)
        conn.commit()
    print(f"Success: 'saved_projects' table is ready in {DB_PATH}.")


if __name__ == "__main__":
    main()
