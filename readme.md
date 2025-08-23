# ORTS WeatherLink

*A tool to bring dynamic, real-world weather to the Open Rails train simulator.*


<img width="1024" height="1024" alt="logo1" src="https://github.com/user-attachments/assets/5c9cd533-9275-4a03-90ad-e9c12aafcd11" />

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

- <img width="400" height="525" alt="image" src="https://github.com/user-attachments/assets/3116a4f1-ac08-494a-a36c-c6e8fe3e7564" />
<img width="1498" height="845" alt="image" src="https://github.com/user-attachments/assets/ca0cef68-299d-47eb-95c2-91247da5f70c" />
<img width="219" height="157" alt="image" src="https://github.com/user-attachments/assets/c36e5a4d-6f25-40e9-bd04-e8dfb5648955" />
<img width="1498" height="845" alt="image" src="https://github.com/user-attachments/assets/b882276d-5850-414a-a346-a1b224ffbf31" />



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

## Adding Custom Sounds

You can add your own `.wav` files for a more customized and immersive sound experience. The application will automatically detect and use them if they are placed in the correct folder with the correct name.

### How It Works

1.  **Create the Folder**: In the same directory where the ORTS WeatherLink application is located, create a new folder named `user_sounds`.

2.  **Add Your Files**: Place your custom sound files (which must be in `.wav` format) into this `user_sounds` folder.

3.  **Follow the Naming Convention**: The application identifies sounds based on their filenames. The name must match the patterns listed below. The `*` is a wildcard, meaning you must use sequential numbers, (e.g., `ThunderSound1.wav`, `ThunderSound2.wav`,`ThunderSound3.wav`, etc).

    **It is highly recommended to use longer sound files (5-15 minutes) for ambient loops like rain and wind to avoid repetition and ensure a smooth experience in-game.**

### Filename Patterns

| Condition Triggered By | Sound Category            | Sound Type | Required Filename Pattern     | Example                  |
| ---------------------- | ------------------------- | ---------- | ----------------------------- | ------------------------ |
| Thunderstorms          | `thunder`                 | `Everywhere` | `ThunderSound*.wav`           | `ThunderSound1.wav`      |
| High Winds             | `wind`                    | `Everywhere` | `wind*.wav`                   | `wind1.wav`              |
| Blizzards              | `blizzard`                | `Everywhere` | `PolarWind*.wav`              | `PolarWind1.wav`         |
| Light Rain             | `everywhere_light_rain`   | `Everywhere` | `LightRain*.wav`              | `LightRain1.wav`         |
| Medium Rain            | `everywhere_medium_rain`  | `Everywhere` | `MediumRain*.wav`             | `MediumRain1.wav`        |
| Heavy Rain             | `everywhere_heavy_rain`   | `Everywhere` | `HeavyRain*.wav`              | `HeavyRain1.wav`         |
| Light Rain             | `cab_light_rain`          | `Cab`      | `CabLightRain*.wav`           | `CabLightRain1.wav`      |
| Medium Rain            | `cab_medium_rain`         | `Cab`      | `CabMediumRain*.wav`          | `CabMediumRain1.wav`     |
| Heavy Rain             | `cab_heavy_rain`          | `Cab`      | `CabHeavyRain*.wav`           | `CabHeavyRain1.wav`      |
| Light Rain             | `pass_light_rain`         | `Pass`     | `PassLightRain*.wav`          | `PassLightRain1.wav`     |
| Medium Rain            | `pass_medium_rain`        | `Pass`     | `PassMediumRain*.wav`         | `PassMediumRain1.wav`    |
| Heavy Rain             | `pass_heavy_rain`         | `Pass`     | `PassHeavyRain*.wav`          | `PassHeavyRain1.wav`     |

After adding your files, you can restart the application or refresh it from FILE > Settings > "Rescan 'user_sounds' folder". For advanced configuration, such as changing the sound type (`Everywhere`, `EverywhereLoop`, etc.), you can edit the `sounds.json` file directly.

## Limitations

1. Openrails accepts no temperature, wind direction and wind strength. Those variables will not be available or passed through the game.
2. Sounds are played using randomly chosen *.wav files. They may not always match what you see on the screen.
3. The sounds are added, based on size and what the weather reports. The program will try to add them multiple times to replicate them looping. But this is not a guarantee it will work.
4. Best option is to use a longer audio, if you so choose to add them. 

## Dependencies & Credits

This tool is made possible by several excellent free APIs and Python libraries:

- **Weather Data:** [Open-Meteo API](https://open-meteo.com/)
- **METAR Data:** [AviationWeather.gov](https://aviationweather.gov/)
- **Geocoding:** [OpenStreetMap Nominatim](https://nominatim.openstreetmap.org/)
- **Mapping:** [tkintermapview](https://github.com/TomSchimansky/TkinterMapView)
- **Charting:** [Matplotlib](https://matplotlib.org/)
- Grok
- Copilot
- Claude
- Gemini 2.5
  
This project can be found on GitHub: [https://github.com/RealDrJester/OpenRailsWeatherLink/](https://github.com/RealDrJester/OpenRailsWeatherLink/)
