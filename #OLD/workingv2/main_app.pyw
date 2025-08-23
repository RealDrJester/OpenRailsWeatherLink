# main_app.pyw
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import threading
from pathlib import Path
import sv_ttk
import sys

# Import our custom modules
from config_manager import ConfigManager
import openrails_parser
from weather_service import WeatherService
from ui_components import AboutWindow, ForecastChart

try:
    from tkintermapview import TkinterMapView
except ImportError:
    messagebox.showerror("Missing Library", "The 'tkintermapview' library is not installed.\n\nPlease open a command prompt and run:\npip install tkintermapview")
    sys.exit(1)

class MainApplication(tk.Tk):
    def __init__(self):
        super().__init__()
        self.config = ConfigManager()
        self.parser = None
        self.weather = WeatherService()
        self.current_route_data = {}
        self.current_activities = {}
        self.selected_activity_path = None
        self.found_coords = None

        self.title("ORTS WeatherLink")
        self.geometry(self.config.get('window_geometry'))
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        sv_ttk.set_theme(self.config.get('theme'))
        self.setup_ui()
        self.post_ui_load()

    def setup_ui(self):
        top_frame = ttk.Frame(self, padding=(10, 10, 10, 0)); top_frame.pack(fill=tk.X, side=tk.TOP); top_frame.grid_columnconfigure(1, weight=1)
        ttk.Label(top_frame, text="Content Folder:").grid(row=0, column=0, sticky='w', padx=(0, 5))
        self.path_combo = ttk.Combobox(top_frame, values=self.config.get('content_paths')); self.path_combo.grid(row=0, column=1, sticky='ew')
        self.path_combo.bind("<<ComboboxSelected>>", self.on_path_selected)
        browse_button = ttk.Button(top_frame, text="Browse...", command=self.select_content_path); browse_button.grid(row=0, column=2, sticky='e', padx=(5, 10))
        self.theme_button = ttk.Button(top_frame, text="Toggle Theme", command=self.toggle_theme); self.theme_button.grid(row=0, column=3, sticky='e')

        main_paned = ttk.PanedWindow(self, orient=tk.HORIZONTAL); main_paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        left_pane = ttk.PanedWindow(main_paned, orient=tk.VERTICAL); main_paned.add(left_pane, weight=1)

        route_frame = ttk.LabelFrame(left_pane, text="1. Select Route", padding=5)
        self.route_listbox = tk.Listbox(route_frame, exportselection=False); self.route_listbox.pack(fill=tk.BOTH, expand=True)
        self.route_listbox.bind("<<ListboxSelect>>", self.on_route_select)
        left_pane.add(route_frame, weight=2)

        activity_frame = ttk.LabelFrame(left_pane, text="2. Select Activity", padding=5)
        self.activity_listbox = tk.Listbox(activity_frame, exportselection=False); self.activity_listbox.pack(fill=tk.BOTH, expand=True)
        self.activity_listbox.bind("<<ListboxSelect>>", self.on_activity_select)
        left_pane.add(activity_frame, weight=3)

        # Right Pane is now a PanedWindow itself
        right_pane = ttk.PanedWindow(main_paned, orient=tk.VERTICAL); main_paned.add(right_pane, weight=3)
        
        # Top part of Right Pane: The Notebook with details
        details_notebook = ttk.Notebook(right_pane); right_pane.add(details_notebook, weight=2)
        
        desc_frame = ttk.Frame(details_notebook)
        self.desc_text = scrolledtext.ScrolledText(desc_frame, wrap=tk.WORD, state=tk.DISABLED); self.desc_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        details_notebook.add(desc_frame, text="Description & Briefing")

        forecast_frame = ttk.Frame(details_notebook)
        self.forecast_text = scrolledtext.ScrolledText(forecast_frame, wrap=tk.WORD, state=tk.DISABLED, font=("Courier New", 9)); self.forecast_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        details_notebook.add(forecast_frame, text="Forecast Table")

        chart_frame = ttk.Frame(details_notebook)
        self.chart_widget = ForecastChart(chart_frame); self.chart_widget.pack(fill=tk.BOTH, expand=True)
        details_notebook.add(chart_frame, text="Forecast Chart")

        # Bottom part of Right Pane: Map, Actions, and Log
        bottom_pane = ttk.PanedWindow(right_pane, orient=tk.VERTICAL); right_pane.add(bottom_pane, weight=3)

        map_actions_pane = ttk.PanedWindow(bottom_pane, orient=tk.HORIZONTAL); bottom_pane.add(map_actions_pane, weight=2)
        map_frame = ttk.LabelFrame(map_actions_pane, text="Route Location", padding=5)
        self.map_widget = TkinterMapView(map_frame, corner_radius=0); self.map_widget.pack(fill=tk.BOTH, expand=True)
        map_actions_pane.add(map_frame, weight=2)

        action_frame = ttk.Frame(map_actions_pane, padding=10)
        self.generate_button = ttk.Button(action_frame, text="Generate Weather Activity", state=tk.DISABLED, command=self.run_generation_thread); self.generate_button.pack(fill=tk.X, pady=5)
        ttk.Button(action_frame, text=f"Clean Up *.{openrails_parser.APP_SUFFIX}.act Files", command=self.run_cleanup).pack(fill=tk.X, pady=5)
        ttk.Button(action_frame, text="About...", command=self.show_about_window).pack(fill=tk.X, side=tk.BOTTOM, pady=(20, 5))
        map_actions_pane.add(action_frame, weight=1)

        log_frame = ttk.LabelFrame(bottom_pane, text="Debug Console", padding=5)
        self.log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, state=tk.DISABLED, font=("Courier New", 8), height=8); self.log_text.pack(fill=tk.BOTH, expand=True)
        bottom_pane.add(log_frame, weight=1)

    def log(self, message): self.after(0, self._log_to_widget, message)
    def _log_to_widget(self, message):
        self.log_text.config(state=tk.NORMAL); self.log_text.insert(tk.END, message + "\n"); self.log_text.see(tk.END); self.log_text.config(state=tk.DISABLED)

    def on_closing(self): self.config.set('window_geometry', self.geometry()); self.destroy()
    def show_about_window(self): AboutWindow(self)
    def toggle_theme(self):
        new_theme = 'dark' if self.config.get('theme') == 'light' else 'light'; sv_ttk.set_theme(new_theme); self.config.set('theme', new_theme)
        self.chart_widget.update_theme()

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
        self.current_activities = self.parser.get_activities_for_route(route_info['path'])
        self.after(0, self._populate_activities_list)

    def _populate_activities_list(self):
        self.activity_listbox.delete(0, tk.END)
        for act_file, act_data in sorted(self.current_activities.items()): self.activity_listbox.insert(tk.END, f"{act_data['display_name']} ({act_file})")
            
    def on_activity_select(self, event=None):
        selections = self.activity_listbox.curselection()
        if not selections: return
        selected_display = self.activity_listbox.get(selections[0])
        for act_data in self.current_activities.values():
            if f"{act_data['display_name']} ({Path(act_data['path']).name})" == selected_display:
                self.selected_activity_path = act_data['path']
                threading.Thread(target=self.update_activity_info, daemon=True).start()
                break

    def update_activity_info(self):
        details = self.parser.get_activity_details(self.selected_activity_path)
        self.after(0, lambda: self.update_description_text(details))
        
        route_info = self.current_route_data.get(self.route_listbox.get(self.route_listbox.curselection()[0]))
        lat, lon = self.parser.find_route_location(route_info)
        self.found_coords = (lat, lon)

        if lat is not None:
            self.after(0, lambda: self.map_widget.set_position(lat, lon))
            self.after(0, lambda: self.map_widget.set_zoom(10))
            self.update_weather_info(lat, lon)
        else: self.after(0, lambda: self.clear_weather_info("No coordinates found for route."))

    def update_description_text(self, details):
        self.desc_text.config(state=tk.NORMAL); self.desc_text.delete(1.0, tk.END)
        self.desc_text.insert(tk.END, f"--- DESCRIPTION ---\n{details['description']}\n\n--- BRIEFING ---\n{details['briefing']}")
        self.desc_text.config(state=tk.DISABLED)

    def update_weather_info(self, lat, lon):
        data = self.weather.get_weather_data(lat, lon)
        self.after(0, lambda: self._update_weather_widgets(lat, lon, data))

    def _update_weather_widgets(self, lat, lon, data):
        if not data: self.clear_weather_info("Failed to fetch weather data."); return
        self.generate_button.config(state=tk.NORMAL)
        current = data.get("current_weather", {}); hourly = data.get("hourly", {})
        self.map_widget.delete_all_marker(); self.map_widget.set_marker(lat, lon, text=f"{current.get('windspeed', 'N/A')} km/h")
        self.forecast_text.config(state=tk.NORMAL); self.forecast_text.delete(1.0, tk.END)
        header = f"{'Time':<10}{'Temp':<10}{'Precip':<12}{'Clouds':<10}{'Wind':<15}{'Condition'}\n"; self.forecast_text.insert(tk.END, header + "-"*(len(header)+5) + "\n")
        
        for i in range(min(12, len(hourly.get('time', [])))):
            temp_str = f"{hourly['temperature_2m'][i]:.1f}°C"
            precip_str = f"{hourly['precipitation'][i]:.1f}mm"
            clouds_str = f"{hourly['cloudcover'][i]}%"
            wind_str = f"{hourly['windspeed_10m'][i]:.1f}km/h"
            cond_str = self.weather.WMO_CODES.get(hourly['weathercode'][i], 'N/A')
            line = f"{hourly['time'][i][-5:]:<10}{temp_str:<10}{precip_str:<12}{clouds_str:<10}{wind_str:<15}{cond_str}\n"
            self.forecast_text.insert(tk.END, line)
        self.forecast_text.config(state=tk.DISABLED)
        self.chart_widget.plot_data(hourly)

    def run_generation_thread(self): threading.Thread(target=self.generate_weather_worker, daemon=True).start()
    def generate_weather_worker(self):
        self.after(0, lambda: self.generate_button.config(state=tk.DISABLED)); self.log("\n--- Starting Weather Generation ---")
        if not self.selected_activity_path: self.log("  > FAILED: No activity selected."); return
        lat, lon = self.found_coords
        if lat is None: self.log("  > FAILED: Coordinates not found."); self.after(0, lambda: self.generate_button.config(state=tk.NORMAL)); return
        
        weather_events, msg = self.weather.create_weather_events_string(lat, lon)
        if not weather_events: self.log(f"  > FAILED: {msg}"); self.after(0, lambda: self.generate_button.config(state=tk.NORMAL)); return
        self.log(f"  > {msg}")

        new_path, msg = self.parser.modify_and_save_activity(self.selected_activity_path, weather_events)
        if new_path: self.log(f"  > {msg}\n  > Saved to: {Path(new_path).name}\n\n--- Generation Complete! ---")
        else: self.log(f"  > FAILED: {msg}")
        self.after(0, lambda: self.generate_button.config(state=tk.NORMAL))

    def run_cleanup(self):
        if not self.parser: return
        files_to_delete = list(self.parser.content_path.glob(f"**/*{openrails_parser.APP_SUFFIX}.act"))
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
        self.generate_button.config(state=tk.DISABLED); self.found_coords = None; self.selected_activity_path = None
        self.desc_text.config(state=tk.NORMAL); self.desc_text.delete(1.0, tk.END); self.desc_text.config(state=tk.DISABLED)
        self.clear_weather_info("Select a route and activity.")
        self.chart_widget.clear_plot()
    
    def clear_weather_info(self, message):
        self.forecast_text.config(state=tk.NORMAL); self.forecast_text.delete(1.0, tk.END)
        self.forecast_text.insert(tk.END, message); self.forecast_text.config(state=tk.DISABLED)

if __name__ == "__main__":
    app = MainApplication()
    app.mainloop()