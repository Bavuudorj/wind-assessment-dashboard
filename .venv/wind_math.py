import pandas as pd
import numpy as np
from scipy.stats import weibull_min
import sqlite3

DB_PATH = "turbines.db"

def get_power_curve(target_turbine_name: str) -> dict[int, float]:
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute(
            "SELECT wind_speed_ms, power_kw FROM power_curves "
            "WHERE turbine_name = ? ORDER BY wind_speed_ms",
            (target_turbine_name,),
        )
        return {ws: kw for ws, kw in cur.fetchall()}


def get_all_turbine_names() -> list[str]:
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute(
            "SELECT DISTINCT turbine_name FROM power_curves ORDER BY turbine_name"
        )
        return [row[0] for row in cur.fetchall()]

import sqlite3
import pandas as pd

def save_project(name: str, lat: float, lon: float, turbine: str, aep: float) -> int:
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute(
            "INSERT INTO saved_projects "
            "(project_name, latitude, longitude, turbine_model, aep_mwh) "
            "VALUES (?, ?, ?, ?, ?)",
            (name, lat, lon, turbine, aep),
        )
        conn.commit()
        return cur.lastrowid


def get_all_projects() -> pd.DataFrame:
    with sqlite3.connect(DB_PATH) as conn:
        return pd.read_sql_query(
            "SELECT id, project_name, latitude, longitude, turbine_model, aep_mwh "
            "FROM saved_projects ORDER BY id DESC",
            conn,
        )

def fit_weibull(df: pd.DataFrame, col: str = "Wind_Speed_50m") -> tuple[float, float]:
    data = df[col].dropna()
    data = data[data > 0]
    k, loc, c = weibull_min.fit(data, floc=0)
    return k, c

def calculate_aep(df: pd.DataFrame, power_curve: dict, col: str = "Wind_Speed_50m") -> float:
    speeds = np.array(sorted(power_curve.keys()))
    powers_kw = np.array([power_curve[s] for s in speeds])

    wind = df[col].dropna().to_numpy()

    cut_in, cut_out = speeds.min(), speeds.max()
    power_kw = np.interp(wind, speeds, powers_kw)
    power_kw[(wind < cut_in) | (wind > cut_out)] = 0.0

    mean_power_kw = power_kw.mean()
    aep_mwh = mean_power_kw * 8760 / 1000.0
    return aep_mwh

def add_turbine_to_db(turbine_name: str, power_curve_df: pd.DataFrame) -> bool:
    required_cols = {"Wind_Speed_ms", "Power_kW"}
    if not required_cols.issubset(power_curve_df.columns):
        print(f"Error: DataFrame must contain columns {required_cols}.")
        return False

    rows = [
        (turbine_name, int(row["Wind_Speed_ms"]), float(row["Power_kW"]))
        for _, row in power_curve_df.iterrows()
    ]

    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.executemany(
                "INSERT INTO power_curves (turbine_name, wind_speed_ms, power_kw) "
                "VALUES (?, ?, ?)",
                rows,
            )
            conn.commit()
        return True

    except sqlite3.IntegrityError as e:
        # Triggered by the composite PK (turbine_name, wind_speed_ms) — duplicate insert.
        print(f"Integrity error adding turbine '{turbine_name}': {e}. "
              f"A turbine with this name and wind speeds may already exist.")
        return False

    except sqlite3.DatabaseError as e:
        print(f"Database error adding turbine '{turbine_name}': {e}")
        return False

    except Exception as e:
        print(f"Unexpected error adding turbine '{turbine_name}': {e}")
        return False

# Import your working fetcher script!
import data_fetcher

if __name__ == "__main__":
    # --- NEW DATABASE TEST ---
    print("\n--- Testing Database Connection ---")
    
    # 1. See what turbines are available
    available_turbines = get_all_turbine_names()
    print(f"Turbines in Database: {available_turbines}")
    
    # 2. Pick the first turbine in the list to test
    if available_turbines:
        test_turbine = available_turbines[0]
        print(f"Fetching curve for: {test_turbine}...")
        
        # We need mock data to test the math without the fetcher right now
        import pandas as pd
        # Creating 10 hours of fake 10m/s wind to test the AEP calculation
        mock_df = pd.DataFrame({'Wind_Speed_50m': [10] * 10}) 
        
        # 3. Get the real curve from the DB
        real_power_curve = get_power_curve(test_turbine)
        
        # 4. Calculate AEP using the REAL database curve
        aep = calculate_aep(mock_df, real_power_curve)
        print(f"\n✅ Database AEP Test Passed!")
        print(f"Estimated AEP for {test_turbine}: {aep:,.2f} MWh")
    else:
        print("Error: No turbines found in the database!")