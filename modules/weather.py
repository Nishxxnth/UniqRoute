"""
Weather fetcher with 10-minute caching and graceful fallback.
Calls OpenWeatherMap API.
"""

import os
import time
import requests
from typing import Dict, Any

# Module-level cache
_weather_cache: Dict[str, Any] = {}
_CACHE_TTL_SECONDS = 600


FALLBACK_WEATHER = {
    'rain_mm': 0,
    'humidity': 70,
    'weather_code': 800,
    'description': 'Clear',
    'storm_penalty': 0,
}

THUNDER_CODES = range(200, 300)   # 2xx thunderstorm
RAIN_CODES = range(500, 600)     # 5xx rain


def get_weather(lat: float = 13.08, lon: float = 80.27) -> Dict[str, Any]:
    """
    Fetch current weather from OpenWeatherMap with 10-minute cache.
    Returns dict: {rain_mm, humidity, weather_code, description, storm_penalty}
    """
    cache_key = f"{lat:.4f},{lon:.4f}"
    now = time.time()

    if cache_key in _weather_cache:
        cached = _weather_cache[cache_key]
        if now - cached['_ts'] < _CACHE_TTL_SECONDS:
            return cached

    api_key = os.getenv('OWM_KEY', '').strip()
    if not api_key:
        return dict(FALLBACK_WEATHER)

    try:
        url = (
            f"https://api.openweathermap.org/data/2.5/weather"
            f"?lat={lat}&lon={lon}&appid={api_key}&units=metric"
        )
        resp = requests.get(url, timeout=5)
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        return dict(FALLBACK_WEATHER)

    weather_code = data.get('weather', [{}])[0].get('id', 800)
    description = data.get('weather', [{}])[0].get('description', 'Clear')
    humidity = data.get('main', {}).get('humidity', 70)
    rain_mm = 0.0
    if 'rain' in data:
        rain_mm = data['rain'].get('1h', data['rain'].get('3h', 0.0))

    if weather_code in THUNDER_CODES:
        storm_penalty = 0.3
    elif weather_code in RAIN_CODES:
        storm_penalty = 0.1
    else:
        storm_penalty = 0.0

    result = {
        'rain_mm': rain_mm,
        'humidity': humidity,
        'weather_code': weather_code,
        'description': description,
        'storm_penalty': storm_penalty,
        '_ts': now,
    }
    _weather_cache[cache_key] = result
    return result