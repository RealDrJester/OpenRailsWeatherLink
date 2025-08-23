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
        sound_channels = {'thunder': 0, 'wind': 0, 'rain': 0}
        sound_counters = {'thunder': 0, 'wind': 0, 'rain': 0, 'blizzard': 0}

        try:
            for i in range(48):
                current_hour_idx = start_hour + (i // 2)
                next_hour_idx = current_hour_idx + 1
                is_half_hour = (i % 2 == 1)
                def get_val(param):
                    val_current = hourly.get(param, [0])[current_hour_idx] if hourly.get(param) and current_hour_idx < len(hourly[param]) and hourly[param][current_hour_idx] is not None else 0
                    if not is_half_hour: return val_current
                    val_next = hourly.get(param, [0])[next_hour_idx] if hourly.get(param) and next_hour_idx < len(hourly[param]) and hourly[param][next_hour_idx] is not None else val_current
                    return (val_current + val_next) / 2.0
                
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

                is_blizzard = add_wind_sounds and p['Liquidity'] < 0.2 and precip_mm >= self.BLIZZARD_PRECIP_MMH and wind_speed > self.WINDY_THRESHOLD_KMH
                is_windy = add_wind_sounds and wind_speed > self.WINDY_THRESHOLD_KMH
                is_thunder = add_thunder_sounds and wmo in self.THUNDERSTORM_CODES
                is_raining = add_rain_sounds and precip_mm > self.LIGHT_RAIN_MMH and p['Liquidity'] > 0.5
                is_medium_rain = is_raining and precip_mm >= self.MEDIUM_RAIN_MMH
                is_light_rain = is_raining and precip_mm < self.MEDIUM_RAIN_MMH

                def create_sound_event(category, sound_info, time, id_prefix, counter):
                    sound_filename_in_act = sound_manager.copy_sound_to_route(sound_info['path'], route_path)
                    if not sound_filename_in_act: return []
                    unique_id = f"{id_prefix}{i:02d}{counter:02d}"
                    return [ f"\t\tEventCategoryTime (", f"\t\t\tEventTypeTime ( )", f"\t\t\tID ( {unique_id} )", f"\t\t\tActivation_Level ( 1 )", f"\t\t\tName ( WTHLINK_{category.capitalize()}_{i}_{counter} )", f"\t\t\tTime ( {time} )", f"\t\t\tOutcomes (",
                        f"\t\t\t\tORTSActSoundFile ( {sound_filename_in_act} Everywhere )", f"\t\t\t)", f"\t\t)" ]

                if event_time_seconds >= sound_channels['wind']:
                    category, sound_prefix, counter_key = (None, None, None)
                    if is_blizzard: category, sound_prefix, counter_key = ('blizzard', "97", 'blizzard')
                    elif is_windy: category, sound_prefix, counter_key = ('wind', "96", 'wind')
                    if category:
                        sound = sound_manager.get_random_sound(category)
                        if sound:
                            sound_events.extend(create_sound_event(category, sound, event_time_seconds + 15, sound_prefix, sound_counters[counter_key]))
                            sound_counters[counter_key] += 1
                            sound_channels['wind'] = event_time_seconds + sound['duration']
                
                if not is_blizzard and event_time_seconds >= sound_channels['rain']:
                    category, sound_prefix, counter_key = (None, None, None)
                    if is_medium_rain: category, sound_prefix, counter_key = ('medium_rain', "94", 'rain')
                    elif is_light_rain: category, sound_prefix, counter_key = ('light_rain', "93", 'rain')
                    if category:
                        sound = sound_manager.get_random_sound(category)
                        if sound:
                            sound_events.extend(create_sound_event(category, sound, event_time_seconds + 10, sound_prefix, sound_counters[counter_key]))
                            sound_counters[counter_key] += 1
                            sound_channels['rain'] = event_time_seconds + sound['duration']
                
                if is_thunder and event_time_seconds >= sound_channels['thunder']:
                    sound = sound_manager.get_random_sound('thunder')
                    if sound:
                        schedule_time = event_time_seconds + random.randint(10, 900)
                        sound_events.extend(create_sound_event('thunder', sound, schedule_time, "95", sound_counters['thunder']))
                        sound_counters['thunder'] += 1
                        sound_channels['thunder'] = schedule_time + sound['duration']

        except (IndexError, KeyError) as e: return None, f"Incomplete weather data received from API. Error: {e}"
        return "\n".join(events + sound_events), "Weather and sound events generated successfully."

    def create_preset_weather_events(self, preset_name):
        presets = { "Developing Thunderstorm": [ (0, {"Overcast": 0.2, "Fog": 50000, "Precipitation": 0.0}), (0.5, {"Overcast": 0.6, "Fog": 20000, "Precipitation": 0.0}), (1, {"Overcast": 0.9, "Fog": 8000, "Precipitation": 0.002, "Liquidity": 1.0}), (1.5, {"Overcast": 1.0, "Fog": 3000, "Precipitation": 0.012, "Liquidity": 1.0}), (3, {"Overcast": 0.5, "Fog": 25000, "Precipitation": 0.001, "Liquidity": 1.0}), (4, {"Overcast": 0.3, "Fog": 50000, "Precipitation": 0.0, "Liquidity": 1.0}), ], "Gradual Clearing": [ (0, {"Overcast": 0.9, "Fog": 8000, "Precipitation": 0.001}), (1, {"Overcast": 0.7, "Fog": 15000, "Precipitation": 0.0}), (2, {"Overcast": 0.4, "Fog": 30000}), (3, {"Overcast": 0.1, "Fog": 50000}), ], "Passing Snow Showers": [ (0, {"Overcast": 0.4, "Fog": 40000, "Precipitation": 0.0, "Liquidity": 0.0}), (0.5, {"Overcast": 0.8, "Fog": 5000, "Precipitation": 0.005, "Liquidity": 0.0}), (1.5, {"Overcast": 0.5, "Fog": 30000, "Precipitation": 0.0, "Liquidity": 0.0}), (2.5, {"Overcast": 0.9, "Fog": 4000, "Precipitation": 0.008, "Liquidity": 0.0}), (3.5, {"Overcast": 0.6, "Fog": 40000, "Precipitation": 0.0, "Liquidity": 0.0}), ] }
        keyframes = presets.get(preset_name);
        if not keyframes: return None, f"Preset '{preset_name}' not found."
        events = []; total_duration_hours = 24; num_intervals = 48
        for i in range(num_intervals):
            current_time_hours = (i / num_intervals) * total_duration_hours
            prev_kf = keyframes[0]; next_kf = keyframes[-1]
            for kf in keyframes:
                if kf[0] <= current_time_hours: prev_kf = kf
            for kf in reversed(keyframes):
                if kf[0] >= current_time_hours: next_kf = kf
            p = {};
            if prev_kf == next_kf: p = prev_kf[1]
            else:
                fraction = (current_time_hours - prev_kf[0]) / (next_kf[0] - prev_kf[0])
                for key in prev_kf[1]:
                    start_val = prev_kf[1][key]; end_val = next_kf[1].get(key, start_val)
                    p[key] = start_val + (end_val - start_val) * fraction
            p.setdefault("Overcast", 0.1); p.setdefault("Fog", 50000); p.setdefault("Precipitation", 0); p.setdefault("Liquidity", 1.0); p["Precipitation"] = min(p["Precipitation"], 0.015)
            event_time_seconds = i * 1800; transition_time = 60 if i == 0 else 1800
            event_lines = [ f"\t\tEventCategoryTime (", f"\t\t\tEventTypeTime ( )", f"\t\t\tID ( 900{i} )", f"\t\t\tActivation_Level ( 1 )", f"\t\t\tName ( WTHLINK_Preset_{preset_name.replace(' ','')}_{i} )", f"\t\t\tTime ( {event_time_seconds} )", f"\t\t\tOutcomes (", f"\t\t\t\tORTSWeatherChange (", f"\t\t\t\t\tORTSOvercast ( {p['Overcast']:.2f} {transition_time} )", f"\t\t\t\t\tORTSFog ( {p['Fog']:.0f} {transition_time} )", f"\t\t\t\t\tORTSPrecipitationIntensity ( {p['Precipitation']:.5f} {transition_time} )", f"\t\t\t\t\tORTSPrecipitationLiquidity ( {p['Liquidity']:.1f} {transition_time} )", f"\t\t\t\t)", f"\t\t\t)", f"\t\t)" ]
            events.extend(event_lines)
        return "\n".join(events), f"'{preset_name}' preset generated successfully."
        
    def create_chaotic_weather_events(self, sound_manager, route_path):
        events = []
        weather_states = [
            {"Overcast": 0.1, "Fog": 60000, "Precipitation": 0.0, "Liquidity": 1.0}, # Clear
            {"Overcast": 0.8, "Fog": 20000, "Precipitation": 0.0, "Liquidity": 1.0, "Sound": ["wind"]}, # Windy
            {"Overcast": 0.9, "Fog": 8000, "Precipitation": 0.0015, "Liquidity": 1.0, "Sound": ["light_rain", "wind"]}, # Light rain & windy
            {"Overcast": 1.0, "Fog": 5000, "Precipitation": 0.008, "Liquidity": 1.0, "Sound": ["medium_rain", "wind"]}, # Medium rain & windy
            {"Overcast": 1.0, "Fog": 3000, "Precipitation": 0.015, "Liquidity": 1.0, "Sound": ["medium_rain", "thunder"]}, # Thunderstorm
            {"Overcast": 1.0, "Fog": 1000, "Precipitation": 0.012, "Liquidity": 0.0, "Sound": ["blizzard"]}, # Blizzard
        ]
        
        sound_channels = {'thunder': 0, 'wind': 0, 'rain': 0}
        sound_counters = {'thunder': 0, 'wind': 0, 'rain': 0, 'blizzard': 0}
        
        for i in range(96): # More events for more chaos
            p = random.choice(weather_states)
            event_time_seconds = i * 900 # Faster event intervals (15 mins)
            transition_time = random.randint(30, 90)

            event_lines = [ f"\t\tEventCategoryTime (", f"\t\t\tEventTypeTime ( )", f"\t\t\tID ( 900{i} )", f"\t\t\tActivation_Level ( 1 )", f"\t\t\tName ( WTHLINK_Chaotic_{i} )", f"\t\t\tTime ( {event_time_seconds} )", f"\t\t\tOutcomes (", f"\t\t\t\tORTSWeatherChange (",
                f"\t\t\t\t\tORTSOvercast ( {p['Overcast']:.2f} {transition_time} )", f"\t\t\t\t\tORTSFog ( {p['Fog']:.0f} {transition_time} )", f"\t\t\t\t\tORTSPrecipitationIntensity ( {p['Precipitation']:.5f} {transition_time} )",
                f"\t\t\t\t\tORTSPrecipitationLiquidity ( {p['Liquidity']:.1f} {transition_time} )", f"\t\t\t\t)", f"\t\t\t)", f"\t\t)" ]
            events.extend(event_lines)
            
            sound_categories = p.get("Sound", [])
            if isinstance(sound_categories, str): sound_categories = [sound_categories]

            def create_sound_event(category, sound_info, time, id_prefix, counter):
                sound_filename_in_act = sound_manager.copy_sound_to_route(sound_info['path'], route_path)
                if not sound_filename_in_act: return []
                unique_id = f"{id_prefix}{i:02d}{counter:02d}"
                return [ f"\t\tEventCategoryTime (", f"\t\t\tEventTypeTime ( )", f"\t\t\tID ( {unique_id} )", f"\t\t\tActivation_Level ( 1 )", f"\t\t\tName ( WTHLINK_Chaotic_{category}_{i}_{counter} )", f"\t\t\tTime ( {time} )", f"\t\t\tOutcomes (",
                    f"\t\t\t\tORTSActSoundFile ( {sound_filename_in_act} Everywhere )", f"\t\t\t)", f"\t\t)" ]
            
            for sound_cat in sound_categories:
                channel, s_prefix, s_counter = (None, None, None)
                if 'rain' in sound_cat and event_time_seconds >= sound_channels['rain']: channel, s_prefix, s_counter = ('rain', "93", 'rain')
                elif 'wind' in sound_cat and event_time_seconds >= sound_channels['wind']: channel, s_prefix, s_counter = ('wind', "96", 'wind')
                elif 'blizzard' in sound_cat and event_time_seconds >= sound_channels['wind']: channel, s_prefix, s_counter = ('blizzard', "97", 'blizzard')
                elif 'thunder' in sound_cat and event_time_seconds >= sound_channels['thunder']: channel, s_prefix, s_counter = ('thunder', "95", 'thunder')
                
                if channel:
                    sound = sound_manager.get_random_sound(sound_cat)
                    if sound:
                        schedule_time = event_time_seconds + random.randint(5, 450)
                        events.extend(create_sound_event(sound_cat, sound, schedule_time, s_prefix, sound_counters[s_counter]))
                        sound_counters[s_counter] += 1
                        sound_channels[channel] = schedule_time + sound['duration']

        return "\n".join(events), "Chaotic weather with multi-channel sound generated successfully."