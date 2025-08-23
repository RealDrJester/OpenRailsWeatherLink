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
        self.WINDY_THRESHOLD_KMH = 30 
        self.BLIZZARD_PRECIP_MMH = 5.0
        self.LIGHT_RAIN_MMH = 0.1
        self.MEDIUM_RAIN_MMH = 2.5
        self.HEAVY_RAIN_MMH = 7.6

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
        
    def create_weather_events_string(self, lat, lon, season, force_snow, date_obj, start_hour, add_thunder_sounds, add_wind_sounds, add_rain_sounds, sound_manager, route_path):
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
        sound_channels = {}
        sound_counters = {}

        try:
            for i in range(48):
                current_hour_idx = start_hour + (i // 2)
                def get_val(param):
                    val_current = hourly.get(param, [0])[current_hour_idx] if hourly.get(param) and current_hour_idx < len(hourly[param]) and hourly[param][current_hour_idx] is not None else 0
                    val_next = hourly.get(param, [0])[current_hour_idx + 1] if hourly.get(param) and current_hour_idx + 1 < len(hourly[param]) and hourly[param][current_hour_idx + 1] is not None else val_current
                    return (val_current + val_next) / 2.0 if (i % 2 == 1) else val_current

                wmo = hourly["weathercode"][current_hour_idx]
                temp = get_val("temperature_2m")
                wind_speed = get_val("windspeed_10m")
                precip_mm = get_val("precipitation")
                
                p = map_weather(wmo, get_val("cloudcover"), precip_mm, get_val("visibility"), temp, season, force_snow)
                event_time_seconds = i * 1800; transition_time = 60 if i == 0 else 1800
                
                event_lines = [ f"\t\tEventCategoryTime (", f"\t\t\tEventTypeTime ( )", f"\t\t\tID ( 900{i} )", f"\t\t\tActivation_Level ( 1 )", f"\t\t\tName ( WTHLINK_Interval_{i} )", f"\t\t\tTime ( {event_time_seconds} )", f"\t\t\tOutcomes (",
                    f"\t\t\t\tORTSWeatherChange (", f"\t\t\t\t\tORTSOvercast ( {p['Overcast']:.2f} {transition_time} )", f"\t\t\t\t\tORTSFog ( {p['Fog']:.0f} {transition_time} )", f"\t\t\t\t\tORTSPrecipitationIntensity ( {p['Precipitation']:.5f} {transition_time} )",
                    f"\t\t\t\t\tORTSPrecipitationLiquidity ( {p['Liquidity']:.1f} {transition_time} )", f"\t\t\t\t)", f"\t\t\t)", f"\t\t)" ]
                events.extend(event_lines)

                conditions = set()
                is_blizzard = add_wind_sounds and p['Liquidity'] < 0.2 and precip_mm >= self.BLIZZARD_PRECIP_MMH and wind_speed > self.WINDY_THRESHOLD_KMH
                if is_blizzard: conditions.add("blizzard")
                elif add_wind_sounds and wind_speed > self.WINDY_THRESHOLD_KMH: conditions.add("windy")
                
                if add_rain_sounds and p['Liquidity'] > 0.5:
                    if precip_mm >= self.HEAVY_RAIN_MMH: conditions.add("heavy_rain")
                    elif precip_mm >= self.MEDIUM_RAIN_MMH: conditions.add("medium_rain")
                    elif precip_mm >= self.LIGHT_RAIN_MMH: conditions.add("light_rain")
                
                if add_thunder_sounds and wmo in self.THUNDERSTORM_CODES: conditions.add("thunderstorm")

                for condition in conditions:
                    sound_categories = sound_manager.get_sounds_for_condition(condition)
                    for category in sound_categories:
                        sound_channels.setdefault(category, 0)
                        sound_counters.setdefault(category, 0)
                        
                        if event_time_seconds >= sound_channels[category]:
                            sound_info = sound_manager.get_random_sound(category)
                            if sound_info:
                                if condition == 'thunderstorm':
                                    schedule_time = event_time_seconds + random.randint(10, 900)
                                else: # Continuous sounds
                                    schedule_time = max(sound_channels[category], event_time_seconds + random.randint(1, 5))

                                sound_filename_in_act = sound_manager.copy_sound_to_route(sound_info['path'], route_path)
                                if sound_filename_in_act:
                                    unique_id = f"9{sound_counters[category]:01d}{i:02d}"
                                    sound_events.extend([
                                        f"\t\tEventCategoryTime (", f"\t\t\tEventTypeTime ( )", f"\t\t\tID ( {unique_id} )", f"\t\t\tActivation_Level ( 1 )",
                                        f"\t\t\tName ( WTHLINK_{category}_{i}_{sound_counters[category]} )", f"\t\t\tTime ( {schedule_time} )", f"\t\t\tOutcomes (",
                                        f"\t\t\t\tORTSActivitySound ( ORTSActSoundFile ( \"{sound_filename_in_act}\" \"{sound_info['sound_type']}\" ) )",
                                        f"\t\t\t)", f"\t\t)"
                                    ])
                                    sound_counters[category] += 1
                                    sound_channels[category] = schedule_time + sound_info['duration']
        except (IndexError, KeyError) as e: return None, f"Incomplete weather data from API. Error: {e}"
        return "\n".join(events + sound_events), "Weather and sound events generated successfully."

    def create_preset_weather_events(self, preset_name):
        return "", "Preset function is disabled pending update to new sound system."

    def create_chaotic_weather_events(self, sound_manager, route_path):
        try:
            events = []
            weather_states = [
                {"Overcast": 0.1, "Fog": 60000, "Precipitation": 0.0,  "Liquidity": 1.0, "Conditions": []},
                {"Overcast": 0.8, "Fog": 20000, "Precipitation": 0.0,  "Liquidity": 1.0, "Conditions": ["windy"]},
                {"Overcast": 0.9, "Fog": 8000,  "Precipitation": 0.0015,"Liquidity": 1.0, "Conditions": ["light_rain", "windy"]},
                {"Overcast": 1.0, "Fog": 5000,  "Precipitation": 0.005, "Liquidity": 1.0, "Conditions": ["medium_rain", "windy"]},
                {"Overcast": 1.0, "Fog": 3000,  "Precipitation": 0.015, "Liquidity": 1.0, "Conditions": ["heavy_rain", "thunderstorm"]},
                {"Overcast": 1.0, "Fog": 1000,  "Precipitation": 0.012, "Liquidity": 0.0, "Conditions": ["blizzard", "thunderstorm"]},
            ]
            
            sound_channels = {}
            sound_counters = {}
            
            for i in range(96): # More events for more chaos
                p = random.choice(weather_states)
                event_time_seconds = i * 900 # Faster event intervals (15 mins)
                transition_time = random.randint(30, 90)

                event_lines = [ f"\t\tEventCategoryTime (", f"\t\t\tEventTypeTime ( )", f"\t\t\tID ( 900{i} )", f"\t\t\tActivation_Level ( 1 )", f"\t\t\tName ( WTHLINK_Chaotic_{i} )", f"\t\t\tTime ( {event_time_seconds} )", f"\t\t\tOutcomes (", f"\t\t\t\tORTSWeatherChange (",
                    f"\t\t\t\t\tORTSOvercast ( {p['Overcast']:.2f} {transition_time} )", f"\t\t\t\t\tORTSFog ( {p['Fog']:.0f} {transition_time} )", f"\t\t\t\t\tORTSPrecipitationIntensity ( {p['Precipitation']:.5f} {transition_time} )",
                    f"\t\t\t\t\tORTSPrecipitationLiquidity ( {p['Liquidity']:.1f} {transition_time} )", f"\t\t\t\t)", f"\t\t\t)", f"\t\t)" ]
                events.extend(event_lines)

                for condition in p.get("Conditions", []):
                    sound_categories = sound_manager.get_sounds_for_condition(condition)
                    for category in sound_categories:
                        sound_channels.setdefault(category, 0)
                        sound_counters.setdefault(category, 0)

                        if event_time_seconds >= sound_channels[category]:
                            sound_info = sound_manager.get_random_sound(category)
                            if sound_info:
                                if condition == 'thunderstorm':
                                    schedule_time = event_time_seconds + random.randint(10, 450)
                                else: # Continuous sounds
                                    schedule_time = max(sound_channels[category], event_time_seconds + random.randint(1, 5))
                                
                                sound_filename_in_act = sound_manager.copy_sound_to_route(sound_info['path'], route_path)
                                if sound_filename_in_act:
                                    unique_id = f"9{sound_counters[category]:01d}{i:02d}"
                                    events.extend([
                                        f"\t\tEventCategoryTime (", f"\t\t\tEventTypeTime ( )", f"\t\t\tID ( {unique_id} )", f"\t\t\tActivation_Level ( 1 )",
                                        f"\t\t\tName ( WTHLINK_Chaotic_{category}_{i}_{sound_counters[category]} )", f"\t\t\tTime ( {schedule_time} )", f"\t\t\tOutcomes (",
                                        f"\t\t\t\tORTSActivitySound ( ORTSActSoundFile ( \"{sound_filename_in_act}\" \"{sound_info['sound_type']}\" ) )",
                                        f"\t\t\t)", f"\t\t)"
                                    ])
                                    sound_counters[category] += 1
                                    sound_channels[category] = schedule_time + sound_info['duration']
                                    
            return "\n".join(events), "Chaotic weather with multi-channel sound generated successfully."
        except Exception as e:
            return None, f"Chaotic weather generation failed: {e}"