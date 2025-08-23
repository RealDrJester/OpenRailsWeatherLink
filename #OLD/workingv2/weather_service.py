# weather_service.py
import requests

class WeatherService:
    def __init__(self):
        self.WMO_CODES = {
            0:"Clear", 1:"Mainly Clear", 2:"Partly Cloudy", 3:"Overcast", 45:"Fog", 48:"Rime Fog", 51:"Light Drizzle", 53:"Drizzle", 55:"Dense Drizzle",
            61:"Rain", 63:"Mod. Rain", 65:"Heavy Rain", 71:"Snow", 73:"Mod. Snow", 75:"Heavy Snow", 80:"Showers", 81:"Mod. Showers", 82:"Violent Showers", 95:"Thunderstorm"
        }

    def get_weather_data(self, lat, lon):
        try:
            url = "https://api.open-meteo.com/v1/forecast"
            params = {
                "latitude": lat, "longitude": lon, "current_weather": "true",
                "hourly": "temperature_2m,precipitation,weathercode,cloudcover,windspeed_10m",
                "forecast_days": 1
            }
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException:
            return None

    def create_weather_events_string(self, lat, lon):
        """Fetches weather and formats it into an Open Rails event string."""
        weather_data = self.get_weather_data(lat, lon)
        if not weather_data:
            return None, "Could not fetch weather data from API."

        def map_weather(wmo, cloudcover, precip):
            params = {"Weather": "Clear", "Overcast": 0.0, "Fog": 0.0, "Precipitation": 0.0}
            if cloudcover is not None: params["Overcast"] = round(cloudcover / 100.0, 2)
            if precip is not None: params["Precipitation"] = round(min(precip, 10.0) / 10.0, 2)
            if wmo is None: return params
            
            if 51 <= wmo <= 67 or 80 <= wmo <= 82: params["Weather"] = "Rain"
            elif 71 <= wmo <= 77 or 85 <= wmo <= 86: params["Weather"] = "Snow"
            elif 45 <= wmo <= 48: params["Fog"], params["Overcast"] = 0.6, max(params["Overcast"], 0.8)
            elif 1 <= wmo <= 3: params["Overcast"] = max(params["Overcast"], 0.3)
            if params["Precipitation"] > 0 and params["Weather"] == "Clear": params["Weather"] = "Rain"
            return params

        events = []
        current = weather_data.get("current_weather", {})
        hourly = weather_data.get("hourly", {})
        
        try:
            # Current weather (at time 00:00:00)
            current_params = map_weather(
                current.get("weathercode"), 
                hourly["cloudcover"][0], 
                hourly["precipitation"][0]
            )
            events.append(f"\t\tORTSWeatherChange ( Time ( 00:00:00 ) Transition ( 60 ) Weather ( {current_params['Weather']} ) Overcast ( {current_params['Overcast']} ) Fog ( {current_params['Fog']} ) Precipitation ( {current_params['Precipitation']} ) )")

            # Hourly forecast for the next 6 hours
            for i in range(1, 7):
                time_str = f"{i:02d}:00:00"
                params = map_weather(
                    hourly["weathercode"][i], 
                    hourly["cloudcover"][i], 
                    hourly["precipitation"][i]
                )
                events.append(f"\t\tORTSWeatherChange ( Time ( {time_str} ) Transition ( 300 ) Weather ( {params['Weather']} ) Overcast ( {params['Overcast']} ) Fog ( {params['Fog']} ) Precipitation ( {params['Precipitation']} ) )")
        except (IndexError, KeyError):
             return None, "Incomplete weather data received from API."

        return "\n".join(events), "Weather data processed successfully."