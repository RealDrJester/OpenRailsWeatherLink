# realweather_gui.pyw (Version 17 - Final)
# A graphical application to inject real-world weather into Open Rails.
# FINAL: Includes Goode Homolosine projection and correctly renames the
# activity's in-game display name.

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import re
import sys
import threading
from pathlib import Path
import csv
import math

try:
    import requests
except ImportError:
    messagebox.showerror("Missing Library", "The 'requests' library is not installed.\n\nPlease open a command prompt and run:\n'pip install requests'")
    sys.exit(1)

# --- Configuration & Data ---
APP_SUFFIX = "REALWORLDWEATHER"
WMO_CODES = {
    0:"Clear Sky", 1:"Mainly Clear", 2:"Partly Cloudy", 3:"Overcast", 45:"Fog", 48:"Depositing Rime Fog", 51:"Light Drizzle", 53:"Moderate Drizzle", 55:"Dense Drizzle",
    61:"Slight Rain", 63:"Moderate Rain", 65:"Heavy Rain", 66:"Light Freezing Rain", 67:"Heavy Freezing Rain", 71:"Slight Snowfall", 73:"Moderate Snowfall", 75:"Heavy Snowfall",
    77:"Snow Grains", 80:"Slight Rain Showers", 81:"Moderate Rain Showers", 82:"Violent Rain Showers", 85:"Slight Snow Showers", 86:"Heavy Snow Showers", 95:"Thunderstorm"
}

# --- Core Logic ---

class GoodeProjection:
    def __init__(self):
        self.earthRadius = 6370997; self.tileSize = 2048; self.ul_x = -20013965; self.ul_y = 8674008
        self.wt_ew_offset = -16385; self.wt_ns_offset = 16385; self.Lon_Center = [0.0] * 12; self.F_East = [0.0] * 12; self.GoodeInit()
    def GoodeInit(self):
        self.Lon_Center[0] = -1.74532925199; self.Lon_Center[1] = -1.74532925199; self.Lon_Center[2] = 0.523598775598; self.Lon_Center[3] = 0.523598775598
        self.Lon_Center[4] = -2.79252680319; self.Lon_Center[5] = -1.0471975512; self.Lon_Center[6] = -2.79252680319; self.Lon_Center[7] = -1.0471975512
        self.Lon_Center[8] = 0.349065850399; self.Lon_Center[9] = 2.44346095279; self.Lon_Center[10] = 0.349065850399; self.Lon_Center[11] = 2.44346095279
        for i in range(12): self.F_East[i] = self.earthRadius * self.Lon_Center[i]
    def ConvertWTC(self, tile_x, tile_z, loc_x, loc_z):
        Y = self.ul_y - ((self.wt_ns_offset - tile_z - 1) * self.tileSize) + loc_z
        X = self.ul_x + ((tile_x - self.wt_ew_offset - 1) * self.tileSize) + loc_x
        return self.Goode_Inverse(X, Y)
    def Goode_Inverse(self, GX, GY):
        region = 0; earthR = self.earthRadius
        if GY >= earthR * 0.710987989993: region = 0 if GX <= earthR * -0.698131700798 else 2
        elif GY >= 0: region = 1 if GX <= earthR * -0.698131700798 else 3
        elif GY >= earthR * -0.710987989993:
            if GX <= earthR * -1.74532925199: region = 4
            elif GX <= earthR * -0.349065850399: region = 5
            elif GX <= earthR * 1.3962634016: region = 8
            else: region = 9
        else:
            if GX <= earthR * -1.74532925199: region = 6
            elif GX <= earthR * -0.349065850399: region = 7
            elif GX <= earthR * 1.3962634016: region = 10
            else: region = 11
        GX = GX - self.F_East[region]; lat, lon = 0.0, 0.0
        if region in [1, 3, 4, 5, 8, 9]:
            lat = GY / earthR; lon = self.Adjust_Lon(self.Lon_Center[region] + GX / (earthR * math.cos(lat))) if abs(abs(lat) - math.pi/2) > 1e-10 else self.Lon_Center[region]
        else:
            arg = (GY + 0.0528035274542 * earthR * (1 if GY >= 0 else -1)) / (1.4142135623731 * earthR)
            if abs(arg) > 1: return None, None
            theta = math.asin(arg); lon = self.Lon_Center[region] + (GX / (0.900316316158 * earthR * math.cos(theta))); arg = (2 * theta + math.sin(2 * theta)) / math.pi
            if abs(arg) > 1: return None, None
            lat = math.asin(arg)
        return math.degrees(lat), math.degrees(lon)
    def Adjust_Lon(self, val): return val - ((1 if val >= 0 else -1) * 2 * math.pi) if abs(val) > math.pi else val

