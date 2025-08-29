# main_app.py
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import threading
from pathlib import Path
import sv_ttk
import sys
import re
from datetime import datetime
import json
import traceback

try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

from config_manager import ConfigManager
import openrails_parser
from weather_service import WeatherService
from sound_manager import SoundManager
from ui_components import AboutWindow, ForecastChart, DateSelectionWindow, TKCALENDAR_AVAILABLE, SettingsWindow, Tooltip, StartupInfoWindow
from manual_editor import ManualWeatherEditor

try:
    from tkintermapview import TkinterMapView
except ImportError:
    messagebox.showerror("Missing Library", "The 'tkintermapview' library is not installed.\n\nPlease open a command prompt and run:\npip install tkintermapview")
    sys.exit(1)

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = Path(sys._MEIPASS)
    except Exception:
        base_path = Path(__file__).parent.resolve()
    return base_path / relative_path

class MainApplication(tk.Tk):
    def __init__(self):
        super().__init__()
        self.config = ConfigManager()
        self.parser = None
        self.shutdown_event = threading.Event()
        self.weather = WeatherService(self._log_to_widget_from_thread)
        self.sound_manager = SoundManager(self._log_to_widget_from_thread)
        self.current_route_data = {}
        self.current_activities = {}
        self.selected_activity_path = None
        self.found_coords = None
        self.historical_selection = None
        self.activity_details = {}
        self.weather_point_markers = []
        self.raw_forecast_list = []
        self.weather_fetch_points = []
        self.path_dist = 0
        self.title("ORTS WeatherLink")
        self.geometry(self.config.get('window_geometry'))
        self.logo_original_img = None
        self.logo_label = None
        
        if PIL_AVAILABLE:
            icon_path = resource_path("icon1.png")
            if icon_path.exists():
                self.icon_image = tk.PhotoImage(file=icon_path)
                self.iconphoto(True, self.icon_image)

        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        sv_ttk.set_theme(self.config.get('theme'))
        
        self.option_add('*tearOff', tk.FALSE)
        menubar = tk.Menu(self)
        self.configure(menu=menubar)
        file_menu = tk.Menu(menubar)
        help_menu = tk.Menu(menubar)
        menubar.add_cascade(menu=file_menu, label="File")
        menubar.add_cascade(menu=help_menu, label="Help")
        file_menu.add_command(label="Refresh Route List", command=self.refresh_routes)
        file_menu.add_command(label="Settings...", command=self.show_settings_window)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.on_closing)
        help_menu.add_command(label="About...", command=self.show_about_window)
        help_menu.add_separator()
        help_menu.add_command(label="Show Debug Info", command=self.show_debug_info)

        self.setup_ui()
        self.log("[Info] Application startup complete.")
        self.post_ui_load()

    def setup_ui(self):
        top_frame = ttk.Frame(self, padding=(10, 10, 10, 0)); top_frame.pack(fill=tk.X, side=tk.TOP); top_frame.grid_columnconfigure(1, weight=1)
        ttk.Label(top_frame, text="Content Folder:").grid(row=0, column=0, sticky='w', padx=(0, 5))
        self.path_combo = ttk.Combobox(top_frame, values=self.config.get('content_paths')); self.path_combo.grid(row=0, column=1, sticky='ew')
        browse_button = ttk.Button(top_frame, text="Browse...", command=self.select_content_path); browse_button.grid(row=0, column=2, sticky='e', padx=(5, 10))
        self.theme_button = ttk.Button(top_frame, text="Toggle Theme", command=self.toggle_theme);

        main_paned = ttk.PanedWindow(self, orient=tk.HORIZONTAL); main_paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=(10,0))
        left_pane = ttk.PanedWindow(main_paned, orient=tk.VERTICAL); main_paned.add(left_pane, weight=1)

        route_frame = ttk.LabelFrame(left_pane, text="1. Select Route", padding=5)
        self.route_filter_var = tk.StringVar()
        self.route_filter_entry = ttk.Entry(route_frame, textvariable=self.route_filter_var)
        self.route_filter_entry.pack(fill=tk.X, padx=2, pady=2)
        self.route_scrollbar = ttk.Scrollbar(route_frame, orient=tk.VERTICAL)
        self.route_listbox = tk.Listbox(route_frame, exportselection=False, yscrollcommand=self.route_scrollbar.set); self.route_scrollbar.config(command=self.route_listbox.yview)
        self.route_scrollbar.pack(side=tk.RIGHT, fill=tk.Y); self.route_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        left_pane.add(route_frame, weight=2)

        activity_frame = ttk.LabelFrame(left_pane, text="2. Select Activity", padding=5)
        self.activity_filter_var = tk.StringVar()
        self.activity_filter_entry = ttk.Entry(activity_frame, textvariable=self.activity_filter_var)
        self.activity_filter_entry.pack(fill=tk.X, padx=2, pady=2)
        self.activity_scrollbar = ttk.Scrollbar(activity_frame, orient=tk.VERTICAL)
        self.activity_listbox = tk.Listbox(activity_frame, exportselection=False, yscrollcommand=self.activity_scrollbar.set); self.activity_scrollbar.config(command=self.activity_listbox.yview)
        self.activity_scrollbar.pack(side=tk.RIGHT, fill=tk.Y); self.activity_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        left_pane.add(activity_frame, weight=3)
        
        # --- Add Bindings ---
        self.path_combo.bind("<<ComboboxSelected>>", self.on_path_selected)
        self.path_combo.bind("<Return>", self.on_path_selected)
        self.route_filter_entry.bind("<KeyRelease>", self._filter_routes)
        self.route_listbox.bind("<<ListboxSelect>>", self.on_route_select)
        self.activity_filter_entry.bind("<KeyRelease>", self._filter_activities)
        self.activity_listbox.bind("<<ListboxSelect>>", self.on_activity_select)

        right_pane = ttk.PanedWindow(main_paned, orient=tk.HORIZONTAL); main_paned.add(right_pane, weight=3)
        
        content_pane = ttk.PanedWindow(right_pane, orient=tk.VERTICAL); right_pane.add(content_pane, weight=3)

        details_notebook = ttk.Notebook(content_pane); content_pane.add(details_notebook, weight=2)
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
        chaotic_button = ttk.Button(log_frame_tab, text="Generate Chaotic Weather (for testing)", command=self.run_chaotic_generation); chaotic_button.pack(fill=tk.X, pady=5)
        details_notebook.add(log_frame_tab, text="Debug Console")

        map_frame = ttk.LabelFrame(content_pane, text="Activity Path", padding=5); content_pane.add(map_frame, weight=3)
        self.map_widget = TkinterMapView(map_frame, corner_radius=0); self.map_widget.pack(fill=tk.BOTH, expand=True)
        self.scout_marker = None

        scroll_container = ttk.Frame(right_pane); scroll_container.grid_rowconfigure(0, weight=1); scroll_container.grid_columnconfigure(0, weight=1)
        canvas = tk.Canvas(scroll_container, highlightthickness=0); scrollbar = ttk.Scrollbar(scroll_container, orient="vertical", command=canvas.yview); canvas.configure(yscrollcommand=scrollbar.set)
        action_frame = ttk.Frame(canvas, padding=10)
        canvas_frame = canvas.create_window((0, 0), window=action_frame, anchor="nw")
        def on_frame_configure(event): canvas.configure(scrollregion=canvas.bbox("all"))
        action_frame.bind("<Configure>", on_frame_configure)
        def on_canvas_configure(event):
            canvas.itemconfig(canvas_frame, width=event.width)
            self.resize_logo(event)
        canvas.bind("<Configure>", on_canvas_configure)
        canvas.grid(row=0, column=0, sticky="nsew"); scrollbar.grid(row=0, column=1, sticky="ns")
        right_pane.add(scroll_container, weight=1)

        self.weather_mode_label = ttk.Label(action_frame, text="Previewing: N/A", font=("", 9, "italic")); self.weather_mode_label.pack(fill=tk.X, pady=(0,10))
        
        self.generate_live_button = ttk.Button(action_frame, text="Generate Live Weather Activity", state=tk.DISABLED, command=lambda: self.run_generation_thread(historical=False)); self.generate_live_button.pack(fill=tk.X, pady=5)
        self.current_weather_button = ttk.Button(action_frame, text="Load Current Weather", state=tk.DISABLED, command=self.load_current_weather_action); self.current_weather_button.pack(fill=tk.X, pady=5)
        self.save_preset_button = ttk.Button(action_frame, text="Save Forecast as Preset...", command=self.save_forecast_as_preset)
        
        hist_frame = ttk.LabelFrame(action_frame, text="Historical & Other Sources", padding=10); hist_frame.pack(fill=tk.X, pady=5)
        self.historical_button = ttk.Button(hist_frame, text="Select Historical Date...", state=tk.DISABLED, command=self.select_historical_date); self.historical_button.pack(fill=tk.X, pady=5)
        self.generate_historical_button = ttk.Button(hist_frame, text="Generate from Historical Date", state=tk.DISABLED, command=lambda: self.run_generation_thread(historical=True)); self.generate_historical_button.pack(fill=tk.X, pady=5)
        self.metar_button = ttk.Button(hist_frame, text="Generate from METAR...", state=tk.DISABLED, command=self.run_metar_generation); self.metar_button.pack(fill=tk.X, pady=5)

        editor_frame = ttk.Frame(action_frame); editor_frame.pack(fill=tk.X, pady=5)
        manual_editor_button = ttk.Button(editor_frame, text="Manual Weather Editor...", command=self.show_manual_editor); manual_editor_button.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 5))
        self.edit_weather_button = ttk.Button(editor_frame, text="Load & Edit Weather File...", state=tk.DISABLED, command=self.load_and_edit_weather_file); self.edit_weather_button.pack(side=tk.LEFT, expand=True, fill=tk.X)
        self.add_thunder_var = tk.BooleanVar(value=True); self.add_thunder_check = ttk.Checkbutton(action_frame, text="Add Thunder Sounds in Storms", variable=self.add_thunder_var); self.add_thunder_check.pack(fill=tk.X, pady=5)
        self.add_rain_var = tk.BooleanVar(value=True); self.add_rain_check = ttk.Checkbutton(action_frame, text="Add Rain Sounds", variable=self.add_rain_var); self.add_rain_check.pack(fill=tk.X, pady=5)
        self.add_wind_var = tk.BooleanVar(value=True); self.add_wind_check = ttk.Checkbutton(action_frame, text="Add Wind & Blizzard Sounds", variable=self.add_wind_var); self.add_wind_check.pack(fill=tk.X, pady=5)
        self.route_cleanup_button = ttk.Button(action_frame, text="Clean Added Files from This Route", command=self.run_route_cleanup, state=tk.DISABLED); self.route_cleanup_button.pack(fill=tk.X, pady=5)
        
        ttk.Separator(action_frame, orient='horizontal').pack(fill='x', pady=10)

        if PIL_AVAILABLE:
            logo_path = resource_path("logo1.png")
            if logo_path.exists():
                self.logo_original_img = Image.open(logo_path)
                img = self.logo_original_img.copy()
                img.thumbnail((200, 200))
                self.logo_img = ImageTk.PhotoImage(img)
                self.logo_label = ttk.Label(action_frame, image=self.logo_img, cursor="hand2")
                self.logo_label.pack(pady=5)
                self.logo_label.bind("<Double-Button-1>", lambda e: self.show_about_window())

        status_frame = ttk.Frame(self, padding=(10,5,10,5)); status_frame.pack(fill=tk.X, side=tk.BOTTOM)
        self.status_label = ttk.Label(status_frame, text="Ready"); self.status_label.pack(side=tk.LEFT)
        self.progress_bar = ttk.Progressbar(status_frame, mode='indeterminate'); self.progress_bar.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(10,0))
        
        # --- Add Tooltips ---
        Tooltip(self.path_combo, "Select the main Open Rails 'Content' folder where your routes and activities are stored.")
        Tooltip(browse_button, "Browse for a 'Content' folder on your computer.")
        Tooltip(self.route_filter_entry, "Type here to filter the list of routes below.")
        Tooltip(self.route_listbox, "Lists all routes found in the selected Content folder. Click to select a route. Routes with existing WTHLINK files are highlighted.")
        Tooltip(self.activity_filter_entry, "Type here to filter the list of activities for the selected route.")
        Tooltip(self.activity_listbox, "Lists all activities for the selected route. Activities with existing weather are highlighted.")
        Tooltip(self.map_widget, "Displays the path of the selected activity. Right-click for more options.")
        Tooltip(self.generate_live_button, "Generates a new activity (.act) file with the fetched live weather data.")
        Tooltip(self.historical_button, "Select a past date and time to fetch historical weather data.")
        Tooltip(self.generate_historical_button, "Generates a new activity file based on the selected historical date.")
        Tooltip(self.metar_button, "Generate a static weather scenario based on a real-time airport METAR report.")
        Tooltip(self.current_weather_button, "Switch back to the current live weather forecast.")
        Tooltip(self.save_preset_button, "Save the current 24-hour forecast as a user preset for the Manual Editor.")
        Tooltip(manual_editor_button, "Open an editor to create a fully custom sequence of weather events.")
        Tooltip(self.edit_weather_button, "Load an existing WTHLINK activity file into the Manual Editor to make changes.")
        Tooltip(self.add_thunder_check, "If checked, thunder sounds will be added during thunderstorms.")
        Tooltip(self.add_rain_check, "If checked, ambient rain sounds will be added during precipitation.")
        Tooltip(self.add_wind_check, "If checked, ambient wind or blizzard sounds will be added based on conditions.")
        Tooltip(self.route_cleanup_button, "Permanently delete all files generated by this tool for the selected route.")
        Tooltip(chaotic_button, "Generates an activity with a series of random, rapid weather changes for testing purposes.")
        
        # Map right-click menu
        self.map_widget.add_right_click_menu_command(label="Get weather for this location", command=self.on_map_right_click, pass_coords=True)
        self.map_widget.add_right_click_menu_command(label="Switch to Satellite View", command=self.set_satellite_view, pass_coords=False)
        self.map_widget.add_right_click_menu_command(label="Switch to Normal View", command=self.set_normal_view, pass_coords=False)

    def set_satellite_view(self):
        self.map_widget.set_tile_server("https://mt0.google.com/vt/lyrs=s&hl=en&x={x}&y={y}&z={z}&s=Ga", max_zoom=22)
        self.log("[Info] Map view switched to Satellite.")

    def set_normal_view(self):
        self.map_widget.set_tile_server("https://a.tile.openstreetmap.org/{z}/{x}/{y}.png")
        self.log("[Info] Map view switched to Normal (OpenStreetMap).")

    def resize_logo(self, event):
        if self.logo_original_img is None or self.logo_label is None:
            return

        # action_frame has padding=10, so subtract 20 for left+right.
        new_width = event.width - 20
        if new_width < 20:
            return

        try:
            img = self.logo_original_img.copy()
            original_width, original_height = img.size

            # Let it shrink, but don't let it grow larger than 200px wide.
            if new_width > 200:
                new_width = 200
            
            aspect_ratio = original_height / float(original_width)
            new_height = int(new_width * aspect_ratio)

            if new_width <= 0 or new_height <= 0: return

            resized_img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            # This is important to prevent garbage collection
            self.logo_img = ImageTk.PhotoImage(resized_img)
            self.logo_label.config(image=self.logo_img)
        except Exception as e:
            self.log(f"[WARN] Could not resize logo: {e}")

    def show_debug_info(self):
        try:
            route_selection = self.route_listbox.curselection()
            selected_route_text = "None"
            if route_selection:
                selected_route_text = self.route_listbox.get(route_selection[0])
            
            info = (
                f"Selected Route: {selected_route_text}\n"
                f"Selected Activity: {Path(self.selected_activity_path).name if self.selected_activity_path else 'None'}\n"
                f"--------------------------------\n"
                f"Path Distance (m): {self.path_dist}\n"
                f"Path Coords Cached: {len(self.path_coords_cache) if hasattr(self, 'path_coords_cache') and self.path_coords_cache else 0}\n"
                f"Found Coords: {self.found_coords}\n"
                f"Historical Selection: {self.historical_selection}\n"
                f"--------------------------------\n"
                f"Weather Fetch Points: {len(self.weather_fetch_points)}\n"
                f"Raw Forecasts Fetched: {len(self.raw_forecast_list) if self.raw_forecast_list else 0}"
            )
            messagebox.showinfo("Debug Information", info, parent=self)
        except Exception as e:
            messagebox.showerror("Debug Error", f"Could not gather debug info:\n{e}", parent=self)

    def _log_to_widget_from_thread(self, message):
        if not self.shutdown_event.is_set():
            self.after(0, self._log_to_widget, message)
        
    def log(self, message):
        if not self.shutdown_event.is_set():
            self.after(0, self._log_to_widget, message)

    def _log_to_widget(self, message):
        try:
            self.log_text.config(state=tk.NORMAL); self.log_text.insert(tk.END, message + "\n"); self.log_text.see(tk.END); self.log_text.config(state=tk.DISABLED)
        except tk.TclError:
            pass # Main window was destroyed
            
    def on_closing(self):
        self.log("[Info] Closing application...")
        self.config.set('window_geometry', self.geometry())
        self.shutdown_event.set()
        self.map_widget.destroy()
        self.destroy()

    def show_about_window(self): AboutWindow(self)
    def show_settings_window(self): SettingsWindow(self, self.config)
    
    def show_manual_editor(self, initial_events=None):
        if not self.selected_activity_path:
            messagebox.showwarning("Warning", "Please select a base activity file first.")
            return
        dialog = ManualWeatherEditor(self, self.parser, self.sound_manager, self.selected_activity_path, self.activity_details.get('start_time', 0), self.activity_details.get('season', 1), initial_events)
        self.wait_window(dialog)
        if dialog.generation_successful:
            self.log("[Info] Manual weather activity created/updated. Refreshing activity list.")
            self.on_route_select()
            
    def load_and_edit_weather_file(self):
        if not self.selected_activity_path: return
        events = self.parser.parse_wthlink_activity(self.selected_activity_path)
        if events is not None:
            self.show_manual_editor(initial_events=events)
        else:
            messagebox.showerror("Error", "Could not parse weather events from the selected file. It might not contain any WTHLINK data.")

    def toggle_theme(self): 
        new_theme = 'dark' if self.config.get('theme') == 'light' else 'light'
        sv_ttk.set_theme(new_theme)
        self.config.set('theme', new_theme)
        self.chart_widget.update_theme()
        
    def start_loading(self, message): self.log(f"[Busy] {message}"); self.status_label.config(text=message); self.progress_bar.start(10)
    def stop_loading(self):
        if not self.shutdown_event.is_set():
            self.log("[Ready] Operation complete."); self.status_label.config(text="Ready"); self.progress_bar.stop(); self.progress_bar.pack_forget(); self.progress_bar.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(10,0))
    def post_ui_load(self):
        last_path = self.config.get('last_content_path')
        if last_path and Path(last_path).is_dir(): self.path_combo.set(last_path); self.load_content_folder(last_path)
        else: self.auto_detect_path()
        if self.config.get('show_startup_info'):
            info_window = StartupInfoWindow(self, self.config)
            self.wait_window(info_window)

    def select_content_path(self):
        path = filedialog.askdirectory(title="Select Open Rails 'Content' Folder")
        if path and Path(path).is_dir():
            self.log(f"[Info] User selected new content path: {path}")
            self.config.add_content_path(path); self.path_combo['values'] = self.config.get('content_paths'); self.path_combo.set(path); self.load_content_folder(path)
            
    def on_path_selected(self, event=None): self.load_content_folder(self.path_combo.get())
    
    def load_content_folder(self, path, use_cache=True):
        if not path or not Path(path).is_dir(): self.log("[ERROR] Invalid path provided."); return
        self.config.set('last_content_path', path)
        self.parser = openrails_parser.OpenRailsParser(path, self.log)
        
        use_cache = use_cache and self.config.get('use_route_cache')
        if use_cache:
            cached_data = self.load_routes_from_cache(path)
            if cached_data:
                self.log("[Info] Loaded route list from cache.")
                self.current_route_data = cached_data
                self.populate_routes(from_cache=True)
                return
        
        self.log("[Info] Scanning for routes... This may take a moment.")
        self.populate_routes()
        
    def refresh_routes(self):
        path = self.path_combo.get()
        if path:
            self.log("[Info] Forcing a refresh of the route list.")
            self.load_content_folder(path, use_cache=False)
        else:
            messagebox.showwarning("No Path", "Please select a content folder first.", parent=self)

    def auto_detect_path(self):
        for p_str in [str(Path.home() / "Documents" / d / "Content") for d in ["Open Rails", "OpenRails"]]:
            p = Path(p_str)
            if p.is_dir() and (p / "ROUTES").is_dir():
                self.log(f"[Info] Auto-detected path: {p_str}")
                self.config.add_content_path(p_str); self.path_combo['values'] = self.config.get('content_paths'); self.path_combo.set(p_str); self.load_content_folder(p_str); return
        self.log("[Warning] Auto-detection failed. Please select a path manually.")
                
    def populate_routes(self, from_cache=False):
        self.route_listbox.delete(0, tk.END); self.activity_listbox.delete(0, tk.END); self.clear_info()
        
        if not from_cache:
            self.current_route_data = self.parser.get_all_routes()
            self.save_routes_to_cache(self.path_combo.get(), self.current_route_data)

        self._all_routes_sorted = sorted(self.current_route_data.keys())
        for i, name in enumerate(self._all_routes_sorted):
            self.route_listbox.insert(tk.END, name)
            route_info = self.current_route_data.get(name)
            if route_info and self.parser.route_has_generated_files(route_info['path']):
                self.route_listbox.itemconfig(i, {'bg': '#204020' if sv_ttk.get_theme() == 'dark' else '#DDFFDD'})

    def _filter_routes(self, event=None):
        filter_text = self.route_filter_var.get().lower()
        self.route_listbox.delete(0, tk.END)
        for i, name in enumerate(self._all_routes_sorted):
            if filter_text in name.lower():
                self.route_listbox.insert(tk.END, name)
                route_info = self.current_route_data.get(name)
                if route_info and self.parser.route_has_generated_files(route_info['path']):
                    new_index = self.route_listbox.get(0, "end").index(name)
                    self.route_listbox.itemconfig(new_index, {'bg': '#204020' if sv_ttk.get_theme() == 'dark' else '#DDFFDD'})

    def on_route_select(self, event=None):
        selections = self.route_listbox.curselection()
        if not selections: self.route_cleanup_button.config(state=tk.DISABLED); return
        self.activity_listbox.delete(0, tk.END); self.clear_info()
        selected_route_name = self.route_listbox.get(selections[0])
        route_info = self.current_route_data.get(selected_route_name)
        if route_info:
            self.route_cleanup_button.config(state=tk.NORMAL)
            threading.Thread(target=self.load_activities_for_route, args=(route_info,), daemon=True).start()
        
    def load_activities_for_route(self, route_info):
        try:
            if self.shutdown_event.is_set(): return
            self.after(0, self.start_loading, f"Loading activities for {route_info['id']}...")
            self.current_activities = self.parser.get_activities_for_route(route_info['path'])
            if not self.shutdown_event.is_set(): self.after(0, self._populate_activities_list)
            if not self.shutdown_event.is_set(): self.after(0, self.stop_loading)
        except Exception as e:
            self.log(f"[CRITICAL] Unhandled exception in load_activities_for_route thread: {e}")
            self.log(traceback.format_exc())
            if not self.shutdown_event.is_set(): self.after(0, self.stop_loading)
        
    def _populate_activities_list(self):
        self.activity_listbox.delete(0, tk.END)
        self.activity_filter_var.set("")
        self._all_activities_sorted = sorted(self.current_activities.items())
        for i, (act_file, act_data) in enumerate(self._all_activities_sorted):
            display_text = f"{act_data['display_name']} ({act_file})"
            self.activity_listbox.insert(tk.END, display_text)
            if act_data.get('has_weather'): self.activity_listbox.itemconfig(i, {'bg': '#502020' if sv_ttk.get_theme() == 'dark' else '#FFDDDD'})

    def _filter_activities(self, event=None):
        filter_text = self.activity_filter_var.get().lower()
        self.activity_listbox.delete(0, tk.END)
        for i, (act_file, act_data) in enumerate(self._all_activities_sorted):
            display_text = f"{act_data['display_name']} ({act_file})"
            if filter_text in display_text.lower():
                self.activity_listbox.insert(tk.END, display_text)
                if act_data.get('has_weather'):
                    new_index = self.activity_listbox.get(0, "end").index(display_text)
                    self.activity_listbox.itemconfig(new_index, {'bg': ('#502020' if sv_ttk.get_theme() == 'dark' else '#FFDDDD')})
                    
    def on_activity_select(self, event=None):
        selections = self.activity_listbox.curselection()
        if not selections: return

        route_selections = self.route_listbox.curselection()
        if not route_selections: return

        self.start_loading("Loading activity details...")
        selected_display = self.activity_listbox.get(selections[0])
        
        selected_route_name = self.route_listbox.get(route_selections[0])
        route_info = self.current_route_data.get(selected_route_name)
        if not route_info: return

        for act_data in self.current_activities.values():
            if f"{act_data['display_name']} ({Path(act_data['path']).name})" == selected_display:
                self.selected_activity_path = act_data['path']
                self.edit_weather_button.config(state=tk.NORMAL if act_data.get('has_weather') else tk.DISABLED)
                self.metar_button.config(state=tk.NORMAL)
                threading.Thread(target=self.update_activity_info, args=(route_info,), daemon=True).start()
                break
                
    def update_activity_info(self, route_info, scout_coords=None):
        try:
            if self.shutdown_event.is_set(): return

            if scout_coords:
                lat, lon = scout_coords; self.found_coords = (lat, lon)
                if not self.shutdown_event.is_set(): self.update_weather_info(lat, lon, route_info)
                if not self.shutdown_event.is_set(): self.after(0, self.stop_loading); return

            self.activity_details = self.parser.get_activity_details(self.selected_activity_path)
            if not self.shutdown_event.is_set(): self.after(0, lambda: self.update_details_text(self.activity_details))
            path_coords, self.path_dist = self.parser.get_activity_path_coords(route_info['path'], self.activity_details['path_id'])
            if path_coords:
                self.path_coords_cache = path_coords
                self.found_coords = path_coords[0][0]
                if not self.shutdown_event.is_set(): self.after(0, lambda: self._update_map_with_path(path_coords))
                if not self.shutdown_event.is_set(): self.update_weather_info(self.found_coords[0], self.found_coords[1], route_info)
            else:
                self.path_coords_cache = None; lat, lon = self.parser.find_route_start_location(route_info); self.found_coords = (lat, lon)
                if lat is not None:
                    if not self.shutdown_event.is_set(): self.after(0, lambda: self._update_map_with_start_point(lat, lon))
                    if not self.shutdown_event.is_set(): self.update_weather_info(lat, lon, route_info)
                else:
                    if not self.shutdown_event.is_set(): self.after(0, lambda: self.clear_weather_info("No coordinates found."))
            if not self.shutdown_event.is_set(): self.after(0, self.stop_loading)
        except Exception as e:
            self.log(f"[CRITICAL] Unhandled exception in update_activity_info thread: {e}")
            self.log(traceback.format_exc())
            if not self.shutdown_event.is_set(): self.after(0, self.stop_loading)
        
    def _update_map_with_path(self, path_coords_with_dist):
        path_coords = [p[0] for p in path_coords_with_dist]
        self.map_widget.delete_all_path(); self.map_widget.delete_all_marker()
        if self.scout_marker: self.scout_marker.delete()
        if len(path_coords) >= 2:
            self.map_widget.set_path(path_coords, color="crimson", width=7)
            self.map_widget.set_marker(path_coords[0][0], path_coords[0][1], text="Start", text_color="white", marker_color_circle="#229922", marker_color_outside="darkgreen")
            self.map_widget.set_marker(path_coords[-1][0], path_coords[-1][1], text="End", text_color="white", marker_color_circle="#C70039", marker_color_outside="darkred")
            min_lat = min(p[0] for p in path_coords); max_lat = max(p[0] for p in path_coords); min_lon = min(p[1] for p in path_coords); max_lon = max(p[1] for p in path_coords)
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

    def update_weather_info(self, lat, lon, route_info, date_obj=None):
        if self.shutdown_event.is_set(): return
        self.log(f"[Info] Fetching weather for Lat: {lat:.4f}, Lon: {lon:.4f}" + (f" on Date: {date_obj.strftime('%Y-%m-%d')}" if date_obj else " for Live Weather"))
        self.start_loading("Fetching weather data...")
        
        self.weather_fetch_points = [(lat, lon)]
        if self.path_dist and self.path_coords_cache and len(self.path_coords_cache) > 2:
            pin_distance_m = self.config.get('pin_distance_km') * 1000
            
            if self.path_dist > pin_distance_m:
                points = {self.path_coords_cache[0][0]} # Use a set to handle duplicates
                
                num_pins = int(self.path_dist // pin_distance_m)
                for i in range(1, num_pins + 1):
                    target_dist = i * pin_distance_m
                    closest_point = min(self.path_coords_cache, key=lambda p: abs(p[1] - target_dist))
                    points.add(closest_point[0])
                
                points.add(self.path_coords_cache[-1][0])
                
                # Sort points based on their order in the original path to maintain route progression
                sorted_points = sorted(list(points), key=lambda p: [c[0] for c in self.path_coords_cache].index(p))
                self.weather_fetch_points = sorted_points
                self.log(f"[Info] Long route (>{self.path_dist/1000:.1f}km). Using {len(self.weather_fetch_points)} weather points (~{pin_distance_m/1000}km apart).")

        self.raw_forecast_list = self.weather.get_weather_data(self.weather_fetch_points, date_obj)
        
        if self.raw_forecast_list:
            first_point_data = self.raw_forecast_list[0]
            if not self.shutdown_event.is_set(): self.after(0, lambda: self._update_weather_widgets(first_point_data, date_obj))
            if not self.shutdown_event.is_set(): self.after(0, self._update_map_with_weather_points)
        else:
            if not self.shutdown_event.is_set(): self.after(0, lambda: self._update_weather_widgets(None, date_obj))

        if not self.shutdown_event.is_set(): self.after(0, self.stop_loading)
        
    def _update_weather_widgets(self, data, date_obj):
        if not data: self.log("[ERROR] Failed to fetch or parse weather data."); self.clear_weather_info("Failed to fetch weather data."); return
        self.historical_button.config(state=tk.NORMAL if TKCALENDAR_AVAILABLE else tk.DISABLED)
        self.save_preset_button.pack(fill=tk.X, pady=5)
        
        if self.historical_selection:
            self.current_weather_button.config(state=tk.NORMAL)
            self.generate_live_button.config(state=tk.DISABLED)
            self.generate_historical_button.config(state=tk.NORMAL)
        else:
            self.current_weather_button.config(state=tk.DISABLED)
            self.generate_live_button.config(state=tk.NORMAL)
            self.generate_historical_button.config(state=tk.DISABLED)
        
        self._update_forecast_display(data, date_obj)

    def _update_forecast_display(self, data, date_obj, point_index=None):
        if not data:
            self.log("[ERROR] No data to display in forecast.")
            self.clear_weather_info("No forecast data available for this point.")
            return

        if point_index is not None:
            coords = self.weather_fetch_points[point_index]
            self.weather_mode_label.config(text=f"Previewing Point {point_index+1}: {coords[0]:.2f}, {coords[1]:.2f}")
        elif self.historical_selection:
            date_str = self.historical_selection['date'].strftime('%Y-%m-%d')
            self.weather_mode_label.config(text=f"Preview: Historical (Start of Route - {date_str})")
        else:
            self.weather_mode_label.config(text="Previewing: Live Weather (Start of Route)")

        hourly = data.get("hourly", {})
        header = f"{'Time':<8}{'Temp':<8}{'Precip':<10}{'Clouds':<10}{'Wind':<15}{'View':<10}{'Condition'}\n"
        self.forecast_text.config(state=tk.NORMAL)
        self.forecast_text.delete(1.0, tk.END)
        self.forecast_text.insert(tk.END, header + "-"*(len(header)+10) + "\n")
        
        def deg_to_dir(deg):
            dirs = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
            return dirs[int((deg + 11.25) / 22.5) % 16] if deg is not None else "N/A"

        for i in range(min(48, len(hourly.get('time', [])))):
            temp = f"{hourly['temperature_2m'][i]:.1f}°C" if 'temperature_2m' in hourly and i < len(hourly['temperature_2m']) and hourly['temperature_2m'][i] is not None else "N/A"
            precip = f"{hourly['precipitation'][i]:.1f}mm" if 'precipitation' in hourly and i < len(hourly['precipitation']) and hourly['precipitation'][i] is not None else "N/A"
            clouds = f"{hourly['cloudcover'][i]}%" if 'cloudcover' in hourly and i < len(hourly['cloudcover']) and hourly['cloudcover'][i] is not None else "N/A"
            wind_s = hourly['windspeed_10m'][i] if 'windspeed_10m' in hourly and i < len(hourly['windspeed_10m']) else None
            wind_d = hourly['winddirection_10m'][i] if 'winddirection_10m' in hourly and i < len(hourly['winddirection_10m']) else None
            wind = f"{wind_s:.1f}km/h {deg_to_dir(wind_d)}" if wind_s is not None else "N/A"
            vis = f"{hourly['visibility'][i]/1000:.1f}km" if 'visibility' in hourly and i < len(hourly['visibility']) and hourly['visibility'][i] is not None else "N/A"
            cond = self.weather.WMO_CODES.get(int(hourly['weathercode'][i]), 'N/A') if 'weathercode' in hourly and i < len(hourly['weathercode']) and hourly['weathercode'][i] is not None else "N/A"
            line = f"{hourly['time'][i][-5:]:<8}{temp:<8}{precip:<10}{clouds:<10}{wind:<15}{vis:<10}{cond}\n"
            self.forecast_text.insert(tk.END, line)
        
        self.forecast_text.config(state=tk.DISABLED)
        chart_title_suffix = f" for Point {point_index+1}" if point_index is not None else " (Start of Route)"
        self.chart_widget.plot_data(hourly, (date_obj.strftime("%Y-%m-%d") if date_obj else "Live") + chart_title_suffix)
        
    def select_historical_date(self):
        if not self.found_coords: messagebox.showwarning("Warning", "Please select an activity first."); return
        dialog = DateSelectionWindow(self); self.wait_window(dialog)
        if dialog.result:
            self.historical_selection = dialog.result; lat, lon = self.found_coords
            route_info = self.current_route_data.get(self.route_listbox.get(self.route_listbox.curselection()[0]))
            threading.Thread(target=self.update_weather_info, args=(lat, lon, route_info, self.historical_selection['date']), daemon=True).start()
            
    def load_current_weather_action(self):
        if not self.found_coords: return
        self.historical_selection = None
        lat, lon = self.found_coords
        route_info = self.current_route_data.get(self.route_listbox.get(self.route_listbox.curselection()[0]))
        threading.Thread(target=self.update_weather_info, args=(lat, lon, route_info), daemon=True).start()

    def on_map_right_click(self, coords):
        self.start_loading(f"Scouting weather at {coords[0]:.4f}, {coords[1]:.4f}...")
        self.weather_mode_label.config(text=f"Preview: Scouting Location")
        if self.scout_marker: self.scout_marker.delete()
        self.scout_marker = self.map_widget.set_marker(coords[0], coords[1], text="Scout Location", marker_color_circle="cyan", marker_color_outside="darkcyan")
        
        route_selections = self.route_listbox.curselection()
        if not route_selections:
             self.log("[ERROR] Cannot scout weather, no route selected.")
             self.stop_loading()
             return

        route_info = self.current_route_data.get(self.route_listbox.get(route_selections[0]))
        self.path_coords_cache = None # Clear path cache for scout clicks
        threading.Thread(target=self.update_activity_info, args=(route_info, coords), daemon=True).start()

    def _update_map_with_weather_points(self):
        for marker in self.weather_point_markers:
            marker.delete()
        self.weather_point_markers.clear()

        if not self.raw_forecast_list or not self.weather_fetch_points or len(self.weather_fetch_points) <= 1:
            self.log("[Debug] Not enough weather points to draw on map.")
            return
        
        self.log(f"[Debug] Drawing {len(self.weather_fetch_points)} weather points on map.")
        for i, point in enumerate(self.weather_fetch_points):
            marker = self.map_widget.set_marker(
                point[0], point[1],
                text=f"W{i+1}",
                command=lambda m, idx=i: self.on_weather_marker_click(idx),
                marker_color_circle="#00529B", 
                marker_color_outside="#003B6F"
            )
            self.weather_point_markers.append(marker)

    def on_weather_marker_click(self, index):
        if index < len(self.raw_forecast_list):
            forecast_data = self.raw_forecast_list[index]
            point_coords = self.weather_fetch_points[index]
            date_obj = self.historical_selection['date'] if self.historical_selection else None
            
            self.log(f"[Info] Displaying weather for point {index+1} at {point_coords[0]:.4f}, {point_coords[1]:.4f}")
            self._update_forecast_display(forecast_data, date_obj, point_index=index)

    def run_generation_thread(self, chaotic=False, historical=False): 
        threading.Thread(target=self.generate_weather_worker, args=(chaotic, historical), daemon=True).start()
        
    def run_chaotic_generation(self):
        if not self.selected_activity_path: messagebox.showwarning("Warning", "Please select an activity first."); return
        self.run_generation_thread(chaotic=True)
        
    def generate_weather_worker(self, chaotic=False, historical=False):
        try:
            if self.shutdown_event.is_set(): return
            self.after(0, self.start_loading, "Generating new activity file...")
            if not self.selected_activity_path:
                self.log("[ERROR] Generation failed: No activity selected.")
                self.after(0, self.stop_loading)
                return
            
            if not self.found_coords:
                self.log("[ERROR] Generation failed: Coordinates not found.")
                self.after(0, self.stop_loading)
                return
            
            self.sound_manager.copied_sounds.clear()
            route_info = self.current_route_data.get(self.route_listbox.get(self.route_listbox.curselection()[0]))
            
            date_obj, weather_events, msg, season = None, None, None, self.activity_details.get('season', 1)

            if chaotic:
                weather_events, msg = self.weather.create_chaotic_weather_events(self.sound_manager, route_info['path'])
            else:
                if historical:
                    if not self.historical_selection:
                        self.log("[ERROR] Historical generation called but no date selected.")
                        if not self.shutdown_event.is_set(): self.after(0, self.stop_loading)
                        return
                    date_obj = self.historical_selection['date']
                    start_hour = self.historical_selection['hour']
                else: # Live Weather
                    date_obj = datetime.now().date()
                    start_hour = datetime.now().hour
                
                season = self.weather.get_season(date_obj, self.found_coords[0])
                add_thunder = self.add_thunder_var.get(); add_wind = self.add_wind_var.get(); add_rain = self.add_rain_var.get()
                transition_secs = self.config.get('weather_transition_secs')
                
                path_coords_for_api = self.path_coords_cache
                if not path_coords_for_api:
                    path_coords_for_api = [(self.found_coords, 0)] if self.found_coords else []

                weather_events, msg = self.weather.create_weather_events_string(path_coords_for_api, self.path_dist, season, date_obj, start_hour, add_thunder, add_wind, add_rain, self.sound_manager, route_info['path'], transition_secs)
                
            if self.shutdown_event.is_set(): return
            if not weather_events: self.log(f"[ERROR] Weather event string creation failed: {msg}"); self.after(0, self.stop_loading); return
            self.log(f"[Info] {msg}")
            
            new_path, save_msg = self.parser.modify_and_save_activity(self.selected_activity_path, weather_events, date_obj, chaotic, season=season)
            
            if new_path:
                success_message = f"New activity file created:\n\n{Path(new_path).name}"
                if self.raw_forecast_list and self.raw_forecast_list[0].get("sunrise_str"):
                    sunrise = self.raw_forecast_list[0]["sunrise_str"]
                    sunset = self.raw_forecast_list[0]["sunset_str"]
                    success_message += f"\n\nSunrise: {sunrise}\nSunset: {sunset}"
                
                self.log(f"[Success] {save_msg}\n  > Saved to: {Path(new_path).name}")
                self.after(0, lambda: messagebox.showinfo("Success", success_message))
            else:
                self.log(f"[ERROR] CRITICAL: Failed to save new activity file: {save_msg}")
                
            if not self.shutdown_event.is_set(): self.after(0, self.stop_loading)
            if not self.shutdown_event.is_set(): self.after(0, self.on_route_select)
        except Exception as e:
            self.log(f"[CRITICAL] Unhandled exception in generate_weather_worker thread: {e}")
            self.log(traceback.format_exc())
            if not self.shutdown_event.is_set(): self.after(0, self.stop_loading)
        
    def save_forecast_as_preset(self):
        self.weather.save_forecast_as_preset(self)
        
    def run_metar_generation(self):
        if not self.selected_activity_path:
            messagebox.showwarning("No Activity", "Please select a base activity first.", parent=self)
            return
        
        icao = tk.simpledialog.askstring("METAR Input", "Enter 4-letter ICAO airport code (e.g., KLAX, EGLL):", parent=self)
        if icao and len(icao) in [3,4]:
            threading.Thread(target=self.generate_from_metar_worker, args=(icao,), daemon=True).start()
        elif icao:
            messagebox.showerror("Invalid ICAO", "ICAO code must be 3 or 4 letters.", parent=self)
    
    def generate_from_metar_worker(self, icao):
        try:
            if self.shutdown_event.is_set(): return
            self.after(0, self.start_loading, f"Generating weather from METAR for {icao}...")
            
            weather_events, msg = self.weather.create_weather_from_metar(icao)
            if not weather_events:
                self.log(f"[ERROR] {msg}")
                self.after(0, lambda: messagebox.showerror("METAR Error", msg, parent=self))
                self.after(0, self.stop_loading)
                return
            
            self.log(f"[Info] {msg}")
            new_path, save_msg = self.parser.modify_and_save_activity(self.selected_activity_path, weather_events, metar_station=icao)

            if new_path:
                self.log(f"[Success] {save_msg}\n  > Saved to: {Path(new_path).name}")
                self.after(0, lambda: messagebox.showinfo("Success", f"New activity file created:\n\n{Path(new_path).name}"))
            else:
                self.log(f"[ERROR] CRITICAL: Failed to save new activity file: {save_msg}")
            
            if not self.shutdown_event.is_set(): self.after(0, self.stop_loading)
            if not self.shutdown_event.is_set(): self.after(0, self.on_route_select)
        except Exception as e:
            self.log(f"[CRITICAL] Unhandled exception in generate_from_metar_worker thread: {e}")
            self.log(traceback.format_exc())
            if not self.shutdown_event.is_set(): self.after(0, self.stop_loading)

    def run_route_cleanup(self):
        selections = self.route_listbox.curselection()
        if not self.parser or not selections: return
        selected_route_name = self.route_listbox.get(selections[0]); route_path = self.current_route_data.get(selected_route_name)['path']
        msg = (f"This will permanently delete all generated files (*.WTHLINK.*.act, WEATHERLINK_*.wav) from the route '{selected_route_name}' and its subfolders.\n\nAre you sure you want to continue?")
        if messagebox.askyesno("Confirm Route Cleanup", msg, icon='warning'):
            self.start_loading(f"Cleaning files for route '{selected_route_name}'...")
            acts, sounds = self.parser.cleanup_generated_files(route_path); self.stop_loading()
            messagebox.showinfo("Cleanup Complete", f"Deleted {acts} activity file(s) and {sounds} sound file(s) from this route.")
            self.on_route_select()

    def run_global_cleanup(self):
        if not self.config.get('content_paths'): messagebox.showwarning("Warning", "No Content Folders configured in Settings."); return
        msg = (f"This will scan ALL configured content folders and permanently delete ALL generated files (*.WTHLINK.*.act, WEATHERLINK_*.wav).\n\nThis action cannot be undone. Are you absolutely sure?")
        if messagebox.askyesno("Confirm GLOBAL Cleanup", msg, icon='warning'):
            self.start_loading("Performing global cleanup...")
            total_acts, total_sounds = 0, 0
            for path in self.config.get('content_paths'):
                temp_parser = openrails_parser.OpenRailsParser(path, self.log)
                acts, sounds = temp_parser.cleanup_generated_files(path)
                total_acts += acts; total_sounds += sounds
            self.stop_loading()
            messagebox.showinfo("Global Cleanup Complete", f"Deleted {total_acts} activity file(s) and {total_sounds} sound file(s) from all content folders.")
            if self.route_listbox.curselection(): self.on_route_select()

    def clear_info(self):
        self.generate_live_button.config(state=tk.DISABLED); self.historical_button.config(state=tk.DISABLED); self.found_coords = None; self.selected_activity_path = None; self.historical_selection = None
        self.generate_historical_button.config(state=tk.DISABLED)
        self.metar_button.config(state=tk.DISABLED)
        self.desc_text.config(state=tk.NORMAL); self.desc_text.delete(1.0, tk.END); self.desc_text.config(state=tk.DISABLED)
        self.existing_weather_raw.config(state=tk.NORMAL); self.existing_weather_raw.delete(1.0, tk.END); self.existing_weather_raw.config(state=tk.DISABLED)
        for item in self.existing_weather_human.get_children(): self.existing_weather_human.delete(item)
        self.clear_weather_info("Select a route and activity.")
        self.chart_widget.clear_plot()
        if self.scout_marker:
            self.scout_marker.delete()
            self.scout_marker = None
        self.map_widget.delete_all_path(); self.map_widget.delete_all_marker()
        for marker in self.weather_point_markers: marker.delete()
        self.weather_point_markers.clear(); self.raw_forecast_list.clear(); self.weather_fetch_points.clear()
        self.weather_mode_label.config(text="Previewing: N/A"); self.current_weather_button.config(state=tk.DISABLED)
        self.edit_weather_button.config(state=tk.DISABLED)
        self.save_preset_button.pack_forget()
        self.route_cleanup_button.config(state=tk.DISABLED)

    def clear_weather_info(self, message):
        self.forecast_text.config(state=tk.NORMAL); self.forecast_text.delete(1.0, tk.END); self.forecast_text.insert(tk.END, message); self.forecast_text.config(state=tk.DISABLED)
    
    def get_cache_path(self):
        return Path(self.config.config_path.parent / "route_cache.json")

    def load_routes_from_cache(self, content_path):
        cache_file = self.get_cache_path()
        if not cache_file.exists():
            return None
        try:
            with open(cache_file, 'r') as f:
                full_cache = json.load(f)
                return full_cache.get(content_path)
        except (json.JSONDecodeError, OSError):
            return None

    def save_routes_to_cache(self, content_path, route_data):
        if not self.config.get('use_route_cache'):
            return
        cache_file = self.get_cache_path()
        try:
            full_cache = {}
            if cache_file.exists():
                with open(cache_file, 'r') as f:
                    full_cache = json.load(f)
            full_cache[content_path] = route_data
            with open(cache_file, 'w') as f:
                json.dump(full_cache, f, indent=2)
            self.log("[Info] Saved route list to cache.")
        except (json.JSONDecodeError, OSError, TypeError) as e:
            self.log(f"[ERROR] Could not write to route cache: {e}")

if __name__ == "__main__":
    if not PIL_AVAILABLE:
        messagebox.showerror("Missing Library", "The 'Pillow' library is not installed.\n\nPlease open a command prompt and run:\npip install Pillow")
        sys.exit(1)
    if not TKCALENDAR_AVAILABLE:
        messagebox.showerror("Missing Library", "The 'tkcalendar' library is not installed.\n\nPlease open a command prompt and run:\npip install tkcalendar")
        sys.exit(1)
    app = MainApplication()
    app.mainloop()