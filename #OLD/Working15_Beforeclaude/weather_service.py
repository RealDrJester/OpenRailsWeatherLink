# weather_service.py
import requests
import random
from datetime import datetime, timedelta
import math

class WeatherService:
    def __init__(self):
        self.WMO_CODES = {
            0:"Clear", 1:"Mainly Clear", 2:"Partly Cloudy", 3:"Overcast", 45:"Fog", 48:"Rime Fog", 51:"Light Drizzle", 53:"Drizzle", 55:"Dense Drizzle",
            61:"Rain", 63:"Mod. Rain", 65:"Heavy Rain", 71:"Snow", 73:"Mod. Snow", 75:"Heavy Snow", 80:"Showers", 81:"Mod. Showers", 82:"Violent Showers", 95:"Thunderstorm",
            96:"Thunderstorm+Hail", 99:"Thunderstorm+Hail"
        }
        self.THUNDERSTORM_CODES = {95, 96, 99}

    def get_weather_data(self, lat, lon, date_obj=None):
        try:
            params = { "latitude": lat, "longitude": lon, "hourly": "temperature_2m,precipitation,weathercode,cloudcover,windspeed_10m,winddirection_10m,visibility" }
            if date_obj:
                url = "https://archive-api.open-meteo.com/v1/archive"; date_str = date_obj.strftime("%Y-%m-%d"); next_day = (date_obj + timedelta(days=1)).strftime("%Y-%m-%d")
                params["start_date"] = date_str; params["end_date"] = next_day
            else:
                url = "https://api.open-meteo.com/v1/forecast"; params["forecast_days"] = 2
            response = requests.get(url, params=params, timeout=15); response.raise_for_status(); return response.json()
        except requests.exceptions.RequestException: return None
        
    def create_weather_events_string(self, lat, lon, season, force_snow, date_obj, start_hour, add_thunder_sounds, sound_manager, route_path):
        weather_data = self.get_weather_data(lat, lon, date_obj)
        if not weather_data: return None, "Could not fetch weather data from API."
        
        def map_weather(wmo, cloud, precip, vis, temp, current_season, snow_forced):
            params = {"Overcast": 0.0, "Fog": 100000.0, "Precipitation": 0.0, "Liquidity": 1.0}
            if cloud is not None: params["Overcast"] = round(cloud / 100.0, 2)
            if precip is not None: params["Precipitation"] = round(min(precip, 15.0) / 1000.0, 5)
            if vis is not None: params["Fog"] = max(10, vis)
            if current_season in [2, 3] and snow_forced: params["Liquidity"] = 0.0
            elif temp is not None:
                if temp > 2: liquidity = 1.0
                elif temp < -1: liquidity = 0.0
                else: liquidity = (temp + 1) / 3.0
                params["Liquidity"] = round(max(0.0, min(1.0, liquidity)), 2)
            else: params["Liquidity"] = 1.0
            if wmo is not None and 45 <= wmo <= 48:
                params["Fog"] = int(min(params["Fog"], 600)); params["Overcast"] = max(params["Overcast"], 0.8)
            return params
            
        events = []; hourly = weather_data.get("hourly", {})
        sound_events = []
        global_sound_counter = 1000 

        try:
            for i in range(48):
                current_hour_idx = start_hour + (i // 2)
                def get_val(param):
                    val_current = hourly.get(param, [0])[current_hour_idx] if hourly.get(param) and current_hour_idx < len(hourly[param]) and hourly[param][current_hour_idx] is not None else 0
                    val_next = hourly.get(param, [0])[current_hour_idx + 1] if hourly.get(param) and current_hour_idx + 1 < len(hourly[param]) and hourly[param][current_hour_idx + 1] is not None else val_current
                    return (val_current + val_next) / 2.0 if (i % 2 == 1) else val_current

                wmo = hourly["weathercode"][current_hour_idx]
                p = map_weather(wmo, get_val("cloudcover"), get_val("precipitation"), get_val("visibility"), get_val("temperature_2m"), season, force_snow)
                event_time_seconds = i * 1800; transition_time = 60 if i == 0 else 1800
                
                event_lines = [ f"\t\tEventCategoryTime (", f"\t\t\tEventTypeTime ( )", f"\t\t\tID ( 900{i} )", f"\t\t\tActivation_Level ( 1 )", f"\t\t\tName ( WTHLINK_Interval_{i} )", f"\t\t\tTime ( {event_time_seconds} )", f"\t\t\tOutcomes (",
                    f"\t\t\t\tORTSWeatherChange (", f"\t\t\t\t\tORTSOvercast ( {p['Overcast']:.2f} {transition_time} )", f"\t\t\t\t\tORTSFog ( {p['Fog']:.0f} {transition_time} )", f"\t\t\t\t\tORTSPrecipitationIntensity ( {p['Precipitation']:.5f} {transition_time} )",
                    f"\t\t\t\t\tORTSPrecipitationLiquidity ( {p['Liquidity']:.1f} {transition_time} )", f"\t\t\t\t)", f"\t\t\t)", f"\t\t)" ]
                events.extend(event_lines)

                is_thunderstorm = add_thunder_sounds and wmo in self.THUNDERSTORM_CODES
                if is_thunderstorm:
                    if random.randint(0, 1) == 0:
                        wav_filename, sound_info = sound_manager.provision_sound_category('thunder', route_path)
                        if wav_filename:
                            schedule_time = event_time_seconds + random.randint(10, 1700)
                            sound_events.extend([ f"\t\tEventCategoryTime ( ID ( {global_sound_counter} ) Name ( WTHLINK_Thunder_{i} ) Time ( {schedule_time} ) Outcomes ( ORTSActivitySound ( ORTSActSoundFile ( \"{wav_filename}\" Everywhere ) ) ) )" ])
                            global_sound_counter += 1
                
        except (IndexError, KeyError) as e: return None, f"Incomplete weather data from API. Error: {e}"
        return "\n".join(events + sound_events), "Weather events generated successfully."

    def create_chaotic_weather_events(self, sound_manager, route_path):
        events = []
        global_sound_counter = 1000
        for i in range(96): # More events for more chaos
            event_time_seconds = i * 900
            transition_time = random.randint(30, 90)
            p = { "Overcast": random.uniform(0, 1), "Fog": random.randint(500, 60000), "Precipitation": random.uniform(0, 0.015), "Liquidity": random.uniform(0, 1) }
            event_lines = [ f"\t\tEventCategoryTime (", f"\t\t\tEventTypeTime ( )", f"\t\t\tID ( 900{i} )", f"\t\t\tActivation_Level ( 1 )", f"\t\t\tName ( WTHLINK_Chaotic_{i} )", f"\t\t\tTime ( {event_time_seconds} )", f"\t\t\tOutcomes (", f"\t\t\t\tORTSWeatherChange (",
                f"\t\t\t\t\tORTSOvercast ( {p['Overcast']:.2f} {transition_time} )", f"\t\t\t\t\tORTSFog ( {p['Fog']:.0f} {transition_time} )", f"\t\t\t\t\tORTSPrecipitationIntensity ( {p['Precipitation']:.5f} {transition_time} )",
                f"\t\t\t\t\tORTSPrecipitationLiquidity ( {p['Liquidity']:.1f} {transition_time} )", f"\t\t\t\t)", f"\t\t\t)", f"\t\t)" ]
            events.extend(event_lines)
            
            # Add a chance for thunder if there is heavy precipitation
            if p['Precipitation'] > 0.010 and random.randint(0, 1) == 0:
                wav_filename, sound_info = sound_manager.provision_sound_category('thunder', route_path)
                if wav_filename:
                    schedule_time = event_time_seconds + random.randint(10, 800)
                    events.extend([ f"\t\tEventCategoryTime ( ID ( {global_sound_counter} ) Name ( WTHLINK_Chaotic_Thunder_{i} ) Time ( {schedule_time} ) Outcomes ( ORTSActivitySound ( ORTSActSoundFile ( \"{wav_filename}\" Everywhere ) ) ) )" ])
                    global_sound_counter += 1
                                    
        return "\n".join(events), "Chaotic weather events generated successfully."