def read_file_with_encodings(path):
    try:
        with open(path, 'r', encoding='utf-16-le', errors='strict') as f: return f.read(), 'utf-16-le'
    except (UnicodeError, UnicodeDecodeError):
        try:
            with open(path, 'r', encoding='utf-8-sig', errors='strict') as f: return f.read(), 'utf-8-sig'
        except Exception: return None, None
    except Exception: return None, None

def get_route_id_from_activity(act_path):
    content, _ = read_file_with_encodings(act_path)
    if not content: return None
    header_match = re.search(r'Tr_Activity_Header\s*\(.*?\)', content, re.IGNORECASE | re.DOTALL)
    if not header_match: return None
    route_id_match = re.search(r'RouteID\s*\(\s*([\w\s\-\.]+)\s*\)', header_match.group(0), re.IGNORECASE)
    if not route_id_match: return None
    return route_id_match.group(1).strip()

def parse_trk_file(trk_path):
    content, _ = read_file_with_encodings(trk_path)
    if not content: return None
    info = {}
    id_match = re.search(r'RouteID\s*\(\s*([\w\s\-\.]+)\s*\)', content, re.IGNORECASE | re.DOTALL)
    name_match = re.search(r'Name\s*\(\s*"(.*?)"\s*\)', content, re.IGNORECASE | re.DOTALL)
    desc_match = re.search(r'Description\s*\(\s*"(.*?)"\s*\)', content, re.IGNORECASE | re.DOTALL)
    info['id'] = id_match.group(1).strip() if id_match else None
    info['name'] = name_match.group(1).strip() if name_match else trk_path.stem
    info['description'] = desc_match.group(1).strip().replace("\\n", "\n") if desc_match else "No description found."
    return info

def find_route_location(route_data, orts_tdb_data, log_callback):
    trk_path = route_data['trk_path']; route_id = route_data['id']
    content, _ = read_file_with_encodings(trk_path)
    if not content:
        log_callback("[ERROR] Could not read .trk file for location data."); return None, None
    lat_match = re.search(r'ORTSLatitude\s*\(\s*(-?\d+\.?\d*)\s*\)', content, re.IGNORECASE)
    lon_match = re.search(r'ORTSLongitude\s*\(\s*(-?\d+\.?\d*)\s*\)', content, re.IGNORECASE)
    if lat_match and lon_match:
        log_callback("[SUCCESS] Found modern ORTSLatitude/Longitude coordinates in .trk file."); return float(lat_match.group(1)), float(lon_match.group(1))
    log_callback("[INFO] Modern coordinates not found. Searching for legacy ORTSReaY/ReaX tags...")
    lat_match_legacy = re.search(r'ORTSReaY\s*\(\s*(-?\d+\.?\d*)\s*\)', content, re.IGNORECASE)
    lon_match_legacy = re.search(r'ORTSReaX\s*\(\s*(-?\d+\.?\d*)\s*\)', content, re.IGNORECASE)
    if lat_match_legacy and lon_match_legacy:
        log_callback("[SUCCESS] Found legacy ORTSReaY/ReaX coordinates in .trk file."); return float(lat_match_legacy.group(1)), float(lon_match_legacy.group(1))
    log_callback("[INFO] Legacy coordinates not found in .trk file. Consulting OrtsTDB.csv...")
    if orts_tdb_data and route_id in orts_tdb_data:
        coords = orts_tdb_data[route_id]; log_callback(f"[SUCCESS] Found coordinates for RouteID '{route_id}' in OrtsTDB.csv."); return coords['lat'], coords['lon']
    log_callback("[INFO] RouteID not found in OrtsTDB.csv. Attempting Goode Homolosine projection...")
    rs_match = re.search(r'RouteStart\s*\(\s*(-?\d+)\s+(-?\d+)\s+(-?\d+\.?\d*)\s+(-?\d+\.?\d*)\s*\)', content, re.IGNORECASE)
    if rs_match:
        tile_x, tile_z, offset_x, offset_z = map(float, rs_match.groups())
        log_callback(f"[INFO] Found RouteStart data: TileX={int(tile_x)}, TileZ={int(tile_z)}, OffsetX={offset_x}, OffsetZ={offset_z}")
        projection = GoodeProjection(); lat, lon = projection.ConvertWTC(int(tile_x), int(tile_z), offset_x, offset_z)
        if lat is not None and lon is not None:
            log_callback(f"[SUCCESS] Calculated coordinates via Goode Homolosine projection."); return lat, lon
    log_callback(f"[ERROR] No coordinate source found for RouteID '{route_id}'."); return None, None

