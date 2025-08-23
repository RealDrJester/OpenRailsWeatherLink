# weather_service.py
import requests
import random
from datetime import datetime, timedelta
import math
import json
from pathlib import Path
from tkinter import simpledialog, messagebox
import xml.etree.ElementTree as ET
import re

class WeatherService:
    def __init__(self, log_callback=print):
        self.log = log_callback
        self.WMO_CODES = {
            0:"Clear", 1:"Mainly Clear", 2:"Partly Cloudy", 3:"Overcast", 45:"Fog", 48:"Rime Fog", 51:"Light Drizzle", 53:"Drizzle", 55:"Dense Drizzle",
            61:"Rain", 63:"Mod. Rain", 65:"Heavy Rain", 71:"Snow", 73:"Mod. Snow", 75:"Heavy Snow", 80:"Showers", 81:"Mod. Showers", 82:"Violent Showers", 95:"Thunderstorm",
            96:"Thunderstorm+Hail", 99:"Thunderstorm+Hail"
        }
        self.SNOW_WMO_CODES = {71, 73, 75}
        self.THUNDERSTORM_CODES = {95, 96, 99}
        self.WINDY_THRESHOLD_KMH = 30 
        self.BLIZZARD_PRECIP_MMH = 5.0
        self.LIGHT_RAIN_MMH = 0.1
        self.MEDIUM_RAIN_MMH = 2.5
        self.HEAVY_RAIN_MMH = 7.6
        self.current_forecast_data = None
        self.last_location_name = "Forecast"

    def get_weather_data(self, weather_points, date_obj=None):
        if not weather_points:
            self.log("[ERROR] get_weather_data called with no coordinates.")
            return None

        if not isinstance(weather_points, list):
             weather_points = [weather_points]
        
        # --- Reverse Geocode for Location Name using OpenStreetMap Nominatim ---
        try:
            first_point = weather_points[0]
            headers = { 'User-Agent': 'ORTSWeatherLink/1.0' }
            geo_url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={first_point[0]}&lon={first_point[1]}"
            geo_res = requests.get(geo_url, timeout=10, headers=headers)
            geo_res.raise_for_status()
            geo_data = geo_res.json()
            if geo_data and "address" in geo_data:
                addr = geo_data["address"]
                city = addr.get("city", addr.get("town", addr.get("village", "Unknown")))
                country = addr.get("country", "")
                self.last_location_name = f"{city}, {country}" if country else city
            else:
                self.last_location_name = "Forecast"
        except requests.exceptions.RequestException as e:
            self.log(f"[WARN] Geocoding API call failed: {e}. Using generic preset name.")
            self.last_location_name = "Forecast"

        base_url = "https://api.open-meteo.com/v1/forecast"
        params = { 
            "hourly": "temperature_2m,precipitation,weathercode,cloudcover,windspeed_10m,winddirection_10m,visibility",
            "daily": "sunrise,sunset",
            "timezone": "auto"
        }

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
        
        # Process and add sunrise/sunset to the first result
        try:
            first_result = all_results[0]
            if "daily" in first_result and "sunrise" in first_result["daily"] and "sunset" in first_result["daily"]:
                sunrise_str_full = first_result["daily"]["sunrise"][0]
                sunset_str_full = first_result["daily"]["sunset"][0]
                first_result["sunrise_str"] = datetime.fromisoformat(sunrise_str_full).strftime('%I:%M %p')
                first_result["sunset_str"] = datetime.fromisoformat(sunset_str_full).strftime('%I:%M %p')
        except (IndexError, KeyError, TypeError, ValueError) as e:
            self.log(f"[WARN] Could not process sunrise/sunset data: {e}")

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
            
    def create_weather_events_string(self, path_coords, path_dist, season, date_obj, start_hour, add_thunder_sounds, add_wind_sounds, add_rain_sounds, sound_manager, route_path):
        weather_points = [p[0] for p in path_coords] if path_coords else []
        weather_data_list = self.get_weather_data(weather_points, date_obj)
        if not weather_data_list: return None, "Could not fetch weather data from API."
        
        def map_weather(wmo, cloud, precip, vis, temp):
            params = {"Overcast": 0.0, "Fog": 100000.0, "Precipitation": 0.0, "Liquidity": 1.0}
            if cloud is not None: params["Overcast"] = round(cloud / 100.0, 2)
            if precip is not None: params["Precipitation"] = round(min(precip, 15.0) / 1000.0, 5)
            if vis is not None: params["Fog"] = max(10, vis)
            
            if wmo in self.SNOW_WMO_CODES:
                params["Liquidity"] = 0.0
            elif temp is not None:
                if temp > 2: liquidity = 1.0
                elif temp < -1: liquidity = 0.0
                else: liquidity = (temp + 1) / 3.0
                params["Liquidity"] = round(max(0.0, min(1.0, liquidity)), 2)
            else:
                params["Liquidity"] = 1.0

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
                p = map_weather(wmo, get_val("cloudcover"), precip_mm, get_val("visibility"), temp)
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

    def create_weather_from_metar(self, icao_code):
        self.log(f"[Info] Fetching METAR for {icao_code}...")
        url = f"https://aviationweather.gov/api/data/metar?ids={icao_code.upper()}&format=xml&hoursBeforeNow=2&mostRecent=true"
        headers = { 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36' }
        try:
            response = requests.get(url, timeout=15, headers=headers)
            response.raise_for_status()
            root = ET.fromstring(response.content)
            metar_node = root.find('data/METAR')
            if metar_node is None:
                return None, f"No recent METAR data found for {icao_code}."
            
            p = {"Overcast": 0.1, "Fog": 50000, "Precipitation": 0.0, "Liquidity": 1.0}

            # Visibility
            vis_node = metar_node.find('visibility_statute_mi')
            if vis_node is not None and vis_node.text is not None:
                try:
                    # Handles values like '6+' by removing non-numeric characters
                    cleaned_text = re.sub(r'[^\d.]', '', vis_node.text)
                    if cleaned_text:
                         vis_mi = float(cleaned_text)
                         p["Fog"] = int(vis_mi * 1609.34)
                except (ValueError, TypeError):
                    self.log(f"[WARN] Could not parse visibility from METAR: '{vis_node.text}'")

            # Clouds
            cloud_cover = {"FEW": 0.2, "SCT": 0.4, "BKN": 0.75, "OVC": 1.0, "CLR": 0.0, "SKC": 0.0}
            max_cover = 0.0
            for sky_node in metar_node.findall('sky_condition'):
                cover = sky_node.get('sky_cover')
                if cloud_cover.get(cover, 0) > max_cover:
                    max_cover = cloud_cover.get(cover, 0)
            p["Overcast"] = max_cover

            # Weather Phenomena (Precipitation, etc.)
            precip_map = { "RA": 2.0, "-RA": 0.5, "+RA": 8.0, "SN": 2.0, "-SN": 0.5, "+SN": 8.0, "DZ": 0.5, "FG": 0.0, "BR": 0.0, "TS": 8.0 }
            liquidity_map = { "RA": 1.0, "SN": 0.0, "DZ": 1.0, "TS": 1.0 }
            weather_node = metar_node.find('wx_string')
            if weather_node is not None:
                weather_str = weather_node.text
                for code, precip_val in precip_map.items():
                    if code in weather_str:
                        p["Precipitation"] = precip_val / 1000.0
                        if code in liquidity_map:
                            p["Liquidity"] = liquidity_map[code]
                        break
                if "FG" in weather_str or "BR" in weather_str: # Fog or Mist
                    p["Fog"] = int(min(p["Fog"], 800))
                    p["Overcast"] = max(p["Overcast"], 0.9)

            event = f"""\t\tEventCategoryTime ( ID ( 9000 ) Name ( WTHLINK_METAR_{icao_code} ) Time ( 0 ) Outcomes ( ORTSWeatherChange ( ORTSOvercast ( {p['Overcast']:.2f} 60 ) ORTSFog ( {p['Fog']:.0f} 60 ) ORTSPrecipitationIntensity ( {p['Precipitation']:.5f} 60 ) ORTSPrecipitationLiquidity ( {p['Liquidity']:.1f} 60 ) ) ) )"""
            return event, f"Successfully created weather from METAR at {icao_code}."
            
        except requests.exceptions.RequestException as e:
            return None, f"Failed to fetch METAR data: {e}"
        except ET.ParseError as e:
            return None, f"Failed to parse METAR XML response: {e}"

    def create_chaotic_weather_events(self, sound_manager, route_path):
        events = []
        for i in range(20): # Generate 20 chaotic events
            event_time = i * 300 # Event every 5 minutes
            overcast = random.uniform(0.0, 1.0)
            fog = random.choice([random.randint(50, 2000), random.randint(10000, 80000)])
            precip = random.choice([0.0, random.uniform(0.1, 15.0)])
            liquidity = random.uniform(0.0, 1.0) if precip > 0 else 1.0
            transition = random.randint(15, 60)
            events.append(f"""\t\tEventCategoryTime ( ID ( 900{i} ) Name ( WTHLINK_Chaotic_{i} ) Time ( {event_time} ) Outcomes ( ORTSWeatherChange ( ORTSOvercast ( {overcast:.2f} {transition} ) ORTSFog ( {int(fog)} {transition} ) ORTSPrecipitationIntensity ( {precip/1000.0:.5f} {transition} ) ORTSPrecipitationLiquidity ( {liquidity:.1f} {transition} ) ) ) )""")
        return "\n".join(events), "Chaotic weather events generated for testing."

    def save_forecast_as_preset(self, parent_app):
        if not self.current_forecast_data:
            messagebox.showwarning("No Forecast", "No forecast data is available to save.", parent=parent_app)
            return
        
        preset_name = simpledialog.askstring("Save Preset", "Enter a name for this forecast preset:", parent=parent_app, initialvalue=self.last_location_name)
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