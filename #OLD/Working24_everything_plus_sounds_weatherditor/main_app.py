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
from sound_manager import SoundManager
from ui_components import AboutWindow, ForecastChart, DateSelectionWindow, TKCALENDAR_AVAILABLE, SettingsWindow
from manual_editor import ManualWeatherEditor

try:
    from tkintermapview import TkinterMapView
except ImportError:
    messagebox.showerror("Missing Library", "The 'tkintermapview' library is not installed.\n\nPlease open a command prompt and run:\npip install tkintermapview")
    sys.exit(1)

class MainApplication(tk.Tk):
    def __init__(self):
        super().__init__()
        self.config = ConfigManager(); self.parser = None; self.weather = WeatherService()
        self.sound_manager = SoundManager(self._log_to_widget_from_thread)
        self.current_route_data = {}; self.current_activities = {}; self.selected_activity_path = None; self.found_coords = None
        self.historical_selection = None
        self.activity_details = {}
        self.title("ORTS WeatherLink"); self.geometry(self.config.get('window_geometry')); self.protocol("WM_DELETE_WINDOW", self.on_closing)
        sv_ttk.set_theme(self.config.get('theme'))
        
        self.option_add('*tearOff', tk.FALSE)
        menubar = tk.Menu(self)
        self.configure(menu=menubar)
        file_menu = tk.Menu(menubar)
        help_menu = tk.Menu(menubar)
        menubar.add_cascade(menu=file_menu, label="File")
        menubar.add_cascade(menu=help_menu, label="Help")
        file_menu.add_command(label="Settings...", command=self.show_settings_window)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.on_closing)
        help_menu.add_command(label="About...", command=self.show_about_window)

        self.setup_ui()
        self.log("[Info] Application startup complete.")
        self.post_ui_load()

    def setup_ui(self):
        top_frame = ttk.Frame(self, padding=(10, 10, 10, 0)); top_frame.pack(fill=tk.X, side=tk.TOP); top_frame.grid_columnconfigure(1, weight=1)
        ttk.Label(top_frame, text="Content Folder:").grid(row=0, column=0, sticky='w', padx=(0, 5))
        self.path_combo = ttk.Combobox(top_frame, values=self.config.get('content_paths')); self.path_combo.grid(row=0, column=1, sticky='ew')
        self.path_combo.bind("<<ComboboxSelected>>", self.on_path_selected)
        browse_button = ttk.Button(top_frame, text="Browse...", command=self.select_content_path); browse_button.grid(row=0, column=2, sticky='e', padx=(5, 10))
        self.theme_button = ttk.Button(top_frame, text="Toggle Theme", command=self.toggle_theme);

        main_paned = ttk.PanedWindow(self, orient=tk.HORIZONTAL); main_paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=(10,0))
        left_pane = ttk.PanedWindow(main_paned, orient=tk.VERTICAL); main_paned.add(left_pane, weight=1)

        route_frame = ttk.LabelFrame(left_pane, text="1. Select Route", padding=5)
        self.route_filter_var = tk.StringVar()
        self.route_filter_entry = ttk.Entry(route_frame, textvariable=self.route_filter_var)
        self.route_filter_entry.pack(fill=tk.X, padx=2, pady=2)
        self.route_filter_entry.bind("<KeyRelease>", self._filter_routes)
        self.route_scrollbar = ttk.Scrollbar(route_frame, orient=tk.VERTICAL)
        self.route_listbox = tk.Listbox(route_frame, exportselection=False, yscrollcommand=self.route_scrollbar.set); self.route_scrollbar.config(command=self.route_listbox.yview)
        self.route_scrollbar.pack(side=tk.RIGHT, fill=tk.Y); self.route_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.route_listbox.bind("<<ListboxSelect>>", self.on_route_select)
        left_pane.add(route_frame, weight=2)

        activity_frame = ttk.LabelFrame(left_pane, text="2. Select Activity", padding=5)
        self.activity_filter_var = tk.StringVar()
        self.activity_filter_entry = ttk.Entry(activity_frame, textvariable=self.activity_filter_var)
        self.activity_filter_entry.pack(fill=tk.X, padx=2, pady=2)
        self.activity_filter_entry.bind("<KeyRelease>", self._filter_activities)
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
        self.map_widget.add_right_click_menu_command(label="Get weather for this location", command=self.on_map_right_click, pass_coords=True)
        self.scout_marker = None
        map_actions_pane.add(map_frame, weight=2)

        action_frame = ttk.Frame(map_actions_pane, padding=10)
        self.weather_mode_label = ttk.Label(action_frame, text="Previewing: N/A", font=("", 9, "italic")); self.weather_mode_label.pack(fill=tk.X, pady=(0,10))
        
        self.preset_menu_var = tk.StringVar()
        preset_options = ["Developing Thunderstorm", "Gradual Clearing", "Passing Snow Showers"]
        self.preset_menu = ttk.OptionMenu(action_frame, self.preset_menu_var, "Select a preset...", *preset_options, command=self.on_preset_selected)
        
        self.generate_button = ttk.Button(action_frame, text="Generate Activity File", state=tk.DISABLED, command=self.run_generation_thread); self.generate_button.pack(fill=tk.X, pady=5)
        self.historical_button = ttk.Button(action_frame, text="Select Historical Date...", state=tk.DISABLED, command=self.select_historical_date); self.historical_button.pack(fill=tk.X, pady=5)
        self.current_weather_button = ttk.Button(action_frame, text="Load Current Weather", command=self.load_current_weather_action)
        ttk.Button(action_frame, text="Manual Weather Editor...", command=self.show_manual_editor).pack(fill=tk.X, pady=5)
        
        self.force_snow_var = tk.BooleanVar(value=True)
        self.force_snow_check = ttk.Checkbutton(action_frame, text="Force Snow in Winter", variable=self.force_snow_var); self.force_snow_check.pack(fill=tk.X, pady=5)
        
        self.add_thunder_var = tk.BooleanVar(value=True)
        self.add_thunder_check = ttk.Checkbutton(action_frame, text="Add Thunder Sounds in Storms", variable=self.add_thunder_var); self.add_thunder_check.pack(fill=tk.X, pady=5)
        
        self.add_rain_var = tk.BooleanVar(value=True)
        self.add_rain_check = ttk.Checkbutton(action_frame, text="Add Rain Sounds", variable=self.add_rain_var); self.add_rain_check.pack(fill=tk.X, pady=5)

        self.add_wind_var = tk.BooleanVar(value=True)
        self.add_wind_check = ttk.Checkbutton(action_frame, text="Add Wind & Blizzard Sounds", variable=self.add_wind_var); self.add_wind_check.pack(fill=tk.X, pady=5)
        
        self.route_cleanup_button = ttk.Button(action_frame, text="Clean Added Files from This Route", command=self.run_route_cleanup, state=tk.DISABLED)
        self.route_cleanup_button.pack(fill=tk.X, pady=5)
        map_actions_pane.add(action_frame, weight=1)

        status_frame = ttk.Frame(self, padding=(10,5,10,5)); status_frame.pack(fill=tk.X, side=tk.BOTTOM)
        self.status_label = ttk.Label(status_frame, text="Ready"); self.status_label.pack(side=tk.LEFT)
        self.progress_bar = ttk.Progressbar(status_frame, mode='indeterminate'); self.progress_bar.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(10,0))

    def _log_to_widget_from_thread(self, message):
        self.after(0, self._log_to_widget, message)
        
    def log(self, message): self.after(0, self._log_to_widget, message)
    def _log_to_widget(self, message): self.log_text.config(state=tk.NORMAL); self.log_text.insert(tk.END, message + "\n"); self.log_text.see(tk.END); self.log_text.config(state=tk.DISABLED)
    def on_closing(self): self.log("[Info] Closing application..."); self.config.set('window_geometry', self.geometry()); self.destroy()
    def show_about_window(self): AboutWindow(self)
    def show_settings_window(self): SettingsWindow(self, self.config)
    
    def show_manual_editor(self):
        if not self.selected_activity_path:
            messagebox.showwarning("Warning", "Please select an activity first to use as a base.")
            return
        # --- FIX: Pass the required initial_season argument ---
        dialog = ManualWeatherEditor(self, self.parser, self.sound_manager, self.selected_activity_path, self.activity_details.get('start_time', 0), self.activity_details.get('season', 1))
        self.wait_window(dialog)
        if dialog.generation_successful:
            self.log("[Info] Manual weather activity created. Refreshing activity list.")
            self.on_route_select()

    def toggle_theme(self): 
        new_theme = 'dark' if self.config.get('theme') == 'light' else 'light'
        sv_ttk.set_theme(new_theme)
        self.config.set('theme', new_theme)
        self.chart_widget.update_theme()
        
    def start_loading(self, message): self.log(f"[Busy] {message}"); self.status_label.config(text=message); self.progress_bar.start(10)
    def stop_loading(self): self.log("[Ready] Operation complete."); self.status_label.config(text="Ready"); self.progress_bar.stop(); self.progress_bar.pack_forget(); self.progress_bar.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(10,0))
    def post_ui_load(self):
        last_path = self.config.get('last_content_path')
        self.log(f"[Debug] Last content path from config: {last_path}")
        if last_path and Path(last_path).is_dir(): self.path_combo.set(last_path); self.load_content_folder(last_path)
        else: self.auto_detect_path()
        
    def select_content_path(self):
        path = filedialog.askdirectory(title="Select Open Rails 'Content' Folder")
        if path and Path(path).is_dir():
            self.log(f"[Info] User selected new content path: {path}")
            self.config.add_content_path(path); self.path_combo['values'] = self.config.get('content_paths'); self.path_combo.set(path); self.load_content_folder(path)
            
    def on_path_selected(self, event=None): self.load_content_folder(self.path_combo.get())
    def load_content_folder(self, path):
        self.log(f"[Info] Loading content folder: {path}")
        if not path or not Path(path).is_dir(): self.log("[ERROR] Invalid path provided."); return
        self.config.set('last_content_path', path); self.parser = openrails_parser.OpenRailsParser(path, self.log); self.populate_routes()
        
    def auto_detect_path(self):
        self.log("[Debug] Auto-detecting content path...")
        for p_str in [str(Path.home() / "Documents" / d / "Content") for d in ["Open Rails", "OpenRails"]]:
            p = Path(p_str)
            if p.is_dir() and (p / "ROUTES").is_dir():
                self.log(f"[Info] Auto-detected path: {p_str}")
                self.config.add_content_path(p_str); self.path_combo['values'] = self.config.get('content_paths'); self.path_combo.set(p_str); self.load_content_folder(p_str); return
        self.log("[Warning] Auto-detection failed. Please select a path manually.")
                
    def populate_routes(self):
        self.route_listbox.delete(0, tk.END); self.activity_listbox.delete(0, tk.END); self.clear_info()
        self.route_filter_var.set("")
        self.current_route_data = self.parser.get_all_routes()
        self._all_routes_sorted = sorted(self.current_route_data.keys())
        for name in self._all_routes_sorted: self.route_listbox.insert(tk.END, name)

    def _filter_routes(self, event=None):
        filter_text = self.route_filter_var.get().lower()
        self.route_listbox.delete(0, tk.END)
        for name in self._all_routes_sorted:
            if filter_text in name.lower():
                self.route_listbox.insert(tk.END, name)

    def on_route_select(self, event=None):
        selections = self.route_listbox.curselection()
        if not selections:
            self.route_cleanup_button.config(state=tk.DISABLED)
            return
        self.activity_listbox.delete(0, tk.END); self.clear_info()
        selected_route_name = self.route_listbox.get(selections[0])
        self.log(f"[Info] User selected route: '{selected_route_name}'")
        route_info = self.current_route_data.get(selected_route_name)
        if route_info:
            self.log(f"[Debug] Route path: {route_info['path']}")
            self.route_cleanup_button.config(state=tk.NORMAL)
            threading.Thread(target=self.load_activities_for_route, args=(route_info,), daemon=True).start()
        
    def load_activities_for_route(self, route_info):
        self.after(0, self.start_loading, f"Loading activities for {route_info['id']}..."); self.parser.load_track_nodes_for_route(route_info['trk_path']); self.current_activities = self.parser.get_activities_for_route(route_info['path']); self.after(0, self._populate_activities_list); self.after(0, self.stop_loading)
        
    def _populate_activities_list(self):
        self.activity_listbox.delete(0, tk.END)
        self.activity_filter_var.set("")
        self._all_activities_sorted = sorted(self.current_activities.items())
        for i, (act_file, act_data) in enumerate(self._all_activities_sorted):
            display_text = f"{act_data['display_name']} ({act_file})"
            self.activity_listbox.insert(tk.END, display_text)
            if act_data.get('has_weather'): self.activity_listbox.itemconfig(i, {'bg': '#502020'} if sv_ttk.get_theme() == 'dark' else '#FFDDDD')

    def _filter_activities(self, event=None):
        filter_text = self.activity_filter_var.get().lower()
        self.activity_listbox.delete(0, tk.END)
        for i, (act_file, act_data) in enumerate(self._all_activities_sorted):
            display_text = f"{act_data['display_name']} ({act_file})"
            if filter_text in display_text.lower():
                self.activity_listbox.insert(tk.END, display_text)
                if act_data.get('has_weather'):
                    new_index = self.activity_listbox.get(0, "end").index(display_text)
                    self.activity_listbox.itemconfig(new_index, {'bg': '#502020'} if sv_ttk.get_theme() == 'dark' else '#FFDDDD')
                    
    def on_activity_select(self, event=None):
        selections = self.activity_listbox.curselection()
        if not selections: return
        self.start_loading("Loading activity details...")
        selected_display = self.activity_listbox.get(selections[0])
        self.log(f"[Info] User selected activity: '{selected_display}'")
        for act_data in self.current_activities.values():
            if f"{act_data['display_name']} ({Path(act_data['path']).name})" == selected_display:
                self.selected_activity_path = act_data['path']; threading.Thread(target=self.update_activity_info, daemon=True).start(); break
                
    def update_activity_info(self, scout_coords=None):
        if scout_coords:
            lat, lon = scout_coords
            self.found_coords = (lat, lon)
            self.update_weather_info(lat, lon)
            self.after(0, self.stop_loading)
            return

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
        if self.scout_marker: self.scout_marker.delete()
        if len(path_coords) >= 2:
            path = self.map_widget.set_path(path_coords, color="crimson", width=7)
            self.map_widget.set_marker(path_coords[0][0], path_coords[0][1], text="Start", text_color="white", marker_color_circle="#229922", marker_color_outside="darkgreen")
            self.map_widget.set_marker(path_coords[-1][0], path_coords[-1][1], text="End", text_color="white", marker_color_circle="#C70039", marker_color_outside="darkred")
            min_lat = min(p[0] for p in path_coords)
            max_lat = max(p[0] for p in path_coords)
            min_lon = min(p[1] for p in path_coords)
            max_lon = max(p[1] for p in path_coords)
            self.map_widget.fit_bounding_box((max_lat, min_lon), (min_lat, max_lon))
        elif len(path_coords) == 1:
            self.map_widget.set_marker(path_coords[0][0], path_coords[0][1], text="Single Point"); self.map_widget.set_position(path_coords[0][0], path_coords[0][1], zoom=10)
            
    def _update_map_with_start_point(self, lat, lon):
        self.map_widget.delete_all_path(); self.map_widget.delete_all_marker()
        if self.scout_marker: self.scout_marker.delete()
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
        self.existing_weather_human.insert('', 'end', values=("─" * 25, "─" * 25))
        for event_index, event_block in enumerate(details['existing_weather']):
            time_match = re.search(r'Time\s*\(\s*(\d+)\s*\)', event_block)
            time_val = int(time_match.group(1)) if time_match else 'N/A'
            name_match = re.search(r'Name\s*\(\s*([^)]+)\s*\)', event_block)
            event_name = name_match.group(1).strip() if name_match else f'Weather Event #{event_index + 1}'
            def get_orts_param(name):
                pattern = fr'{name}\s*\(\s*([\d\.-]+)(?:\s+([\d\.-]+))?\s*\)'
                match = re.search(pattern, event_block, re.IGNORECASE)
                if match: return match.group(1), (match.group(2) if match.group(2) else None)
                return None, None
            overcast, overcast_duration = get_orts_param('ORTSOvercast')
            fog, fog_duration = get_orts_param('ORTSFog')
            precip, precip_duration = get_orts_param('ORTSPrecipitationIntensity')
            liquid, liquid_duration = get_orts_param('ORTSPrecipitationLiquidity')
            if time_val != 'N/A':
                h, m, s = time_val // 3600, (time_val % 3600) // 60, time_val % 60
                self.existing_weather_human.insert('', 'end', values=(f"⏰ TIME: {h:02d}:{m:02d}:{s:02d}", f"{time_val}s"))
                self.existing_weather_human.insert('', 'end', values=(f"📝 EVENT: {event_name}", ""))
            if overcast: self.existing_weather_human.insert('', 'end', values=("☁️  Cloud Cover", f"{float(overcast) * 100:.0f}%" + (f" (transition: {overcast_duration}s)" if overcast_duration else "")))
            if fog: self.existing_weather_human.insert('', 'end', values=("👁️  Visibility", f"{float(fog) / 1000.0:.1f} km" + (f" (transition: {fog_duration}s)" if fog_duration else "")))
            if precip:
                precip_mm = float(precip) * 1000.0
                duration_text = f" (transition: {precip_duration}s)" if precip_duration else ""
                self.existing_weather_human.insert('', 'end', values=("🌧️  Precipitation", f"{precip_mm:.1f} mm/h{duration_text}" if precip_mm > 0 else f"None (0.0 mm/h){duration_text}"))
            if liquid:
                liquid_val = float(liquid)
                duration_text = f" (transition: {liquid_duration}s)" if liquid_duration else ""
                self.existing_weather_human.insert('', 'end', values=("🌧️/❄️ Precip. Type", (f"Rain ({liquid_val:.1f})" if liquid_val > 0.5 else f"Snow ({liquid_val:.1f})") + duration_text))
            if event_index < len(details['existing_weather']) - 1: self.existing_weather_human.insert('', 'end', values=("", ""))

    def update_weather_info(self, lat, lon, date_obj=None):
        self.log(f"[Info] Fetching weather for Lat: {lat:.4f}, Lon: {lon:.4f}" + (f" on Date: {date_obj.strftime('%Y-%m-%d')}" if date_obj else " for Live Weather"))
        self.start_loading("Fetching weather data..."); self.historical_selection = {'date': date_obj} if date_obj else None
        data = self.weather.get_weather_data(lat, lon, date_obj); self.after(0, lambda: self._update_weather_widgets(data, date_obj)); self.stop_loading()
        
    def _update_weather_widgets(self, data, date_obj):
        if not data: self.log("[ERROR] Failed to fetch or parse weather data."); self.clear_weather_info("Failed to fetch weather data."); return
        self.generate_button.config(state=tk.NORMAL); self.historical_button.config(state=tk.NORMAL if TKCALENDAR_AVAILABLE else tk.DISABLED)
        self.preset_menu.pack_forget()
        if self.historical_selection:
            date_str = self.historical_selection['date'].strftime('%Y-%m-%d'); self.weather_mode_label.config(text=f"Preview: Historical ({date_str})"); self.current_weather_button.pack(fill=tk.X, pady=5); self.generate_button.config(text="Generate Historical Activity")
        else:
            self.weather_mode_label.config(text="Previewing: Live Weather"); self.current_weather_button.pack_forget(); self.generate_button.config(text="Generate Live Weather Activity")
        hourly = data.get("hourly", {}); header = f"{'Time':<8}{'Temp':<8}{'Precip':<10}{'Clouds':<10}{'Wind':<15}{'View':<10}{'Condition'}\n"; 
        self.forecast_text.config(state=tk.NORMAL); self.forecast_text.delete(1.0, tk.END); self.forecast_text.insert(tk.END, header + "-"*(len(header)+10) + "\n")
        def deg_to_dir(deg): dirs = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]; return dirs[int((deg + 11.25) / 22.5) % 16] if deg is not None else "N/A"
        for i in range(min(24, len(hourly.get('time', [])))):
            temp = f"{hourly['temperature_2m'][i]:.1f}°C" if 'temperature_2m' in hourly and hourly['temperature_2m'][i] is not None else "N/A"
            precip = f"{hourly['precipitation'][i]:.1f}mm" if 'precipitation' in hourly and hourly['precipitation'][i] is not None else "N/A"
            clouds = f"{hourly['cloudcover'][i]}%" if 'cloudcover' in hourly and hourly['cloudcover'][i] is not None else "N/A"
            wind_s = hourly['windspeed_10m'][i] if 'windspeed_10m' in hourly else None; wind_d = hourly['winddirection_10m'][i] if 'winddirection_10m' in hourly else None; wind = f"{wind_s:.1f}km/h {deg_to_dir(wind_d)}" if wind_s is not None else "N/A"
            vis = f"{hourly['visibility'][i]/1000:.1f}km" if 'visibility' in hourly and hourly['visibility'][i] is not None else "N/A"
            cond = self.weather.WMO_CODES.get(hourly['weathercode'][i], 'N/A') if 'weathercode' in hourly and hourly['weathercode'][i] is not None else "N/A"
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
        self.preset_menu.pack_forget()
        self.preset_menu_var.set("Select a preset...")
        lat, lon = self.found_coords; threading.Thread(target=self.update_weather_info, args=(lat, lon), daemon=True).start()

    def on_preset_selected(self, preset_name):
        self.clear_weather_info(f"Selected preset: {preset_name}\n\nClick 'Generate Preset Activity' to apply this weather scenario.")
        self.chart_widget.clear_plot()
        self.historical_selection = None
        self.weather_mode_label.config(text=f"Preview: Preset ({preset_name})")
        self.generate_button.config(text="Generate Preset Activity", state=tk.NORMAL)
        self.current_weather_button.pack(fill=tk.X, pady=5)
        self.historical_button.config(state=tk.DISABLED)

    def on_map_right_click(self, coords):
        self.start_loading(f"Scouting weather at {coords[0]:.4f}, {coords[1]:.4f}...")
        self.weather_mode_label.config(text=f"Preview: Scouting Location")
        if self.scout_marker: self.scout_marker.delete()
        self.scout_marker = self.map_widget.set_marker(coords[0], coords[1], text="Scout Location", marker_color_circle="cyan", marker_color_outside="darkcyan")
        threading.Thread(target=self.update_activity_info, args=(coords,), daemon=True).start()

    def run_generation_thread(self, chaotic=False, preset=None, manual_events=None): 
        self.log("[Debug] Generation thread started.")
        threading.Thread(target=self.generate_weather_worker, args=(chaotic, self.preset_menu_var.get(), manual_events), daemon=True).start()
        
    def run_chaotic_generation(self):
        if not self.selected_activity_path: messagebox.showwarning("Warning", "Please select an activity first."); return
        self.log("[Info] User triggered Chaotic Weather generation.")
        self.run_generation_thread(chaotic=True)
        
    def generate_weather_worker(self, chaotic=False, preset_name=None, manual_events=None):
        self.after(0, self.start_loading, "Generating new activity file...")
        if not self.selected_activity_path: self.log("[ERROR] Generation failed: No activity selected."); self.after(0, self.stop_loading); return
        lat, lon = self.found_coords
        if lat is None and not (manual_events or chaotic or (preset_name and preset_name != "Select a preset...")): 
            self.log("[ERROR] Generation failed: Coordinates not found."); self.after(0, self.stop_loading); self.after(0, lambda: self.generate_button.config(state=tk.NORMAL)); return
        
        self.sound_manager.copied_sounds.clear()
        selected_route_name = self.route_listbox.get(self.route_listbox.curselection()[0])
        route_path = self.current_route_data.get(selected_route_name)['path']

        date_obj = None
        weather_events, msg = None, None
        is_manual = False

        if manual_events:
            self.log("[Debug] Mode: Manual Weather")
            weather_events = manual_events
            msg = "Manual weather events prepared."
            is_manual = True
        elif chaotic:
            self.log("[Debug] Mode: Chaotic Weather")
            weather_events, msg = self.weather.create_chaotic_weather_events(self.sound_manager, route_path)
        elif preset_name and preset_name != "Select a preset...":
            self.log(f"[Debug] Mode: Preset Weather ('{preset_name}')")
            weather_events, msg = self.weather.create_preset_weather_events(preset_name)
        else:
            self.log("[Debug] Mode: Live/Historical Weather")
            date_obj = self.historical_selection['date'] if self.historical_selection else None
            start_hour = self.historical_selection['hour'] if self.historical_selection else 0
            season = self.activity_details.get('season', 1)
            force_snow = self.force_snow_var.get()
            add_thunder = self.add_thunder_var.get()
            add_wind = self.add_wind_var.get()
            add_rain = self.add_rain_var.get()
            weather_events, msg = self.weather.create_weather_events_string(lat, lon, season, force_snow, date_obj, start_hour, add_thunder, add_wind, add_rain, self.sound_manager, route_path)
            
        if not weather_events: self.log(f"[ERROR] Weather event string creation failed: {msg}"); self.after(0, self.stop_loading); self.after(0, lambda: self.generate_button.config(state=tk.NORMAL)); return
        self.log(f"[Info] {msg}")
        
        new_path, msg = self.parser.modify_and_save_activity(self.selected_activity_path, weather_events, date_obj, chaotic, manual_suffix="MANUAL" if is_manual else None)
        if new_path:
            self.log(f"[Success] {msg}\n  > Saved to: {Path(new_path).name}\n\n--- Generation Complete! ---")
            self.after(0, lambda: messagebox.showinfo("Success", f"New activity file created:\n\n{Path(new_path).name}"))
        else:
            self.log(f"[ERROR] CRITICAL: Failed to save new activity file: {msg}")
            
        self.after(0, self.stop_loading); self.after(0, lambda: self.generate_button.config(state=tk.NORMAL)); self.after(0, self.on_route_select)
        
    def run_route_cleanup(self):
        selections = self.route_listbox.curselection()
        if not self.parser or not selections: return
        
        selected_route_name = self.route_listbox.get(selections[0])
        route_path = self.current_route_data.get(selected_route_name)['path']

        msg = (f"This will permanently delete all generated files:\n" f"  - *.WTHLINK.*.act\n" f"  - WEATHERLINK_*.wav\n\n" f"from the route '{selected_route_name}' and its subfolders.\n\n" f"Are you sure you want to continue?")
        
        if messagebox.askyesno("Confirm Route Cleanup", msg, icon='warning'):
            self.log(f"[Info] User initiated cleanup for route: '{selected_route_name}'")
            self.start_loading(f"Cleaning files for route '{selected_route_name}'...")
            acts, sounds = self.parser.cleanup_generated_files(route_path)
            self.stop_loading()
            messagebox.showinfo("Cleanup Complete", f"Deleted {acts} activity file(s) and {sounds} sound file(s) from this route.")
            self.on_route_select()

    def run_global_cleanup(self):
        if not self.config.get('content_paths'): 
            messagebox.showwarning("Warning", "No Content Folders configured in Settings.")
            return

        msg = (f"This will scan ALL configured content folders and permanently delete ALL generated files:\n" f"  - *.WTHLINK.*.act\n" f"  - WEATHERLINK_*.wav\n\n" f"This action cannot be undone. Are you absolutely sure?")

        if messagebox.askyesno("Confirm GLOBAL Cleanup", msg, icon='warning'):
            self.log("[Info] User initiated GLOBAL cleanup.")
            self.start_loading("Performing global cleanup...")
            total_acts, total_sounds = 0, 0
            for path in self.config.get('content_paths'):
                temp_parser = openrails_parser.OpenRailsParser(path, self.log)
                acts, sounds = temp_parser.cleanup_generated_files(path)
                total_acts += acts
                total_sounds += sounds
            self.stop_loading()
            messagebox.showinfo("Global Cleanup Complete", f"Deleted {total_acts} activity file(s) and {total_sounds} sound file(s) from all content folders.")
            if self.route_listbox.curselection():
                self.on_route_select()

    def clear_info(self):
        self.generate_button.config(state=tk.DISABLED); self.historical_button.config(state=tk.DISABLED); self.found_coords = None; self.selected_activity_path = None; self.historical_selection = None
        self.desc_text.config(state=tk.NORMAL); self.desc_text.delete(1.0, tk.END); self.desc_text.config(state=tk.DISABLED)
        self.existing_weather_raw.config(state=tk.NORMAL); self.existing_weather_raw.delete(1.0, tk.END); self.existing_weather_raw.config(state=tk.DISABLED)
        for item in self.existing_weather_human.get_children(): self.existing_weather_human.delete(item)
        self.clear_weather_info("Select a route and activity.")
        self.chart_widget.clear_plot(); self.map_widget.delete_all_path(); self.map_widget.delete_all_marker()
        if self.scout_marker: self.scout_marker.delete(); self.scout_marker = None
        self.weather_mode_label.config(text="Previewing: N/A"); self.current_weather_button.pack_forget()
        self.preset_menu.pack_forget()
        self.preset_menu_var.set("Select a preset...")
        self.route_cleanup_button.config(state=tk.DISABLED)

    def clear_weather_info(self, message):
        self.forecast_text.config(state=tk.NORMAL); self.forecast_text.delete(1.0, tk.END); self.forecast_text.insert(tk.END, message); self.forecast_text.config(state=tk.DISABLED)

if __name__ == "__main__":
    if not TKCALENDAR_AVAILABLE:
        messagebox.showerror("Missing Library", "The 'tkcalendar' library is not installed.\n\nPlease open a command prompt and run:\npip install tkcalendar")
        sys.exit(1)
    app = MainApplication()
    app.mainloop()