# ui_components.py
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import sv_ttk
from datetime import date

try:
    from tkcalendar import DateEntry
    TKCALENDAR_AVAILABLE = True
except ImportError:
    TKCALENDAR_AVAILABLE = False
try:
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    MPL_AVAILABLE = True
except ImportError:
    MPL_AVAILABLE = False

class AboutWindow(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("About ORTS WeatherLink")
        self.geometry("450x350")
        self.transient(parent)
        self.grab_set()
        
        main_frame = ttk.Frame(self, padding="20")
        main_frame.pack(expand=True, fill="both")

        ttk.Label(main_frame, text="ORTS WeatherLink", font=("", 14, "bold")).pack(pady=(0, 5), anchor="w")
        ttk.Label(main_frame, text="Version 1.0").pack(anchor="w")
        ttk.Label(main_frame, text="Author: DrJester, Grok, Claude, Copilot & Gemini AI.").pack(anchor="w", pady=(0,10))

        ttk.Label(main_frame, text="Links:", font=("", 10, "bold")).pack(anchor="w", pady=(5,0))
        ttk.Label(main_frame, text="https://linktr.ee/DrJester - Linktree for all my projects.").pack(anchor="w")
        ttk.Label(main_frame, text="https://github.com/RealDrJester/OpenRailsWeatherLink/ - This software Github repository.").pack(anchor="w")
        ttk.Label(main_frame, text="https://github.com/RealDrJester - GitHub repositories for all my public works.").pack(anchor="w", pady=(0,10))
        
        desc_text = scrolledtext.ScrolledText(main_frame, wrap=tk.WORD, height=4)
        desc_text.pack(fill="both", expand=True, pady=(5,0))
        desc_text.insert(tk.END, "[DESCRIPTION OF THE PROGRAM]. For Ede.")
        desc_text.config(state=tk.DISABLED)

        ttk.Button(main_frame, text="Close", command=self.destroy).pack(pady=(15, 0))

class DateSelectionWindow(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent); self.title("Select Historical Date"); self.geometry("300x150"); self.transient(parent); self.grab_set(); self.result = None
        main_frame = ttk.Frame(self, padding="15"); main_frame.pack(expand=True, fill="both"); main_frame.grid_columnconfigure(1, weight=1)
        ttk.Label(main_frame, text="Date:").grid(row=0, column=0, sticky="w", pady=(0, 10))
        if TKCALENDAR_AVAILABLE:
            self.cal = DateEntry(main_frame, selectmode='day', date_pattern='yyyy-mm-dd', maxdate=date.today()); self.cal.grid(row=0, column=1, sticky="ew")
        else: ttk.Label(main_frame, text="tkcalendar not found!").grid(row=0, column=1)
        ttk.Label(main_frame, text="Start Hour:").grid(row=1, column=0, sticky="w", pady=(0, 10))
        self.hour_combo = ttk.Combobox(main_frame, values=[f"{h:02d}" for h in range(24)], state="readonly"); self.hour_combo.set("12"); self.hour_combo.grid(row=1, column=1, sticky="ew")
        button_frame = ttk.Frame(main_frame); button_frame.grid(row=2, column=0, columnspan=2, pady=(10, 0))
        ttk.Button(button_frame, text="OK", command=self.on_ok, state=tk.NORMAL if TKCALENDAR_AVAILABLE else tk.DISABLED).pack(side="left", padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.destroy).pack(side="left", padx=5)
    def on_ok(self): self.result = {"date": self.cal.get_date(), "hour": int(self.hour_combo.get())}; self.destroy()

class SettingsWindow(tk.Toplevel):
    def __init__(self, parent, config_manager):
        super().__init__(parent)
        self.transient(parent); self.grab_set()
        self.title("Settings")
        self.config = config_manager
        self.parent = parent

        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=10, pady=10)

        general_frame = ttk.Frame(notebook, padding=10)
        notebook.add(general_frame, text="General")
        
        theme_frame = ttk.LabelFrame(general_frame, text="Theme", padding=10)
        theme_frame.pack(fill="x")
        self.theme_var = tk.StringVar(value=self.config.get('theme'))
        light_rb = ttk.Radiobutton(theme_frame, text="Light", variable=self.theme_var, value="light", command=self.apply_theme)
        light_rb.pack(side="left", padx=5)
        dark_rb = ttk.Radiobutton(theme_frame, text="Dark", variable=self.theme_var, value="dark", command=self.apply_theme)
        dark_rb.pack(side="left", padx=5)
        
        map_settings_frame = ttk.LabelFrame(general_frame, text="Map Settings", padding=10)
        map_settings_frame.pack(fill="x", pady=(10,0))
        ttk.Label(map_settings_frame, text="Weather Pin Distance (km):").grid(row=0, column=0, sticky="w", padx=5)
        self.pin_distance_var = tk.IntVar(value=self.config.get('pin_distance_km'))
        pin_spinbox = ttk.Spinbox(map_settings_frame, from_=5, to=100, increment=5, textvariable=self.pin_distance_var, command=self.save_pin_distance, width=8)
        pin_spinbox.grid(row=0, column=1, sticky="w")

        sound_frame = ttk.LabelFrame(general_frame, text="Sound System", padding=10)
        sound_frame.pack(fill="x", pady=(10,0))
        ttk.Button(sound_frame, text="Rescan `user_sounds` Folder", command=self.parent.sound_manager.discover_sounds).pack(fill="x")

        paths_frame = ttk.Frame(notebook, padding=10)
        notebook.add(paths_frame, text="Content Paths & Cleanup")
        
        paths_lf = ttk.LabelFrame(paths_frame, text="Open Rails Content Folders", padding=10)
        paths_lf.pack(fill="both", expand=True)
        
        self.paths_listbox = tk.Listbox(paths_lf)
        self.paths_listbox.pack(fill="both", expand=True, pady=(0, 5))
        self.populate_paths()

        btn_frame = ttk.Frame(paths_lf)
        btn_frame.pack(fill="x")
        ttk.Button(btn_frame, text="Add...", command=self.add_path).pack(side="left", expand=True, fill="x", padx=(0,5))
        ttk.Button(btn_frame, text="Remove", command=self.remove_path).pack(side="left", expand=True, fill="x")

        cleanup_lf = ttk.LabelFrame(paths_frame, text="Cleanup Operations", padding=10)
        cleanup_lf.pack(fill="x", pady=(10,0))
        ttk.Button(cleanup_lf, text="Clean All Added Files from ALL Content Folders...", command=self.parent.run_global_cleanup).pack(fill="x")

        ttk.Button(self, text="Close", command=self.destroy).pack(pady=(0,10))

    def save_pin_distance(self):
        try:
            distance = self.pin_distance_var.get()
            self.config.set('pin_distance_km', distance)
        except (tk.TclError, ValueError):
            pass # Ignore errors from spinbox during input

    def apply_theme(self):
        theme = self.theme_var.get()
        sv_ttk.set_theme(theme)
        self.config.set('theme', theme)
        self.parent.chart_widget.update_theme()
    
    def populate_paths(self):
        self.paths_listbox.delete(0, tk.END)
        for path in self.config.get('content_paths'):
            self.paths_listbox.insert(tk.END, path)

    def add_path(self):
        path = filedialog.askdirectory(title="Select Open Rails 'Content' Folder", parent=self)
        if path:
            self.config.add_content_path(path)
            self.populate_paths()
            self.parent.path_combo['values'] = self.config.get('content_paths')
    
    def remove_path(self):
        selections = self.paths_listbox.curselection()
        if not selections: return
        path_to_remove = self.paths_listbox.get(selections[0])
        self.config.remove_content_path(path_to_remove)
        self.populate_paths()
        self.parent.path_combo['values'] = self.config.get('content_paths')
        if path_to_remove == self.parent.path_combo.get():
            self.parent.path_combo.set('')
            self.parent.route_listbox.delete(0, tk.END)
            self.parent.activity_listbox.delete(0, tk.END)
            self.parent.clear_info()

