import logging
from typing import Optional

import pandas as pd
import requests

logger = logging.getLogger(__name__)
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

REQUEST_TIMEOUT_SECONDS = 30


def fetch_wind_data(lat: float, lon: float, start_year: int, end_year: int) -> Optional[pd.DataFrame]:
    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": f"{start_year}-01-01",
        "end_date": f"{end_year}-12-31",
        "hourly": "wind_speed_10m,wind_speed_100m",
        "wind_speed_unit": "ms",
        "timezone": "auto",
    }

    try:
        response = requests.get(url, params=params, timeout=REQUEST_TIMEOUT_SECONDS)
        response.raise_for_status()
        payload = response.json()

    except requests.exceptions.Timeout:
        logger.error("Timeout fetching wind data for (%s, %s) — server did not respond within %ss.",
                     lat, lon, REQUEST_TIMEOUT_SECONDS)
        return None

    except requests.exceptions.ConnectionError as e:
        logger.error("Connection error fetching wind data for (%s, %s): %s. "
                     "Check your internet connection.", lat, lon, e)
        return None

    except requests.exceptions.HTTPError as e:
        status = e.response.status_code if e.response is not None else "unknown"
        logger.error("HTTP %s from wind data API for (%s, %s): %s", status, lat, lon, e)
        return None

    except Exception as e:
        logger.exception("Unexpected error fetching wind data for (%s, %s): %s", lat, lon, e)
        return None

    try:
        hourly = payload["hourly"]
        df = pd.DataFrame({
            "time": pd.to_datetime(hourly["time"]),
            "Wind_Speed_10m": hourly["wind_speed_10m"],
            "Wind_Speed_100m": hourly["wind_speed_100m"],
        }).set_index("time")

        # Approximate 50 m using the power-law profile (alpha ~ 1/7 for open terrain).
        # If your real fetcher already returns 50 m natively, replace this block.
        alpha = 1 / 7
        df["Wind_Speed_50m"] = df["Wind_Speed_10m"] * (50 / 10) ** alpha

        return df

    except (KeyError, ValueError, TypeError) as e:
        logger.error("Unexpected response shape from wind data API for (%s, %s): %s", lat, lon, e)
        return None
