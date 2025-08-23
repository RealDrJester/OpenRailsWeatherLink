# weather_service.py
import requests
import random
from datetime import datetime, timedelta
import math
import json
from pathlib import Path
from tkinter import simpledialog, messagebox

class WeatherService:
    def __init__(self, log_callback=print):
        self.log = log_callback
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
        self.current_forecast_data = None

    def get_weather_data(self, weather_points, date_obj=None):
        if not weather_points:
            self.log("[ERROR] get_weather_data called with no coordinates.")
            return None

        if not isinstance(weather_points, list):
             weather_points = [weather_points]
        
        base_url = "https://api.open-meteo.com/v1/forecast"
        params = { "hourly": "temperature_2m,precipitation,weathercode,cloudcover,windspeed_10m,winddirection_10m,visibility" }

        if date_obj is not None:
            is_historical = date_obj < datetime.now().date()
            if is_historical:
                base_url = "https://archive-api.open-meteo.com/v1/archive"
            else: # It's a forecast for today or a future date
                base_url = "https://api.open-meteo.com/v1/forecast"
            
            date_str = date_obj.strftime("%Y-%m-%d")
            next_day = (date_obj + timedelta(days=1)).strftime("%Y-%m-%d")
            params["start_date"] = date_str
            params["end_date"] = next_day
        else: # Default live weather forecast
            params["forecast_days"] = 2

        all_results = []
        for i, coords in enumerate(weather_points):
            current_params = params.copy()
            current_params["latitude"] = coords[0]
            current_params["longitude"] = coords[1]
            
            try:
                if len(weather_points) > 5 and i > 0 and i % 5 == 0:
                     self.log(f"[Debug] Fetching weather point {i+1}/{len(weather_points)}...")
                response = requests.get(base_url, params=current_params, timeout=15)
                response.raise_for_status()
                data = response.json()
                all_results.append(data)
            except requests.exceptions.RequestException as e:
                self.log(f"[WARN] API call for point {coords} failed: {e}. Skipping point.")
                continue

        if not all_results:
            self.log("[ERROR] All API calls for weather points failed. Cannot retrieve weather data.")
            return None

        self.current_forecast_data = all_results
        return all_results

    def get_season(self, date_obj, lat):
        month = date_obj.month
        if lat >= 0: # Northern Hemisphere
            if month in [3, 4, 5]: return 0 # Spring
            if month in [6, 7, 8]: return 1 # Summer
            if month in [9, 10, 11]: return 2 # Autumn
            return 3 # Winter
        else: # Southern Hemisphere
            if month in [9, 10, 11]: return 0 # Spring
            if month in [12, 1, 2]: return 1 # Summer
            if month in [3, 4, 5]: return 2 # Autumn
            return 3 # Winter
            
    def create_weather_events_string(self, path_coords, path_dist, season, force_snow, date_obj, start_hour, add_thunder_sounds, add_wind_sounds, add_rain_sounds, sound_manager, route_path):
        weather_points = [p[0] for p in path_coords] if path_coords else []
        weather_data_list = self.get_weather_data(weather_points, date_obj)
        if not weather_data_list: return None, "Could not fetch weather data from API."
        
        def map_weather(wmo, cloud, precip, vis, temp, current_season, snow_forced):
            params = {"Overcast": 0.0, "Fog": 100000.0, "Precipitation": 0.0, "Liquidity": 1.0}
            if cloud is not None: params["Overcast"] = round(cloud / 100.0, 2)
            if precip is not None: params["Precipitation"] = round(min(precip, 15.0) / 1000.0, 5)
            if vis is not None: params["Fog"] = max(10, vis)
            if current_season in [3] and snow_forced: params["Liquidity"] = 0.0 # Winter only
            elif temp is not None:
                if temp > 2: liquidity = 1.0
                elif temp < -1: liquidity = 0.0
                else: liquidity = (temp + 1) / 3.0
                params["Liquidity"] = round(max(0.0, min(1.0, liquidity)), 2)
            else: params["Liquidity"] = 1.0
            if wmo is not None and 45 <= wmo <= 48:
                params["Fog"] = int(min(params["Fog"], 600)); params["Overcast"] = max(params["Overcast"], 0.8)
            return params
            
        events = []; sound_events = []; sound_channels = {}; sound_playlists = {}; global_sound_counter = 0
        num_locations = len(weather_data_list)
        total_intervals = 48

        try:
            for i in range(total_intervals):
                location_index = min(int((i / total_intervals) * num_locations), num_locations - 1)
                hourly = weather_data_list[location_index].get("hourly", {})
                
                current_hour_idx = start_hour + (i // 2)
                def get_val(param):
                    if not hourly or not hourly.get(param) or current_hour_idx >= len(hourly[param]): return 0
                    val_current = hourly[param][current_hour_idx] if hourly[param][current_hour_idx] is not None else 0
                    val_next_idx = current_hour_idx + 1
                    if val_next_idx >= len(hourly[param]): val_next = val_current
                    else: val_next = hourly[param][val_next_idx] if hourly[param][val_next_idx] is not None else val_current
                    return (val_current + val_next) / 2.0 if (i % 2 == 1) else val_current

                wmo = int(get_val("weathercode")); temp = get_val("temperature_2m"); wind_speed = get_val("windspeed_10m"); precip_mm = get_val("precipitation")
                p = map_weather(wmo, get_val("cloudcover"), precip_mm, get_val("visibility"), temp, season, force_snow)
                event_time_seconds = i * 1800; transition_time = 60 if i == 0 else 1800
                
                event_lines = [ f"\t\tEventCategoryTime ( ID ( 900{i} ) Name ( WTHLINK_Interval_{i} ) Time ( {event_time_seconds} ) Outcomes ( ORTSWeatherChange ( ORTSOvercast ( {p['Overcast']:.2f} {transition_time} ) ORTSFog ( {p['Fog']:.0f} {transition_time} ) ORTSPrecipitationIntensity ( {p['Precipitation']:.5f} {transition_time} ) ORTSPrecipitationLiquidity ( {p['Liquidity']:.1f} {transition_time} ) ) ) )" ]
                events.extend(event_lines)

                conditions = set()
                if add_wind_sounds and p['Liquidity'] < 0.2 and precip_mm >= self.BLIZZARD_PRECIP_MMH and wind_speed > self.WINDY_THRESHOLD_KMH: conditions.add("blizzard")
                elif add_wind_sounds and wind_speed > self.WINDY_THRESHOLD_KMH: conditions.add("windy")
                
                if add_rain_sounds and p['Liquidity'] > 0.5:
                    if precip_mm >= self.HEAVY_RAIN_MMH: conditions.add("heavy_rain")
                    elif precip_mm >= self.MEDIUM_RAIN_MMH: conditions.add("medium_rain")
                    elif precip_mm >= self.LIGHT_RAIN_MMH: conditions.add("light_rain")
                
                if add_thunder_sounds and wmo in self.THUNDERSTORM_CODES: conditions.add("thunderstorm")

                for sound_def in sound_manager.sound_definitions:
                    category = sound_def['category']
                    if sound_def['condition'] in conditions:
                        sound_channels.setdefault(category, 0)
                        if event_time_seconds >= sound_channels[category]:
                            if not sound_playlists.get(category):
                                all_sounds = sound_manager.sounds.get(category, [])
                                if all_sounds: sound_playlists[category] = random.sample(all_sounds, len(all_sounds))
                            
                            if sound_playlists.get(category):
                                sound_info = sound_playlists[category].pop()
                                schedule_time = max(sound_channels[category], event_time_seconds + random.randint(1, 5)) if sound_def['condition'] != 'thunderstorm' else event_time_seconds + random.randint(10, 900)
                                sound_filename_in_act = sound_manager.copy_sound_to_route(sound_info['path'], route_path)
                                if sound_filename_in_act:
                                    sound_events.extend([f"\t\tEventCategoryTime ( ID ( 9{global_sound_counter} ) Name ( WTHLINK_{category}_{i}_{global_sound_counter} ) Time ( {schedule_time} ) Outcomes ( ORTSActivitySound ( ORTSActSoundFile ( \"{sound_filename_in_act}\" {sound_info['sound_type']} ) ) ) )"])
                                    global_sound_counter += 1
                                    sound_channels[category] = schedule_time + sound_info['duration']
        except (IndexError, KeyError) as e: return None, f"Incomplete weather data from API. Error: {e}"
        return "\n".join(events + sound_events), "Weather and sound events generated successfully."

    def create_chaotic_weather_events(self, sound_manager, route_path):
        return "", "Chaotic weather temporarily disabled."

    def save_forecast_as_preset(self, parent_app):
        if not self.current_forecast_data:
            messagebox.showwarning("No Forecast", "No forecast data is available to save.", parent=parent_app)
            return
        
        preset_name = simpledialog.askstring("Save Preset", "Enter a name for this forecast preset:", parent=parent_app)
        if not preset_name:
            return
        
        events = []
        hourly = self.current_forecast_data[0]['hourly'] 
        start_time = parent_app.activity_details.get('start_time', 0)
        
        for i in range(24): 
            time = i * 1800
            temp = hourly['temperature_2m'][i]; precip = hourly['precipitation'][i]; overcast = hourly['cloudcover'][i]; fog = hourly['visibility'][i]
            liquidity = 1.0 if temp > 0 else 0.0
            events.append((time, overcast, fog, precip, liquidity, 1800, "None"))
        
        season = self.get_season(datetime.now().date(), self.current_forecast_data[0]['latitude'])
        new_preset = {"season": season, "events": events}

        user_presets_path = Path("user_presets.json")
        user_presets = {}
        if user_presets_path.exists():
            with open(user_presets_path, 'r') as f:
                try: user_presets = json.load(f)
                except json.JSONDecodeError: pass
        
        if preset_name in user_presets:
            if not messagebox.askyesno("Confirm Overwrite", "A preset with this name already exists. Overwrite it?", parent=parent_app):
                return
        
        user_presets[preset_name] = new_preset
        with open(user_presets_path, 'w') as f:
            json.dump(user_presets, f, indent=4)
        
        messagebox.showinfo("Success", f"Preset '{preset_name}' saved successfully.", parent=parent_app)