def fetch_current_weather(lat, lon):
    try:
        url = "https://api.open-meteo.com/v1/forecast"; params = {"latitude": lat, "longitude": lon, "current_weather": "true"}
        response = requests.get(url, params=params, timeout=10); response.raise_for_status()
        data = response.json().get("current_weather", {}); wmo = data.get("weathercode")
        return {"condition": WMO_CODES.get(wmo, f"Code {wmo}"), "temperature": f"{data.get('temperature', 'N/A')}°C", "wind": f"{data.get('windspeed', 'N/A')} km/h"}
    except requests.exceptions.RequestException: return None

def create_weather_events_string(lat, lon):
    try:
        url = "https://api.open-meteo.com/v1/forecast"; params = {"latitude": lat, "longitude": lon, "current_weather": "true", "hourly": "weathercode,cloudcover,precipitation", "forecast_days": 1}
        response = requests.get(url, params=params, timeout=10); response.raise_for_status()
        weather_data = response.json()
    except requests.exceptions.RequestException as e: return None, f"Could not fetch weather data: {e}"
    def map_weather(wmo, c, p):
        params = {"Weather": "Clear","Overcast": 0.0,"Fog": 0.0,"Precipitation": 0.0}
        if c is not None: params["Overcast"] = round(c/100.0, 2)
        if p is not None: params["Precipitation"] = round(min(p, 10.0)/10.0, 2)
        if wmo is None: return params
        if 51 <= wmo <= 67 or 80 <= wmo <= 82: params["Weather"] = "Rain"
        elif 71 <= wmo <= 77 or 85 <= wmo <= 86 or wmo == 22: params["Weather"] = "Snow"
        elif 45 <= wmo <= 48: params["Fog"], params["Overcast"] = 0.6, max(params["Overcast"], 0.8)
        elif 1 <= wmo <= 3: params["Overcast"] = max(params["Overcast"], 0.3)
        if params["Precipitation"] > 0 and params["Weather"] == "Clear": params["Weather"] = "Rain"
        return params
    events, current = [], weather_data.get("current_weather", {})
    params = map_weather(current.get("weathercode"), weather_data["hourly"]["cloudcover"][0], weather_data["hourly"]["precipitation"][0])
    events.append(f"\t\tORTSWeatherChange ( Time ( 00:00:00 ) Transition ( 60 ) Weather ( {params['Weather']} ) Overcast ( {params['Overcast']} ) Fog ( {params['Fog']} ) Precipitation ( {params['Precipitation']} ) )")
    for i in range(1, 7):
        try:
            t, w, c, p = f"{i:02d}:00:00", weather_data["hourly"]["weathercode"][i], weather_data["hourly"]["cloudcover"][i], weather_data["hourly"]["precipitation"][i]
            params = map_weather(w, c, p); events.append(f"\t\tORTSWeatherChange ( Time ( {t} ) Transition ( 300 ) Weather ( {params['Weather']} ) Overcast ( {params['Overcast']} ) Fog ( {params['Fog']} ) Precipitation ( {params['Precipitation']} ) )")
        except IndexError: break
    return "\n".join(events), "Weather data processed successfully."

