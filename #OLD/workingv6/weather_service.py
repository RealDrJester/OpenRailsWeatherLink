# weather_service.py
import requests
from datetime import datetime
import random

class WeatherService:
    def __init__(self):
        self.WMO_CODES = {
            0:"Clear", 1:"Mainly Clear", 2:"Partly Cloudy", 3:"Overcast", 45:"Fog", 48:"Rime Fog", 51:"Light Drizzle", 53:"Drizzle", 55:"Dense Drizzle",
            61:"Rain", 63:"Mod. Rain", 65:"Heavy Rain", 71:"Snow", 73:"Mod. Snow", 75:"Heavy Snow", 80:"Showers", 81:"Mod. Showers", 82:"Violent Showers", 95:"Thunderstorm"
        }
    def get_weather_data(self, lat, lon, date_obj=None):
        try:
            params = { "latitude": lat, "longitude": lon, "hourly": "temperature_2m,precipitation,weathercode,cloudcover,windspeed_10m,winddirection_10m,visibility" }
            if date_obj:
                url = "https://archive-api.open-meteo.com/v1/archive"; date_str = date_obj.strftime("%Y-%m-%d"); params["start_date"] = date_str; params["end_date"] = date_str; params["forecast_days"] = 2
            else:
                url = "https://api.open-meteo.com/v1/forecast"; params["forecast_days"] = 2
            response = requests.get(url, params=params, timeout=15); response.raise_for_status(); return response.json()
        except requests.exceptions.RequestException: return None
    def create_weather_events_string(self, lat, lon, season, date_obj=None, start_hour=0):
        weather_data = self.get_weather_data(lat, lon, date_obj)
        if not weather_data: return None, "Could not fetch weather data from API."
        def map_weather(wmo, cloud, precip, vis, current_season):
            params = {"Overcast": 0.0, "Fog": 100000.0, "Precipitation": 0.0, "Liquidity": 1.0}
            if cloud is not None: params["Overcast"] = round(cloud / 100.0, 2)
            if precip is not None: params["Precipitation"] = round(min(precip, 20.0) / 1000.0, 5)
            if vis is not None: params["Fog"] = max(10, vis)
            # Season check for liquidity
            if current_season in [2, 3]: # Autumn, Winter
                params["Liquidity"] = 0.0 # Snow
            else: # Spring, Summer
                params["Liquidity"] = 1.0 # Rain
            if wmo is not None and 45 <= wmo <= 48:
                params["Fog"] = int(min(params["Fog"], 600)); params["Overcast"] = max(params["Overcast"], 0.8)
            return params
        events = []; hourly = weather_data.get("hourly", {})
        try:
            for i in range(48):
                current_hour_idx = start_hour + (i // 2)
                next_hour_idx = current_hour_idx + 1
                is_half_hour = (i % 2 == 1)
                def get_val(param):
                    val_current = hourly.get(param, [0])[current_hour_idx] if hourly.get(param) and hourly[param][current_hour_idx] is not None else 0
                    if not is_half_hour: return val_current
                    val_next = hourly.get(param, [0])[next_hour_idx] if hourly.get(param) and len(hourly[param]) > next_hour_idx and hourly[param][next_hour_idx] is not None else val_current
                    return (val_current + val_next) / 2.0
                wmo = hourly["weathercode"][current_hour_idx]
                p = map_weather(wmo, get_val("cloudcover"), get_val("precipitation"), get_val("visibility"), season)
                event_time_seconds = i * 1800; transition_time = 60 if i == 0 else 1800
                event_lines = [
                    f"\t\tEventCategoryTime (", f"\t\t\tEventTypeTime ( )", f"\t\t\tID ( 900{i} )", f"\t\t\tActivation_Level ( 1 )",
                    f"\t\t\tName ( WTHLINK_Interval_{i} )", f"\t\t\tTime ( {event_time_seconds} )", f"\t\t\tOutcomes (",
                    f"\t\t\t\tORTSWeatherChange (", f"\t\t\t\t\tORTSOvercast ( {p['Overcast']:.2f} {transition_time} )",
                    f"\t\t\t\t\tORTSFog ( {p['Fog']:.0f} {transition_time} )", f"\t\t\t\t\tORTSPrecipitationIntensity ( {p['Precipitation']:.5f} {transition_time} )",
                    f"\t\t\t\t\tORTSPrecipitationLiquidity ( {p['Liquidity']:.1f} {transition_time} )", f"\t\t\t\t)", f"\t\t\t)", f"\t\t)"
                ]
                events.extend(event_lines)
        except (IndexError, KeyError) as e: return None, f"Incomplete weather data received from API. Error: {e}"
        return "\n".join(events), "Weather events generated successfully."
    def create_chaotic_weather_events(self):
        events = []
        weather_states = [
            {"Overcast": 0.1, "Fog": 60000, "Precipitation": 0.0, "Liquidity": 1.0}, # Clear
            {"Overcast": 0.9, "Fog": 800, "Precipitation": 0.0, "Liquidity": 1.0},   # Dense Fog
            {"Overcast": 0.8, "Fog": 5000, "Precipitation": 0.015, "Liquidity": 1.0}, # Heavy Rain
            {"Overcast": 0.9, "Fog": 2000, "Precipitation": 0.018, "Liquidity": 0.0}, # Heavy Snow
        ]
        for i in range(48):
            p = random.choice(weather_states)
            event_time_seconds = i * 1800; transition_time = 300
            event_lines = [
                f"\t\tEventCategoryTime (", f"\t\t\tEventTypeTime ( )", f"\t\t\tID ( 900{i} )", f"\t\t\tActivation_Level ( 1 )",
                f"\t\t\tName ( WTHLINK_Chaotic_{i} )", f"\t\t\tTime ( {event_time_seconds} )", f"\t\t\tOutcomes (",
                f"\t\t\t\tORTSWeatherChange (", f"\t\t\t\t\tORTSOvercast ( {p['Overcast']:.2f} {transition_time} )",
                f"\t\t\t\t\tORTSFog ( {p['Fog']:.0f} {transition_time} )", f"\t\t\t\t\tORTSPrecipitationIntensity ( {p['Precipitation']:.5f} {transition_time} )",
                f"\t\t\t\t\tORTSPrecipitationLiquidity ( {p['Liquidity']:.1f} {transition_time} )", f"\t\t\t\t)", f"\t\t\t)", f"\t\t)"
            ]
            events.extend(event_lines)
        return "\n".join(events), "Chaotic weather events generated successfully."