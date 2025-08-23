# openrails_parser.py
import re
import math
from pathlib import Path
from datetime import datetime
import shutil

APP_SUFFIX = "WTHLINK"

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

class OpenRailsParser:
    def __init__(self, content_path_str, log_callback=print):
        self.content_path = Path(content_path_str); self.routes_path = self.content_path / "ROUTES"; self.goode = GoodeProjection(); self.log = log_callback
    def _read_file(self, path):
        try:
            with open(path, 'r', encoding='utf-16-le', errors='strict') as f: return f.read(), 'utf-16-le'
        except (UnicodeError, UnicodeDecodeError):
            try:
                with open(path, 'r', encoding='utf-8-sig', errors='strict') as f: return f.read(), 'utf-8-sig'
            except Exception: return None, None
        except Exception: return None, None
    def get_all_routes(self):
        routes = {}
        if not self.routes_path.is_dir(): return {}
        for trk_path in sorted(self.routes_path.glob("**/*.trk")):
            content, _ = self._read_file(trk_path)
            if not content: continue
            name_match = re.search(r'Name\s*\(\s*"(.*?)"\s*\)', content, re.IGNORECASE | re.DOTALL)
            route_id_match = re.search(r'RouteID\s*\(\s*([\w\s\-\.]+)\s*\)', content, re.IGNORECASE | re.DOTALL)
            if name_match and route_id_match: routes[name_match.group(1)] = {"id": route_id_match.group(1).strip(), "path": str(trk_path.parent), "trk_path": str(trk_path)}
        return routes
    def get_activities_for_route(self, route_path_str):
        activities = {}; activities_path = Path(route_path_str) / "ACTIVITIES"
        if not activities_path.is_dir(): return {}
        for act_path in sorted(activities_path.glob("*.act")):
            content, _ = self._read_file(act_path)
            if not content: continue
            name_match = re.search(r'\sName\s*\(\s*"(.*?)"\s*\)', content, re.IGNORECASE | re.DOTALL)
            if name_match:
                has_weather_version = any(activities_path.glob(f"{act_path.stem.split('.')[0]}.{APP_SUFFIX}.*.act"))
                activities[act_path.name] = {"display_name": name_match.group(1), "path": str(act_path), "has_weather": has_weather_version}
        return activities
    def get_activity_details(self, act_path_str):
        details = {"description": "N/A", "briefing": "N/A", "path_id": None, "existing_weather": [], "season": 1}
        content, _ = self._read_file(act_path_str)
        if not content: return details
        def extract_text(key):
            match = re.search(fr'{key}\s*\(\s*"(.*?)"\s*\)', content, re.IGNORECASE | re.DOTALL)
            if match: return match.group(1).replace('"\n\n"+', '').replace('"\n"+', '\n').strip()
            return f"No {key} found."
        details["description"] = extract_text("Description"); details["briefing"] = extract_text("Briefing")
        path_id_match = re.search(r'PathID\s*\(\s*(\w+)\s*\)', content, re.IGNORECASE)
        if path_id_match: details["path_id"] = path_id_match.group(1)
        season_match = re.search(r'Season\s*\(\s*(\d)\s*\)', content, re.IGNORECASE)
        if season_match: details["season"] = int(season_match.group(1))
        weather_events = re.findall(r'ORTSWeatherChange\s*\((.*?)\)', content, re.DOTALL)
        if weather_events: details["existing_weather"] = weather_events
        return details
    def find_route_start_location(self, route_data):
        trk_path = Path(route_data['trk_path']); content, _ = self._read_file(trk_path)
        if not content: return None, None
        lat_match = re.search(r'ORTSLatitude\s*\(\s*(-?\d+\.?\d*)\s*\)', content, re.IGNORECASE)
        lon_match = re.search(r'ORTSLongitude\s*\(\s*(-?\d+\.?\d*)\s*\)', content, re.IGNORECASE)
        if lat_match and lon_match:
            self.log("[SUCCESS] Found modern coordinates in .trk file."); return float(lat_match.group(1)), float(lon_match.group(1))
        rs_match = re.search(r'RouteStart\s*\(\s*(-?\d+)\s+(-?\d+)\s+(-?\d+\.?\d*)\s+(-?\d+\.?\d*)\s*\)', content, re.IGNORECASE)
        if rs_match:
            tile_x, tile_z, offset_x, offset_z = map(float, rs_match.groups())
            lat, lon = self.goode.ConvertWTC(int(tile_x), int(tile_z), offset_x, offset_z)
            if lat is not None and lon is not None:
                self.log(f"[SUCCESS] Calculated coordinates via Goode projection."); return lat, lon
        self.log(f"[ERROR] No coordinate source found."); return None, None
    def modify_and_save_activity(self, original_path_str, act_events_content, date_obj=None, chaotic=False):
        original_path = Path(original_path_str)
        try:
            date_str = date_obj.strftime("%Y%m%d") if date_obj else datetime.now().strftime("%Y%m%d")
            filename_suffix = f"{APP_SUFFIX}.CHAOTIC" if chaotic else f"{APP_SUFFIX}.{date_str}"
            new_path = original_path.parent / f"{original_path.stem.split('.')[0]}.{filename_suffix}.act"
            shutil.copy2(original_path, new_path)
            self.log(f"  > Created safe copy: {new_path.name}")
            new_content, original_encoding = self._read_file(new_path)
            if not new_content: return None, "Failed to read the newly created copy."
            name_pattern = re.compile(r'(Name\s*\(\s*")([^"]*)(")', re.IGNORECASE)
            name_match = name_pattern.search(new_content)
            if name_match:
                original_name = name_match.group(2).split(' [')[0]
                name_suffix = f"[{APP_SUFFIX}.CHAOTIC]" if chaotic else f"[{APP_SUFFIX}.{date_str}]"
                new_activity_name = f"{original_name} {name_suffix}"
                replacement_string = f'{name_match.group(1)}{new_activity_name}{name_match.group(3)}'
                new_content = name_pattern.sub(replacement_string, new_content, count=1)
                self.log(f"  > Renamed activity to: \"{new_activity_name}\"")
            else: self.log("  > WARNING: Could not find activity Name() to rename.")
            
            # Remove any old weather events from anywhere in the file to ensure a clean slate
            new_content = re.sub(r'\s*ORTSWeatherChange\s*\(\s*.*?\s*\)', '', new_content, flags=re.DOTALL)
            
            # CORE BUG FIX: Inject into Tr_Activity_File, not Events
            activity_file_match = re.search(r'(\bTr_Activity_File\s*\(\s*)', new_content, re.IGNORECASE | re.DOTALL)
            if not activity_file_match: return None, "Could not find 'Tr_Activity_File ()' block."
            
            injection_point = activity_file_match.end(1)
            final_content = f"{new_content[:injection_point]}\n{act_events_content}\n{new_content[injection_point:]}"
            
            with open(new_path, 'w', encoding=original_encoding) as f: f.write(final_content)
            return new_path, "New activity file created successfully!"
        except Exception as e: return None, f"Error saving files: {e}"