def modify_and_save_activity(original_path, weather_events_str, log_callback):
    try:
        original_content, original_encoding = read_file_with_encodings(original_path)
        if not original_content: return None, "Failed to read original activity to save."
        
        new_content = original_content
        name_pattern = re.compile(r'(Name\s*\(\s*")([^"]*)(")', re.IGNORECASE)
        name_match = name_pattern.search(original_content)
        
        if name_match:
            original_name = name_match.group(2)
            new_activity_name = f"{original_name} [{APP_SUFFIX}]"
            replacement_string = f'{name_match.group(1)}{new_activity_name}{name_match.group(3)}'
            new_content = name_pattern.sub(replacement_string, new_content, count=1)
            log_callback(f"  > Renamed activity to: \"{new_activity_name}\"")
        else:
            log_callback("  > WARNING: Could not find activity Name() to rename. The name will be a duplicate in-game.")
        
        new_content = re.sub(r'\s*ORTSWeatherChange\s*\(\s*.*?\s*\)', '', new_content, flags=re.DOTALL)
        events_match = re.search(r'(\bEvents\s*\(\s*)', new_content, re.IGNORECASE | re.DOTALL)
        if not events_match: return None, "Could not find 'Events (' block."
        
        final_content = f"{new_content[:events_match.end(1)]}\n{weather_events_str}\n{new_content[events_match.end(1):]}"
        
        p = Path(original_path)
        new_path = p.parent / f"{p.stem}.{APP_SUFFIX}.act"
        with open(new_path, 'w', encoding=original_encoding) as f: f.write(final_content)
        return new_path, "New activity file created successfully!"
    except Exception as e: return None, f"Error saving file: {e}"

