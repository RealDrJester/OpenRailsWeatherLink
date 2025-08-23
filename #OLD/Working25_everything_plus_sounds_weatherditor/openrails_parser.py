# openrails_parser.py
import re
import math
import random
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
        self.current_track_nodes = {}
    def _read_file(self, path):
        try:
            with open(path, 'r', encoding='utf-16-le', errors='strict') as f: return f.read(), 'utf-16-le'
        except (UnicodeError, UnicodeDecodeError):
            try:
                with open(path, 'r', encoding='utf-8-sig', errors='strict') as f: return f.read(), 'utf-8-sig'
            except Exception: return None, None
        except Exception: return None, None
    def load_track_nodes_for_route(self, trk_path_str):
        self.current_track_nodes = {}
        pass
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
        details = {"description": "N/A", "briefing": "N/A", "path_id": None, "existing_weather": [], "season": 1, "start_time": 0}
        content, _ = self._read_file(act_path_str)
        if not content: return details
        def extract_text(key):
            match = re.search(fr'{key}\s*\(\s*"(.*?)"\s*\)', content, re.IGNORECASE | re.DOTALL)
            if match: return match.group(1).replace('"\n\n"+', '').replace('"\n"+', '\n').strip()
            return f"No {key} found."
        details["description"] = extract_text("Description"); details["briefing"] = extract_text("Briefing")
        path_id_match = re.search(r'PathID\s*\(\s*(?:"([^"]*)"|(\S+))\s*(?:\s+[0-9]+)?\s*\)', content, re.IGNORECASE)
        if path_id_match: details["path_id"] = path_id_match.group(1) or path_id_match.group(2)
        season_match = re.search(r'Season\s*\(\s*(\d)\s*\)', content, re.IGNORECASE)
        if season_match: details["season"] = int(season_match.group(1))
        start_time_match = re.search(r'Player_Traffic_Definition\s*\(\s*(\d+)', content, re.IGNORECASE | re.DOTALL)
        if start_time_match:
            details["start_time"] = int(start_time_match.group(1))
        weather_pattern = r'(Event(?:CategoryTime|TypeTime)\s*\(.*?ORTSWeatherChange.*?\)\s*\))'
        weather_events = re.findall(weather_pattern, content, re.DOTALL | re.IGNORECASE)
        if weather_events: 
            details["existing_weather"] = weather_events
        return details
    def find_route_start_location(self, route_data):
        trk_path = Path(route_data['trk_path']); route_id = route_data['id']
        content, _ = self._read_file(trk_path)
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
        self.log(f"[ERROR] No coordinate source found for RouteID '{route_id}'."); return None, None
    def get_activity_path_coords(self, route_path_str, path_id):
        if not path_id: self.log("[INFO] PathID not found in activity file. Cannot draw path."); return []
        pat_path = Path(route_path_str) / "PATHS" / f"{path_id}.pat"
        if not pat_path.exists(): self.log(f"[ERROR] Path file not found: {pat_path.name}"); return []
        self.log(f"[INFO] Parsing activity path: {pat_path.name}")
        content, _ = self._read_file(pat_path)
        if not content: self.log(f"[ERROR] Could not read path file."); return []
        pdp_pattern = re.compile(r'TrackPDP\s*\(\s*(-?\d+)\s+(-?\d+)\s+([\d\.-]+)\s+([\d\.-]+)\s+([\d\.-]+)', re.IGNORECASE)
        path_node_pattern = re.compile(r'TrPathNode\s*\(\s*\w+\s+\w+\s+\w+\s+(\d+)\s*\)', re.IGNORECASE)
        pdp_list = [ {'tile_x': int(m[1]), 'tile_z': int(m[2]), 'offset_x': float(m[3]), 'offset_z': float(m[5])} for m in pdp_pattern.finditer(content) ]
        path_indices = [int(m.group(1)) for m in path_node_pattern.finditer(content)]
        if not pdp_list or not path_indices:
            self.log(f"[WARN] No valid path data found in {pat_path.name}"); return []
        path_coords = []; sample_rate = max(1, len(path_indices) // 100)
        for i, pdp_index in enumerate(path_indices):
            if i % sample_rate == 0 or i == len(path_indices) - 1:
                if pdp_index < len(pdp_list):
                    node_data = pdp_list[pdp_index]
                    lat, lon = self.goode.ConvertWTC(node_data['tile_x'], node_data['tile_z'], node_data['offset_x'], node_data['offset_z'])
                    if lat is not None: path_coords.append((lat, lon))
        self.log(f"[INFO] Generated map path with {len(path_coords)} points.")
        return path_coords
    def modify_and_save_activity(self, original_path_str, act_events_content, date_obj=None, chaotic=False, manual_suffix=None, season=None):
        original_path = Path(original_path_str)
        try:
            if manual_suffix:
                filename_suffix = f"{APP_SUFFIX}.{manual_suffix}"
                name_suffix = f"[{APP_SUFFIX}.{manual_suffix}]"
            else:
                date_str = date_obj.strftime("%Y%m%d") if date_obj else datetime.now().strftime("%Y%m%d")
                filename_suffix = f"{APP_SUFFIX}.CHAOTIC" if chaotic else f"{APP_SUFFIX}.{date_str}"
                name_suffix = f"[{APP_SUFFIX}.CHAOTIC]" if chaotic else f"[{APP_SUFFIX}.{date_str}]"
            
            base_stem = re.split(fr'\.{APP_SUFFIX}\.', original_path.stem)[0]
            new_path = original_path.parent / f"{base_stem}.{filename_suffix}.act"

            shutil.copy2(original_path, new_path)
            self.log(f"  > Created safe copy: {new_path.name}")
            new_content, original_encoding = self._read_file(new_path)
            if not new_content: return None, "Failed to read the newly created copy."
            name_pattern = re.compile(r'(Name\s*\(\s*")([^"]*)(")', re.IGNORECASE)
            name_match = name_pattern.search(new_content)
            if name_match:
                original_name = name_match.group(2).split(' [')[0]
                new_activity_name = f"{original_name} {name_suffix}"
                replacement_string = f'{name_match.group(1)}{new_activity_name}{name_match.group(3)}'
                new_content = name_pattern.sub(replacement_string, new_content, count=1)
                self.log(f"  > Renamed activity to: \"{new_activity_name}\"")
            else: self.log("  > WARNING: Could not find activity Name() to rename.")

            if season is not None:
                season_pattern = re.compile(r'(\bSeason\s*\(\s*)(\d)(\s*\))', re.IGNORECASE)
                if season_pattern.search(new_content):
                    new_content = season_pattern.sub(fr'\g<1>{season}\g<3>', new_content, count=1)
                    self.log(f"  > Changed season to: {season}")

            events_match = re.search(r'(\bEvents\s*\(\s*)(.*?)(\s*\)\s*\))', new_content, re.IGNORECASE | re.DOTALL)
            if not events_match: return None, "Could not find 'Events ()' block."
            clean_events_content = re.sub(r'\s*EventCategoryTime\s*\(\s*Name\s*\(\s*WTHLINK_.*?\)\s*.*?\)', '', events_match.group(2), flags=re.DOTALL | re.IGNORECASE).strip()
            final_content = f"{new_content[:events_match.start(2)]}\n{act_events_content}\n{clean_events_content}\n\t{new_content[events_match.end(2):]}"
            with open(new_path, 'w', encoding=original_encoding) as f: f.write(final_content)
            return new_path, "New activity file created successfully!"
        except Exception as e: return None, f"Error saving files: {e}"

    def cleanup_generated_files(self, search_path_str):
        search_path = Path(search_path_str)
        if not search_path.is_dir():
            return 0, 0

        act_pattern = f"*.{APP_SUFFIX}.*.act"
        files_to_delete = list(search_path.glob(f"**/{act_pattern}"))
        deleted_act_count = 0
        for f in files_to_delete:
            try:
                f.unlink()
                deleted_act_count += 1
                self.log(f"Deleted activity: {f.name}")
            except OSError as e:
                self.log(f"Could not delete {f.name}: {e}")

        sound_pattern = "WEATHERLINK_*.wav"
        sound_files_to_delete = list(search_path.glob(f"**/SOUND/{sound_pattern}"))
        deleted_sound_count = 0
        for f in sound_files_to_delete:
            try:
                f.unlink()
                deleted_sound_count += 1
                self.log(f"Deleted sound: {f.name}")
            except OSError as e:
                self.log(f"Could not delete {f.name}: {e}")
        
        return deleted_act_count, deleted_sound_count