class ForecastChart(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        if not MPL_AVAILABLE: ttk.Label(self, text="Matplotlib not found.\nPlease run: pip install matplotlib").pack(expand=True); return
        self.figure = Figure(figsize=(5, 4), dpi=100); self.ax1 = self.figure.add_subplot(111)
        self.ax2 = self.ax1.twinx()
        self.canvas = FigureCanvasTkAgg(self.figure, self); self.canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.update_theme()
    def update_theme(self):
        if not MPL_AVAILABLE: return
        is_dark = sv_ttk.get_theme() == "dark"; bg_color = '#2B2B2B' if is_dark else '#F0F0F0'; text_color = 'white' if is_dark else 'black'
        self.figure.patch.set_facecolor(bg_color); self.ax1.set_facecolor('#3C3C3C' if is_dark else 'white')
        self.ax1.tick_params(axis='x', colors=text_color, labelrotation=45); self.ax1.tick_params(axis='y', colors=text_color)
        self.ax2.tick_params(axis='y', colors=text_color)
        for spine in self.ax1.spines.values(): spine.set_color(text_color)
        for spine in self.ax2.spines.values(): spine.set_color(text_color)
        self.ax1.title.set_color(text_color); self.ax1.set_xlabel("Time", color=text_color); self.ax1.set_ylabel("Temp/Cloud/Wind/View", color=text_color); self.ax2.set_ylabel("Rain (mm/h)", color=text_color)
        legend = self.ax1.get_legend()
        if legend:
            legend.get_frame().set_facecolor(bg_color)
            for text in legend.get_texts(): text.set_color(text_color)
        self.canvas.draw()
    def plot_data(self, hourly_data, date_str):
        if not MPL_AVAILABLE: return
        self.ax1.clear(); self.ax2.clear(); times = [t[-5:] for t in hourly_data['time'][:24]]; temps = hourly_data['temperature_2m'][:24]; clouds = hourly_data['cloudcover'][:24]; winds = hourly_data['windspeed_10m'][:24]; rain = hourly_data['precipitation'][:24]
        vis = [(v / 1000 if v is not None else 0) for v in hourly_data['visibility'][:24]] if hourly_data.get('visibility') else [0]*24
        p1, = self.ax1.plot(times, temps, marker='o', linestyle='-', label='Temp (°C)', color='#FF7F0E')
        p2, = self.ax1.plot(times, clouds, marker='s', linestyle='--', label='Cloud Cover (%)', color='#1F77B4')
        p3, = self.ax1.plot(times, winds, marker='^', linestyle=':', label='Wind (km/h)', color='#2CA02C')
        p4, = self.ax1.plot(times, vis, marker='x', linestyle='-.', label='View (km)', color='#9467BD')
        p5, = self.ax2.plot(times, rain, marker='D', linestyle='-', label='Rain (mm/h)', color='#D62728')
        self.ax1.set_title(f"24-Hour Forecast for {date_str}"); self.ax1.set_xlabel("Time"); self.ax1.set_ylabel("Temp / Cloud / Wind / View"); self.ax2.set_ylabel("Rain (mm/h)")
        self.ax1.grid(True, linestyle='--', alpha=0.6); self.ax1.legend(handles=[p1, p2, p3, p4, p5]); self.figure.tight_layout(); self.update_theme()
    def clear_plot(self):
        if not MPL_AVAILABLE: return
        self.ax1.clear(); self.ax2.clear(); self.ax1.set_title("No data available"); self.update_theme()