# 🚫 AI INSTRUCTIONS: DO NOT MODIFY UNLESS EXPLICITLY REQUESTED
# This section is protected. You may only:
# - Fix bugs that are clearly identified
# - Implement specific changes as described by the user
# ❌ Do NOT refactor, rename, delete, or restructure anything here
# ❌ Do NOT change logic, functionality, or formatting unless asked
# If unsure, ASK the user before making changes.

# main_app.py
# main_app.py
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import threading
from pathlib import Path
import sv_ttk
import sys
import re

from config_manager import ConfigManager
import openrails_parser
from weather_service import WeatherService
from ui_components import AboutWindow, ForecastChart, DateSelectionWindow, TKCALENDAR_AVAILABLE

try:
    from tkintermapview import TkinterMapView
except ImportError:
    messagebox.showerror("Missing Library", "The 'tkintermapview' library is not installed.\n\nPlease open a command prompt and run:\npip install tkintermapview")
    sys.exit(1)

class MainApplication(tk.Tk):
    def __init__(self):
        super().__init__()
        self.config = ConfigManager(); self.parser = None; self.weather = WeatherService()
        self.current_route_data = {}; self.current_activities = {}; self.selected_activity_path = None; self.found_coords = None
        self.historical_selection = None
        self.activity_details = {}
        self.title("ORTS WeatherLink"); self.geometry(self.config.get('window_geometry')); self.protocol("WM_DELETE_WINDOW", self.on_closing)
        sv_ttk.set_theme(self.config.get('theme')); self.setup_ui(); self.post_ui_load()

    def setup_ui(self):
        top_frame = ttk.Frame(self, padding=(10, 10, 10, 0)); top_frame.pack(fill=tk.X, side=tk.TOP); top_frame.grid_columnconfigure(1, weight=1)
        ttk.Label(top_frame, text="Content Folder:").grid(row=0, column=0, sticky='w', padx=(0, 5))
        self.path_combo = ttk.Combobox(top_frame, values=self.config.get('content_paths')); self.path_combo.grid(row=0, column=1, sticky='ew')
        self.path_combo.bind("<<ComboboxSelected>>", self.on_path_selected)
        browse_button = ttk.Button(top_frame, text="Browse...", command=self.select_content_path); browse_button.grid(row=0, column=2, sticky='e', padx=(5, 10))
        self.theme_button = ttk.Button(top_frame, text="Toggle Theme", command=self.toggle_theme); self.theme_button.grid(row=0, column=3, sticky='e')

        main_paned = ttk.PanedWindow(self, orient=tk.HORIZONTAL); main_paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=(10,0))
        left_pane = ttk.PanedWindow(main_paned, orient=tk.VERTICAL); main_paned.add(left_pane, weight=1)

        route_frame = ttk.LabelFrame(left_pane, text="1. Select Route", padding=5)
        self.route_scrollbar = ttk.Scrollbar(route_frame, orient=tk.VERTICAL)
        self.route_listbox = tk.Listbox(route_frame, exportselection=False, yscrollcommand=self.route_scrollbar.set); self.route_scrollbar.config(command=self.route_listbox.yview)
        self.route_scrollbar.pack(side=tk.RIGHT, fill=tk.Y); self.route_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.route_listbox.bind("<<ListboxSelect>>", self.on_route_select)
        left_pane.add(route_frame, weight=2)

        activity_frame = ttk.LabelFrame(left_pane, text="2. Select Activity", padding=5)
        self.activity_scrollbar = ttk.Scrollbar(activity_frame, orient=tk.VERTICAL)
        self.activity_listbox = tk.Listbox(activity_frame, exportselection=False, yscrollcommand=self.activity_scrollbar.set); self.activity_scrollbar.config(command=self.activity_listbox.yview)
        self.activity_scrollbar.pack(side=tk.RIGHT, fill=tk.Y); self.activity_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.activity_listbox.bind("<<ListboxSelect>>", self.on_activity_select)
        left_pane.add(activity_frame, weight=3)

        right_pane = ttk.PanedWindow(main_paned, orient=tk.VERTICAL); main_paned.add(right_pane, weight=3)
        details_notebook = ttk.Notebook(right_pane); right_pane.add(details_notebook, weight=2)
        
        desc_frame = ttk.Frame(details_notebook); self.desc_text = scrolledtext.ScrolledText(desc_frame, wrap=tk.WORD, state=tk.DISABLED); self.desc_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5); details_notebook.add(desc_frame, text="Description & Briefing")
        ew_pane = ttk.PanedWindow(details_notebook, orient=tk.HORIZONTAL); details_notebook.add(ew_pane, text="Existing Weather")
        ew_raw_frame = ttk.LabelFrame(ew_pane, text="Raw Data", padding=5); self.existing_weather_raw = scrolledtext.ScrolledText(ew_raw_frame, wrap=tk.WORD, state=tk.DISABLED, font=("Courier New", 8)); self.existing_weather_raw.pack(fill=tk.BOTH, expand=True); ew_pane.add(ew_raw_frame, weight=1)
        
        ew_human_frame = ttk.LabelFrame(ew_pane, text="Human-Readable", padding=5)
        self.existing_weather_human_scrollbar = ttk.Scrollbar(ew_human_frame, orient=tk.VERTICAL)
        self.existing_weather_human = ttk.Treeview(ew_human_frame, columns=('param', 'value'), show='headings', yscrollcommand=self.existing_weather_human_scrollbar.set)
        self.existing_weather_human_scrollbar.config(command=self.existing_weather_human.yview)
        self.existing_weather_human.heading('param', text='Parameter'); self.existing_weather_human.heading('value', text='Value'); self.existing_weather_human.column('param', width=120)
        self.existing_weather_human_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.existing_weather_human.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        ew_pane.add(ew_human_frame, weight=1)
        
        forecast_frame = ttk.Frame(details_notebook); self.forecast_text = scrolledtext.ScrolledText(forecast_frame, wrap=tk.WORD, state=tk.DISABLED, font=("Courier New", 9)); self.forecast_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5); details_notebook.add(forecast_frame, text="Forecast Table")
        chart_frame = ttk.Frame(details_notebook); self.chart_widget = ForecastChart(chart_frame); self.chart_widget.pack(fill=tk.BOTH, expand=True); details_notebook.add(chart_frame, text="Forecast Chart")
        log_frame_tab = ttk.Frame(details_notebook); self.log_text = scrolledtext.ScrolledText(log_frame_tab, wrap=tk.WORD, state=tk.DISABLED, font=("Courier New", 8), height=8); self.log_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        ttk.Button(log_frame_tab, text="Generate Chaotic Weather (for testing)", command=self.run_chaotic_generation).pack(fill=tk.X, pady=5)
        details_notebook.add(log_frame_tab, text="Debug Console")

        map_actions_pane = ttk.PanedWindow(right_pane, orient=tk.HORIZONTAL); right_pane.add(map_actions_pane, weight=3)
        map_frame = ttk.LabelFrame(map_actions_pane, text="Activity Path", padding=5)
        self.map_widget = TkinterMapView(map_frame, corner_radius=0); self.map_widget.pack(fill=tk.BOTH, expand=True)
        map_actions_pane.add(map_frame, weight=2)

        action_frame = ttk.Frame(map_actions_pane, padding=10)
        self.weather_mode_label = ttk.Label(action_frame, text="Previewing: N/A", font=("", 9, "italic")); self.weather_mode_label.pack(fill=tk.X, pady=(0,10))
        self.generate_button = ttk.Button(action_frame, text="Generate Activity File", state=tk.DISABLED, command=self.run_generation_thread); self.generate_button.pack(fill=tk.X, pady=5)
        self.historical_button = ttk.Button(action_frame, text="Select Historical Date...", state=tk.DISABLED, command=self.select_historical_date); self.historical_button.pack(fill=tk.X, pady=5)
        self.current_weather_button = ttk.Button(action_frame, text="Load Current Weather", command=self.load_current_weather_action);
        self.force_snow_var = tk.BooleanVar(value=True)
        self.force_snow_check = ttk.Checkbutton(action_frame, text="Force Snow in Winter", variable=self.force_snow_var); self.force_snow_check.pack(fill=tk.X, pady=5)
        ttk.Button(action_frame, text=f"Clean Up *.{openrails_parser.APP_SUFFIX}.*.act Files", command=self.run_cleanup).pack(fill=tk.X, pady=5)
        ttk.Button(action_frame, text="About...", command=self.show_about_window).pack(fill=tk.X, side=tk.BOTTOM, pady=(20, 5))
        map_actions_pane.add(action_frame, weight=1)

        status_frame = ttk.Frame(self, padding=(10,5,10,5)); status_frame.pack(fill=tk.X, side=tk.BOTTOM)
        self.status_label = ttk.Label(status_frame, text="Ready"); self.status_label.pack(side=tk.LEFT)
        self.progress_bar = ttk.Progressbar(status_frame, mode='indeterminate'); self.progress_bar.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(10,0))

    def log(self, message): self.after(0, self._log_to_widget, message)
    def _log_to_widget(self, message): self.log_text.config(state=tk.NORMAL); self.log_text.insert(tk.END, message + "\n"); self.log_text.see(tk.END); self.log_text.config(state=tk.DISABLED)
    def on_closing(self): self.config.set('window_geometry', self.geometry()); self.destroy()
    def show_about_window(self): AboutWindow(self)
    def toggle_theme(self): new_theme = 'dark' if self.config.get('theme') == 'light' else 'light'; sv_ttk.set_theme(new_theme); self.config.set('theme', new_theme); self.chart_widget.update_theme()
    def start_loading(self, message): self.status_label.config(text=message); self.progress_bar.start(10)
    def stop_loading(self): self.status_label.config(text="Ready"); self.progress_bar.stop(); self.progress_bar.pack_forget(); self.progress_bar.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(10,0))
    def post_ui_load(self):
        last_path = self.config.get('last_content_path')
        if last_path: self.path_combo.set(last_path); self.load_content_folder(last_path)
        else: self.auto_detect_path()
    def select_content_path(self):
        path = filedialog.askdirectory(title="Select Open Rails 'Content' Folder")
        if path and Path(path).is_dir():
            self.config.add_content_path(path); self.path_combo['values'] = self.config.get('content_paths'); self.path_combo.set(path); self.load_content_folder(path)
    def on_path_selected(self, event=None): self.load_content_folder(self.path_combo.get())
    def load_content_folder(self, path):
        if not path or not Path(path).is_dir(): return
        self.config.set('last_content_path', path); self.parser = openrails_parser.OpenRailsParser(path, self.log); self.populate_routes()
    def auto_detect_path(self):
        for p_str in [str(Path.home() / "Documents" / d / "Content") for d in ["Open Rails", "OpenRails"]]:
            p = Path(p_str)
            if p.is_dir() and (p / "ROUTES").is_dir():
                self.config.add_content_path(p_str); self.path_combo['values'] = self.config.get('content_paths'); self.path_combo.set(p_str); self.load_content_folder(p_str); return
    def populate_routes(self):
        self.route_listbox.delete(0, tk.END); self.activity_listbox.delete(0, tk.END); self.clear_info()
        self.current_route_data = self.parser.get_all_routes()
        for name in sorted(self.current_route_data.keys()): self.route_listbox.insert(tk.END, name)
    def on_route_select(self, event=None):
        selections = self.route_listbox.curselection()
        if not selections: return
        self.activity_listbox.delete(0, tk.END); self.clear_info()
        selected_route_name = self.route_listbox.get(selections[0])
        route_info = self.current_route_data.get(selected_route_name)
        if route_info: threading.Thread(target=self.load_activities_for_route, args=(route_info,), daemon=True).start()
    def load_activities_for_route(self, route_info):
        self.after(0, self.start_loading, f"Loading activities for {route_info['id']}..."); self.parser.load_track_nodes_for_route(route_info['trk_path']); self.current_activities = self.parser.get_activities_for_route(route_info['path']); self.after(0, self._populate_activities_list); self.after(0, self.stop_loading)
    def _populate_activities_list(self):
        self.activity_listbox.delete(0, tk.END)
        for i, (act_file, act_data) in enumerate(sorted(self.current_activities.items())):
            self.activity_listbox.insert(tk.END, f"{act_data['display_name']} ({act_file})")
            if act_data.get('has_weather'): self.activity_listbox.itemconfig(i, {'bg': '#502020'} if sv_ttk.get_theme() == 'dark' else '#FFDDDD')
    def on_activity_select(self, event=None):
        selections = self.activity_listbox.curselection()
        if not selections: return
        self.start_loading("Loading activity details...")
        selected_display = self.activity_listbox.get(selections[0])
        for act_data in self.current_activities.values():
            if f"{act_data['display_name']} ({Path(act_data['path']).name})" == selected_display:
                self.selected_activity_path = act_data['path']; threading.Thread(target=self.update_activity_info, daemon=True).start(); break
    def update_activity_info(self):
        self.activity_details = self.parser.get_activity_details(self.selected_activity_path); self.after(0, lambda: self.update_details_text(self.activity_details))
        route_info = self.current_route_data.get(self.route_listbox.get(self.route_listbox.curselection()[0]))
        path_coords = self.parser.get_activity_path_coords(route_info['path'], self.activity_details['path_id'])
        if path_coords:
            self.found_coords = path_coords[0]; self.after(0, lambda: self._update_map_with_path(path_coords)); self.update_weather_info(self.found_coords[0], self.found_coords[1])
        else:
            lat, lon = self.parser.find_route_start_location(route_info); self.found_coords = (lat, lon)
            if lat is not None: self.after(0, lambda: self._update_map_with_start_point(lat, lon)); self.update_weather_info(lat, lon)
            else: self.after(0, lambda: self.clear_weather_info("No coordinates found."))
        self.after(0, self.stop_loading)
    def _update_map_with_path(self, path_coords):
        self.map_widget.delete_all_path(); self.map_widget.delete_all_marker()
        if len(path_coords) >= 2:  # Use working version condition
            path = self.map_widget.set_path(path_coords, color="crimson", width=7)
            self.map_widget.set_marker(path_coords[0][0], path_coords[0][1], text="Start", text_color="white", marker_color_circle="#229922", marker_color_outside="darkgreen")
            self.map_widget.set_marker(path_coords[-1][0], path_coords[-1][1], text="End", text_color="white", marker_color_circle="#C70039", marker_color_outside="darkred")
            # Use working version bounding box method
            self.map_widget.fit_bounding_box(path.bounding_box)
        elif len(path_coords) == 1:
            self.map_widget.set_marker(path_coords[0][0], path_coords[0][1], text="Single Point"); self.map_widget.set_position(path_coords[0][0], path_coords[0][1], zoom=10)
    def _update_map_with_start_point(self, lat, lon):
        self.map_widget.delete_all_path(); self.map_widget.delete_all_marker()
        self.map_widget.set_marker(lat, lon, text="Activity Start (No Path Data)"); self.map_widget.set_position(lat, lon, zoom=10)
    def update_details_text(self, details):
        self.desc_text.config(state=tk.NORMAL); self.desc_text.delete(1.0, tk.END); self.desc_text.insert(tk.END, f"--- DESCRIPTION ---\n{details['description']}\n\n--- BRIEFING ---\n{details['briefing']}"); self.desc_text.config(state=tk.DISABLED)
        self.existing_weather_raw.config(state=tk.NORMAL); self.existing_weather_raw.delete(1.0, tk.END)
        for item in self.existing_weather_human.get_children(): self.existing_weather_human.delete(item)
        if not details['existing_weather']:
            self.existing_weather_raw.insert(tk.END, "No ORTSWeatherChange events found in this file.")
        else:
            self.existing_weather_raw.insert(tk.END, "\n".join(details['existing_weather']))
            self.parse_and_display_existing_weather(details)
        self.existing_weather_raw.config(state=tk.DISABLED)
        
    def parse_and_display_existing_weather(self, details):
        seasons = {0: "Spring", 1: "Summer", 2: "Autumn", 3: "Winter"}
        self.existing_weather_human.insert('', 'end', values=("Activity Season", f"{seasons.get(details['season'], 'Unknown')} ({details['season']})"))
        
        # Add separator
        self.existing_weather_human.insert('', 'end', values=("─" * 25, "─" * 25))
        
        for event_index, event_block in enumerate(details['existing_weather']):
            # Extract Time
            time_match = re.search(r'Time\s*\(\s*(\d+)\s*\)', event_block)
            time_val = int(time_match.group(1)) if time_match else 'N/A'
            
            # Extract Name for identification
            name_match = re.search(r'Name\s*\(\s*([^)]+)\s*\)', event_block)
            event_name = name_match.group(1).strip() if name_match else f'Weather Event #{event_index + 1}'
            
            # Improved parameter extraction function
            def get_orts_param(name):
                # More flexible regex that handles various whitespace patterns
                pattern = fr'{name}\s*\(\s*([\d\.-]+)(?:\s+([\d\.-]+))?\s*\)'
                match = re.search(pattern, event_block, re.IGNORECASE)
                if match:
                    value = match.group(1)
                    duration = match.group(2) if match.group(2) else None
                    return value, duration
                return None, None
            
            # Extract all weather parameters
            overcast, overcast_duration = get_orts_param('ORTSOvercast')
            fog, fog_duration = get_orts_param('ORTSFog')
            precip, precip_duration = get_orts_param('ORTSPrecipitationIntensity')
            liquid, liquid_duration = get_orts_param('ORTSPrecipitationLiquidity')
            
            # Display the event header with time formatting
            if time_val != 'N/A':
                hours = time_val // 3600
                minutes = (time_val % 3600) // 60
                seconds = time_val % 60
                time_display = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
                self.existing_weather_human.insert('', 'end', values=(f"⏰ TIME: {time_display}", f"{time_val}s"))
                self.existing_weather_human.insert('', 'end', values=(f"📝 EVENT: {event_name}", ""))
            
            # Display weather parameters grouped by category
            if overcast:
                overcast_percent = float(overcast) * 100
                duration_text = f" (transition: {overcast_duration}s)" if overcast_duration else ""
                self.existing_weather_human.insert('', 'end', values=("☁️  Cloud Cover", f"{overcast_percent:.0f}%{duration_text}"))
            
            if fog:
                fog_km = float(fog) / 1000.0
                duration_text = f" (transition: {fog_duration}s)" if fog_duration else ""
                self.existing_weather_human.insert('', 'end', values=("👁️  Visibility", f"{fog_km:.1f} km{duration_text}"))
            
            if precip:
                precip_mm = float(precip) * 1000.0
                duration_text = f" (transition: {precip_duration}s)" if precip_duration else ""
                if precip_mm > 0:
                    self.existing_weather_human.insert('', 'end', values=("🌧️  Precipitation", f"{precip_mm:.1f} mm/h{duration_text}"))
                else:
                    self.existing_weather_human.insert('', 'end', values=("☀️  Precipitation", f"None (0.0 mm/h){duration_text}"))
            
            if liquid:
                liquid_val = float(liquid)
                duration_text = f" (transition: {liquid_duration}s)" if liquid_duration else ""
                if liquid_val > 0.5:
                    self.existing_weather_human.insert('', 'end', values=("🌧️  Precip. Type", f"Rain ({liquid_val:.1f}){duration_text}"))
                else:
                    self.existing_weather_human.insert('', 'end', values=("❄️  Precip. Type", f"Snow ({liquid_val:.1f}){duration_text}"))
            
            # Add separator between events if there are more events
            if event_index < len(details['existing_weather']) - 1:
                self.existing_weather_human.insert('', 'end', values=("", ""))

    def update_weather_info(self, lat, lon, date_obj=None):
        self.start_loading("Fetching weather data..."); self.historical_selection = {'date': date_obj} if date_obj else None
        data = self.weather.get_weather_data(lat, lon, date_obj); self.after(0, lambda: self._update_weather_widgets(data, date_obj)); self.stop_loading()
    def _update_weather_widgets(self, data, date_obj):
        if not data: self.clear_weather_info("Failed to fetch weather data."); return
        self.generate_button.config(state=tk.NORMAL); self.historical_button.config(state=tk.NORMAL if TKCALENDAR_AVAILABLE else tk.DISABLED)
        if self.historical_selection:
            date_str = self.historical_selection['date'].strftime('%Y-%m-%d'); self.weather_mode_label.config(text=f"Preview: Historical ({date_str})"); self.current_weather_button.pack(fill=tk.X, pady=5); self.generate_button.config(text="Generate Historical Activity")
        else:
            self.weather_mode_label.config(text="Previewing: Live Weather"); self.current_weather_button.pack_forget(); self.generate_button.config(text="Generate Live Weather Activity")
        hourly = data.get("hourly", {}); header = f"{'Time':<8}{'Temp':<8}{'Precip':<10}{'Clouds':<10}{'Wind':<15}{'View':<10}{'Condition'}\n"; 
        self.forecast_text.config(state=tk.NORMAL); self.forecast_text.delete(1.0, tk.END); self.forecast_text.insert(tk.END, header + "-"*(len(header)+10) + "\n")
        def deg_to_dir(deg): dirs = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]; return dirs[int((deg + 11.25) / 22.5) % 16] if deg is not None else "N/A"
        for i in range(min(24, len(hourly.get('time', [])))):
            temp = f"{hourly['temperature_2m'][i]:.1f}°C" if hourly['temperature_2m'][i] is not None else "N/A"
            precip = f"{hourly['precipitation'][i]:.1f}mm" if hourly['precipitation'][i] is not None else "N/A"
            clouds = f"{hourly['cloudcover'][i]}%" if hourly['cloudcover'][i] is not None else "N/A"
            wind_s = hourly['windspeed_10m'][i]; wind_d = hourly['winddirection_10m'][i]; wind = f"{wind_s:.1f}km/h {deg_to_dir(wind_d)}" if wind_s is not None else "N/A"
            vis = f"{hourly['visibility'][i]/1000:.1f}km" if hourly.get('visibility') and hourly['visibility'][i] is not None else "N/A"
            cond = self.weather.WMO_CODES.get(hourly['weathercode'][i], 'N/A') if hourly['weathercode'][i] is not None else "N/A"
            line = f"{hourly['time'][i][-5:]:<8}{temp:<8}{precip:<10}{clouds:<10}{wind:<15}{vis:<10}{cond}\n"
            self.forecast_text.insert(tk.END, line)
        self.forecast_text.config(state=tk.DISABLED); self.chart_widget.plot_data(hourly, date_obj.strftime("%Y-%m-%d") if date_obj else "Live")
    def select_historical_date(self):
        if not self.found_coords: messagebox.showwarning("Warning", "Please select an activity first."); return
        dialog = DateSelectionWindow(self); self.wait_window(dialog)
        if dialog.result:
            self.historical_selection = dialog.result; lat, lon = self.found_coords
            threading.Thread(target=self.update_weather_info, args=(lat, lon, self.historical_selection['date']), daemon=True).start()
    def load_current_weather_action(self):
        if not self.found_coords: return
        lat, lon = self.found_coords; threading.Thread(target=self.update_weather_info, args=(lat, lon), daemon=True).start()
    def run_generation_thread(self, chaotic=False): threading.Thread(target=self.generate_weather_worker, args=(chaotic,), daemon=True).start()
    def run_chaotic_generation(self):
        if not self.selected_activity_path: messagebox.showwarning("Warning", "Please select an activity first."); return
        self.run_generation_thread(chaotic=True)
    def generate_weather_worker(self, chaotic=False):
        self.after(0, self.start_loading, "Generating new activity file...")
        if not self.selected_activity_path: self.log("  > FAILED: No activity selected."); self.after(0, self.stop_loading); return
        lat, lon = self.found_coords
        if lat is None: self.log("  > FAILED: Coordinates not found."); self.after(0, self.stop_loading); self.after(0, lambda: self.generate_button.config(state=tk.NORMAL)); return
        if chaotic:
            weather_events, msg = self.weather.create_chaotic_weather_events(); date_obj = None
        else:
            date_obj = self.historical_selection['date'] if self.historical_selection else None
            start_hour = self.historical_selection['hour'] if self.historical_selection else 0
            season = self.activity_details.get('season', 1)
            force_snow = self.force_snow_var.get()
            weather_events, msg = self.weather.create_weather_events_string(lat, lon, season, force_snow, date_obj, start_hour)
        if not weather_events: self.log(f"  > FAILED: {msg}"); self.after(0, self.stop_loading); self.after(0, lambda: self.generate_button.config(state=tk.NORMAL)); return
        self.log(f"  > {msg}")
        new_path, msg = self.parser.modify_and_save_activity(self.selected_activity_path, weather_events, date_obj, chaotic)
        if new_path: self.log(f"  > {msg}\n  > Saved to: {Path(new_path).name}\n\n--- Generation Complete! ---")
        else: self.log(f"  > FAILED: {msg}")
        self.after(0, self.stop_loading); self.after(0, lambda: self.generate_button.config(state=tk.NORMAL)); self.after(0, self.on_route_select)
    def run_cleanup(self):
        if not self.parser: return
        files_to_delete = list(self.parser.content_path.glob(f"**/*.{openrails_parser.APP_SUFFIX}.*.act"))
        if not files_to_delete: messagebox.showinfo("Cleanup", "No generated activity files found."); return
        if messagebox.askyesno("Confirm Deletion", f"Found {len(files_to_delete)} generated files. Permanently delete them?"):
            deleted_count = 0
            for f in files_to_delete:
                try: f.unlink(); deleted_count += 1
                except OSError as e: self.log(f"Could not delete {f.name}: {e}")
            messagebox.showinfo("Cleanup Complete", f"Deleted {deleted_count} file(s).")
            selections = self.route_listbox.curselection()
            if selections: self.on_route_select()
    def clear_info(self):
        self.generate_button.config(state=tk.DISABLED); self.historical_button.config(state=tk.DISABLED); self.found_coords = None; self.selected_activity_path = None; self.historical_selection = None
        self.desc_text.config(state=tk.NORMAL); self.desc_text.delete(1.0, tk.END); self.desc_text.config(state=tk.DISABLED)
        self.existing_weather_raw.config(state=tk.NORMAL); self.existing_weather_raw.delete(1.0, tk.END); self.existing_weather_raw.config(state=tk.DISABLED)
        for item in self.existing_weather_human.get_children(): self.existing_weather_human.delete(item)
        self.clear_weather_info("Select a route and activity.")
        self.chart_widget.clear_plot(); self.map_widget.delete_all_path(); self.map_widget.delete_all_marker(); self.weather_mode_label.config(text="Previewing: N/A"); self.current_weather_button.pack_forget()
    def clear_weather_info(self, message):
        self.forecast_text.config(state=tk.NORMAL); self.forecast_text.delete(1.0, tk.END); self.forecast_text.insert(tk.END, message); self.forecast_text.config(state=tk.DISABLED)

if __name__ == "__main__":
    if not TKCALENDAR_AVAILABLE:
        messagebox.showerror("Missing Library", "The 'tkcalendar' library is not installed.\n\nPlease open a command prompt and run:\npip install tkcalendar")
        sys.exit(1)
    app = MainApplication()
    app.mainloop()