# --- GUI Application Class ---
class WeatherApp(tk.Tk):
    def __init__(self):
        super().__init__(); self.title(f"Open Rails Real-World Weather Injector (v17 - Final)"); self.geometry("900x700")
        self.content_path = None; self.route_info_map = {}; self.current_activity_paths = {}; self.orts_tdb_data = {}
        self.setup_ui(); self.auto_detect_path()
    def setup_ui(self):
        path_frame = ttk.Frame(self, padding="5"); path_frame.pack(fill=tk.X, side=tk.TOP)
        ttk.Label(path_frame, text="OR Content Path:").pack(side=tk.LEFT); self.path_var = tk.StringVar(value="Searching...")
        ttk.Entry(path_frame, textvariable=self.path_var, state="readonly").pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        ttk.Button(path_frame, text="Select Folder...", command=self.select_content_path).pack(side=tk.LEFT)
        main_paned = ttk.PanedWindow(self, orient=tk.HORIZONTAL); main_paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        selection_paned = ttk.PanedWindow(self, orient=tk.VERTICAL); main_paned.add(selection_paned, weight=3)
        route_frame = ttk.Frame(selection_paned, padding="5"); ttk.Label(route_frame, text="1. Select a Route", font=("", 10, "bold")).pack(anchor=tk.W)
        self.route_listbox = tk.Listbox(route_frame, exportselection=False); self.route_listbox.pack(fill=tk.BOTH, expand=True, pady=(5,0)); self.route_listbox.bind("<<ListboxSelect>>", self.on_route_select)
        selection_paned.add(route_frame, weight=2)
        activity_frame = ttk.Frame(selection_paned, padding="5"); ttk.Label(activity_frame, text="2. Select an Activity", font=("", 10, "bold")).pack(anchor=tk.W)
        self.activity_listbox = tk.Listbox(activity_frame, exportselection=False); self.activity_listbox.pack(fill=tk.BOTH, expand=True, pady=(5,0)); self.activity_listbox.bind("<<ListboxSelect>>", self.on_activity_select)
        selection_paned.add(activity_frame, weight=3)
        right_paned = ttk.PanedWindow(self, orient=tk.VERTICAL); main_paned.add(right_paned, weight=4)
        info_frame = ttk.LabelFrame(right_paned, text="Route Information", padding="10"); right_paned.add(info_frame, weight=2)
        self.route_id_var=tk.StringVar(value="---"); self.route_name_var=tk.StringVar(value="---"); self.route_folder_var=tk.StringVar(value="---"); self.route_desc_var=tk.StringVar(value="---")
        ttk.Label(info_frame, text="Name:", font=("", 10, "bold")).grid(row=0, column=0, sticky="ne"); ttk.Label(info_frame, textvariable=self.route_name_var, wraplength=400, justify=tk.LEFT).grid(row=0, column=1, sticky="nw", padx=5)
        ttk.Label(info_frame, text="RouteID:", font=("", 10, "bold")).grid(row=1, column=0, sticky="ne"); ttk.Label(info_frame, textvariable=self.route_id_var).grid(row=1, column=1, sticky="nw", padx=5)
        ttk.Label(info_frame, text="Folder:", font=("", 10, "bold")).grid(row=2, column=0, sticky="ne"); ttk.Label(info_frame, textvariable=self.route_folder_var).grid(row=2, column=1, sticky="nw", padx=5)
        ttk.Label(info_frame, text="Description:", font=("", 10, "bold")).grid(row=3, column=0, sticky="ne"); ttk.Label(info_frame, textvariable=self.route_desc_var, wraplength=400, justify=tk.LEFT).grid(row=3, column=1, sticky="nw", padx=5)
        info_frame.grid_columnconfigure(1, weight=1)
        preview_frame = ttk.LabelFrame(right_paned, text="Weather Preview", padding="10"); right_paned.add(preview_frame, weight=1)
        self.weather_condition_var=tk.StringVar(value="---"); self.weather_temp_var=tk.StringVar(value="---"); self.weather_wind_var=tk.StringVar(value="---")
        ttk.Label(preview_frame, text="Condition:", font=("", 10, "bold")).grid(row=0, column=0, sticky="w"); ttk.Label(preview_frame, textvariable=self.weather_condition_var).grid(row=0, column=1, sticky="w", padx=5)
        ttk.Label(preview_frame, text="Temperature:", font=("", 10, "bold")).grid(row=1, column=0, sticky="w"); ttk.Label(preview_frame, textvariable=self.weather_temp_var).grid(row=1, column=1, sticky="w", padx=5)
        ttk.Label(preview_frame, text="Wind:", font=("", 10, "bold")).grid(row=2, column=0, sticky="w"); ttk.Label(preview_frame, textvariable=self.weather_wind_var).grid(row=2, column=1, sticky="w", padx=5)
        action_frame = ttk.Frame(right_paned, padding="5"); right_paned.add(action_frame, weight=3)
        self.generate_button = ttk.Button(action_frame, text="Generate Weather Activity", command=self.run_generation_thread); self.generate_button.pack(fill=tk.X, pady=5); self.generate_button.config(state=tk.DISABLED)
        self.cleanup_button = ttk.Button(action_frame, text=f"Clean Up *.{APP_SUFFIX}.act Files", command=self.run_cleanup); self.cleanup_button.pack(fill=tk.X, pady=(0,5))
        ttk.Label(action_frame, text="Diagnostic Log", font=("", 10, "bold")).pack(anchor=tk.W)
        self.log_text = scrolledtext.ScrolledText(action_frame, wrap=tk.WORD, state=tk.DISABLED, font=("Courier New", 8)); self.log_text.pack(fill=tk.BOTH, expand=True)
    def log(self, message): self.log_text.config(state=tk.NORMAL); self.log_text.insert(tk.END, message + "\n"); self.log_text.see(tk.END); self.log_text.config(state=tk.DISABLED)
    def is_valid_content_path(self, p): return all((Path(p) / d).is_dir() for d in ["Trains", "Routes", "Global"]) if p and Path(p).is_dir() else False
    def update_paths(self, new_path):
        if self.is_valid_content_path(new_path):
            p = Path(new_path); self.content_path = p; self.path_var.set(str(p)); self.log(f"Content path set to: {p}")
            self.load_orts_tdb(p.parent); self.populate_routes_and_activities()
        else:
            self.content_path = None; self.path_var.set("Invalid Folder!"); self.route_listbox.delete(0, tk.END)
            messagebox.showerror("Invalid Folder", "Please choose the 'Content' folder, containing 'Trains', 'Routes', and 'Global'.")
    def auto_detect_path(self):
        for p in [Path.home() / "Documents" / "Open Rails", Path.home() / "Documents" / "OpenRails"]:
            if self.is_valid_content_path(p / "Content"): self.update_paths(p / "Content"); self.load_orts_tdb(p); return
        self.log("Auto-detection failed. Please select your OR 'Content' folder."); self.path_var.set("Please select 'Content' folder...")
    def select_content_path(self):
        p = filedialog.askdirectory(title="Select your Open Rails 'Content' Folder");
        if p: self.update_paths(p); self.load_orts_tdb(Path(p).parent)
    def load_orts_tdb(self, or_root_path):
        tdb_path = or_root_path / "OrtsTDB.csv"
        self.orts_tdb_data.clear()
        if tdb_path.exists():
            try:
                with open(tdb_path, 'r', encoding='utf-8') as f:
                    reader = csv.reader(f); next(reader)
                    for row in reader:
                        if len(row) >= 3 and row[0] and row[1] and row[2]:
                            self.orts_tdb_data[row[0]] = {'lat': float(row[1]), 'lon': float(row[2])}
                self.log(f"[INFO] Successfully loaded {len(self.orts_tdb_data)} entries from OrtsTDB.csv.")
            except Exception as e: self.log(f"[ERROR] Failed to load OrtsTDB.csv: {e}")
        else: self.log("[WARN] OrtsTDB.csv not found. Location data for some legacy MSTS routes will be unavailable.")
    def populate_routes_and_activities(self):
        self.route_listbox.delete(0, tk.END); self.activity_listbox.delete(0, tk.END)
        self.route_info_map.clear(); self.generate_button.config(state=tk.DISABLED)
        if not self.content_path: self.log("Content folder not set."); return
        self.log("--- Starting New Scan ---"); threading.Thread(target=self._populate_worker, daemon=True).start()
    def _populate_worker(self):
        route_index = {}
        all_trks = sorted(self.content_path.glob("**/ROUTES/**/*.trk"))
        self.log(f"Phase 1: Indexing {len(all_trks)} .trk files...")
        for trk_path in all_trks:
            trk_info = parse_trk_file(trk_path)
            if trk_info and trk_info.get('id'):
                route_id = trk_info['id']; route_index[route_id] = {**trk_info, "folder_name": trk_path.parent.name, "trk_path": trk_path, "activities": []}
        self.log(f"Phase 1 Complete: Indexed {len(route_index)} unique RouteIDs.")
        all_activities = sorted([f for f in self.content_path.glob("**/*.act") if f".{APP_SUFFIX}." not in f.name])
        self.log(f"Phase 2: Linking {len(all_activities)} activity files...")
        for act_path in all_activities:
            route_id = get_route_id_from_activity(act_path)
            if route_id and route_id in route_index:
                route_index[route_id]["activities"].append(act_path)
            elif route_id:
                self.log(f"[WARN] Found RouteID '{route_id}' in activity but no matching .trk file was indexed.")
        self.route_info_map = {data['name']: data for data in route_index.values() if data['activities']}
        self.route_listbox.delete(0, tk.END)
        for route_name in sorted(self.route_info_map.keys()): self.route_listbox.insert(tk.END, route_name)
        self.log(f"--- Scan Complete: Found activities for {len(self.route_info_map)} routes. ---")
    def on_route_select(self, event):
        selections = self.route_listbox.curselection();
        if not selections: return
        self.activity_listbox.delete(0, tk.END); self.current_activity_paths.clear()
        self.generate_button.config(state=tk.DISABLED); self.weather_condition_var.set("---"); self.weather_temp_var.set("---"); self.weather_wind_var.set("---")
        selected_route_name = self.route_listbox.get(selections[0])
        route_data = self.route_info_map.get(selected_route_name)
        if route_data:
            self.route_id_var.set(route_data['id']); self.route_name_var.set(route_data['name']); self.route_folder_var.set(route_data['folder_name']); self.route_desc_var.set(route_data['description'])
            for act_path in sorted(route_data["activities"], key=lambda p: p.name):
                self.activity_listbox.insert(tk.END, act_path.name); self.current_activity_paths[act_path.name] = act_path
    def on_activity_select(self, event):
        selections = self.activity_listbox.curselection();
        if not selections: return
        self.generate_button.config(state=tk.DISABLED)
        if self.route_listbox.curselection():
            threading.Thread(target=self.update_preview_worker, daemon=True).start()
    def update_preview_worker(self):
        selections = self.route_listbox.curselection()
        if not selections: return
        route_data = self.route_info_map.get(self.route_listbox.get(selections[0]))
        if not route_data: self.weather_condition_var.set("Route info error"); return
        self.log_text.config(state=tk.NORMAL); self.log_text.delete(1.0, tk.END); self.log_text.config(state=tk.DISABLED)
        self.log(f"--- Analyzing Route for Weather ---\nRoute: {route_data['name']}")
        lat, lon = find_route_location(route_data, self.orts_tdb_data, self.log)
        if lat is not None:
            self.log(f"  > Location: Lat={lat:.4f}, Lon={lon:.4f}\nFetching current weather...")
            self.weather_condition_var.set("Fetching..."); self.weather_temp_var.set("..."); self.weather_wind_var.set("...")
            weather = fetch_current_weather(lat, lon)
            if weather:
                self.weather_condition_var.set(weather['condition']); self.weather_temp_var.set(weather['temperature']); self.weather_wind_var.set(weather['wind'])
                self.generate_button.config(state=tk.NORMAL)
            else: self.weather_condition_var.set("API Error")
        else: self.weather_condition_var.set("No coords found")
    def run_generation_thread(self):
        selections = self.activity_listbox.curselection()
        if not selections: return
        act_path = self.current_activity_paths.get(self.activity_listbox.get(selections[0]))
        if act_path: threading.Thread(target=self.generate_weather_worker, args=(act_path,), daemon=True).start()
    def generate_weather_worker(self, act_path):
        self.generate_button.config(state=tk.DISABLED); self.log("\n--- Starting Weather Generation ---")
        selections = self.route_listbox.curselection()
        if not selections: self.log("  > FAILED: No route selected."); self.generate_button.config(state=tk.NORMAL); return
        route_data = self.route_info_map.get(self.route_listbox.get(selections[0]))
        if not route_data: self.log("  > FAILED: Route data missing."); self.generate_button.config(state=tk.NORMAL); return
        lat, lon = find_route_location(route_data, self.orts_tdb_data, lambda msg: None)
        if lat is None: self.log("  > FAILED: Cannot find coordinates for this route."); self.generate_button.config(state=tk.NORMAL); return
        self.log(f"Step 1: Using coordinates Lat={lat:.4f}, Lon={lon:.4f}")
        self.log("Step 2: Fetching full weather forecast...")
        weather_events, msg = create_weather_events_string(lat, lon); self.log(f"  > {msg}")
        if not weather_events: self.generate_button.config(state=tk.NORMAL); return
        self.log("Step 3: Creating new activity file..."); new_path, msg = modify_and_save_activity(act_path, weather_events, self.log)
        if new_path: self.log(f"  > {msg}\n  > Saved to: {new_path.name}\n\n--- Generation Complete! ---")
        else: self.log(f"  > FAILED: {msg}")
        self.generate_button.config(state=tk.NORMAL)
    def run_cleanup(self):
        if not self.content_path: messagebox.showwarning("Cleanup", "Content path is not set."); return
        files = list(self.content_path.glob(f"**/*.{APP_SUFFIX}.act"))
        if not files: messagebox.showinfo("Cleanup", "No generated activity files found."); return
        if messagebox.askyesno("Confirm Deletion", f"Found {len(files)} generated files. Permanently delete them?"):
            deleted, errors = 0, 0
            for f in files:
                try: f.unlink(); deleted += 1
                except OSError: errors += 1
            messagebox.showinfo("Cleanup Complete", f"Deleted {deleted} file(s).\nEncountered {errors} error(s)."); self.populate_routes_and_activities()

if __name__ == "__main__":
    app = WeatherApp()
    app.mainloop()