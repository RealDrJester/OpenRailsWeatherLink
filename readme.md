# ORTS WeatherLink

*A tool to bring dynamic, real-world weather to the Open Rails train simulator.*

![Application Screenshot](https://i.imgur.com/uR00572.png) 

## Description

ORTS WeatherLink is a tool designed to enhance the realism of the Open Rails train simulator. It fetches real-world live or historical weather data based on a route's geographical location and automatically creates a new activity file with dynamic, evolving weather conditions.

This allows users to experience authentic atmospheric conditions—from clear skies to thunderstorms—that change throughout their simulated journey, based on what the weather was really like at that location on that day.

## Features

- **Live Weather:** Fetches current 48-hour weather forecasts for any route in the world.
- **Historical Weather:** Fetches actual weather data for any past date, allowing you to run an activity in the authentic conditions of that day.
- **METAR Integration:** Generates a static weather scenario based on a real-time airport METAR report, perfect for creating specific, consistent conditions.
- **Dynamic Event Generation:** Creates a full 24-hour sequence of weather changes in a new `.act` file, leaving your original activity file untouched.
- **Manual Editor:** A powerful UI for creating completely custom weather event sequences from scratch. You can define every detail, including cloud cover, fog, precipitation, and transition times.
- **Sound Injection:** Automatically adds ambient sound effects for rain, wind, thunderstorms, and blizzards to the generated activity. It also supports custom user-provided sounds.
- **Path Visualization:** Displays the selected activity's path on an interactive map, helping you visualize the journey and the locations where weather data is being sampled.
- **Route Caching:** Caches your route list for significantly faster application startup times.

## How to Use

1.  Launch the application.
2.  Select your main Open Rails `Content` folder using the "Browse..." button.
3.  Select a Route from the list on the left.
4.  Select a base Activity to use as a template.
5.  The application will automatically load live weather for the activity's start point.
6.  To generate the activity, click **"Generate Live Weather Activity"**.
7.  Alternatively, use the "Historical & Other Sources" section to:
    - Select a past date and click **"Generate from Historical Date"**.
    - Generate weather from a live airport report using the **"Generate from METAR..."** button.
8.  Or, for full control, open the **"Manual Weather Editor..."** to create your own sequence.
9.  Launch Open Rails and enjoy your new, weather-enhanced activity! The new file will have the same name as the original, with `.WTHLINK.` and the date added to it.

## Dependencies & Credits

This tool is made possible by several excellent free APIs and Python libraries:

- **Weather Data:** [Open-Meteo API](https://open-meteo.com/)
- **METAR Data:** [AviationWeather.gov](https://aviationweather.gov/)
- **Geocoding:** [OpenStreetMap Nominatim](https://nominatim.openstreetmap.org/)
- **Mapping:** [tkintermapview](https://github.com/TomSchimansky/TkinterMapView)
- **Charting:** [Matplotlib](https://matplotlib.org/)

This project can be found on GitHub: [https://github.com/RealDrJester/OpenRailsWeatherLink/](https://github.com/RealDrJester/OpenRailsWeatherLink/)