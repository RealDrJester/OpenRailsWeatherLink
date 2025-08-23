# ui_components.py
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import sv_ttk
from datetime import date
import webbrowser
import sys
from pathlib import Path

try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

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

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = Path(__file__).parent.resolve()
    return base_path / relative_path

class Tooltip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tooltip_window = None
        self.widget.bind("<Enter>", self.show_tooltip)
        self.widget.bind("<Leave>", self.hide_tooltip)

    def show_tooltip(self, event):
        x = event.x_root + 20
        y = event.y_root + 10

        self.tooltip_window = tk.Toplevel(self.widget)
        self.tooltip_window.wm_overrideredirect(True)
        self.tooltip_window.wm_geometry(f"+{x}+{y}")

        label = tk.Label(self.tooltip_window, text=self.text, background="#FFFFE0", foreground="black", relief="solid", borderwidth=1, wraplength=250, justify=tk.LEFT)
        label.pack(ipadx=1)

    def hide_tooltip(self, event):
        if self.tooltip_window:
            self.tooltip_window.destroy()
        self.tooltip_window = None

class StartupInfoWindow(tk.Toplevel):
    def __init__(self, parent, config):
        super().__init__(parent)
        self.config = config
        self.title("Welcome to ORTS WeatherLink - Important Information")
        self.transient(parent)
        self.grab_set()

        main_frame = ttk.Frame(self, padding="15")
        main_frame.pack(expand=True, fill="both")

        ttk.Label(main_frame, text="Limitations & Considerations", font=("", 12, "bold")).pack(pady=(0, 10))

        text = (
            "- Route Pathing Accuracy: The activity path shown on the map is based on data within the route files. Its accuracy depends on how the route creator defined it and may not always be 100% precise.\n\n"
            "- Simulator Data Limitations: Open Rails does not currently use temperature, wind speed, or wind direction for its in-game physics. While this data is fetched and displayed for informational purposes, it is not injected into the simulation.\n\n"
            "- Sound Playback: The injection of custom sounds into activities is subject to the limitations of the Open Rails sound engine. Sounds may occasionally overlap or behave unexpectedly. For a more seamless and immersive experience, using longer audio files (10-15 minutes) for ambient sounds like rain and wind is highly recommended.\n\n"
            "- Weather API: This tool relies on the free Open-Meteo API. Its availability and accuracy are not guaranteed. Please be mindful of fair use."
        )
        message = tk.Message(main_frame, text=text, width=400)
        message.pack(pady=10)

        self.dont_show_var = tk.BooleanVar(value=False)
        check = ttk.Checkbutton(main_frame, text="Don't show this message again", variable=self.dont_show_var)
        check.pack(pady=10)

        ttk.Button(main_frame, text="OK", command=self.on_ok).pack()

    def on_ok(self):
        self.config.set('show_startup_info', not self.dont_show_var.get())
        self.destroy()

class AboutWindow(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("About ORTS WeatherLink")
        self.transient(parent)
        self.grab_set()
        
        main_frame = ttk.Frame(self, padding="20")
        main_frame.pack(expand=True, fill="both")

        ttk.Label(main_frame, text="ORTS WeatherLink", font=("", 14, "bold")).pack(pady=(0, 5), anchor="w")
        ttk.Label(main_frame, text="Version 1.0").pack(anchor="w")
        ttk.Label(main_frame, text="Author: DrJester, Grok, Claude, Copilot & Gemini AI.").pack(anchor="w", pady=(0,10))
        
        def create_link(parent, text, url):
            link = ttk.Label(parent, text=text, foreground="blue", cursor="hand2")
            link.pack(anchor="w")
            link.bind("<Button-1>", lambda e: webbrowser.open_new(url))
            return link

        ttk.Label(main_frame, text="Links:", font=("", 10, "bold")).pack(anchor="w", pady=(5,0))
        create_link(main_frame, "Linktree (All Projects)", "https://linktr.ee/DrJester")
        self.github_link = "https://github.com/RealDrJester/OpenRailsWeatherLink/"
        create_link(main_frame, "This Software's GitHub Repository", self.github_link)
        create_link(main_frame, "All Public GitHub Repositories", "https://github.com/RealDrJester")
        
        description = "ORTS WeatherLink is a tool designed to enhance the realism of the Open Rails train simulator. It fetches real-world historical or current weather data based on the route's location and date, and automatically creates a new activity file with dynamic weather changes. This allows users to experience authentic atmospheric conditions—from clear skies to thunderstorms—that evolve throughout their simulated journey. For Ede."
        desc_label = ttk.Label(main_frame, text=description, wraplength=400, justify=tk.LEFT)
        desc_label.pack(pady=(15,0), anchor="w")

        if PIL_AVAILABLE:
            logo_path = resource_path("logo1.png")
            if logo_path.exists():
                img = Image.open(logo_path)
                img.thumbnail((200, 200))
                self.logo_img = ImageTk.PhotoImage(img)
                logo_label = ttk.Label(main_frame, image=self.logo_img, cursor="hand2")
                logo_label.pack(pady=(15,0))
                logo_label.bind("<Double-Button-1>", lambda e: webbrowser.open_new(self.github_link))

        ttk.Button(main_frame, text="Close", command=self.destroy).pack(pady=(15, 0))
        
        self.update_idletasks()
        self.minsize(self.winfo_reqwidth(), self.winfo_reqheight())
        self.resizable(False, False)

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
        
        performance_frame = ttk.LabelFrame(general_frame, text="Performance", padding=10)
        performance_frame.pack(fill="x", pady=(10,0))
        self.cache_var = tk.BooleanVar(value=self.config.get('use_route_cache'))
        cache_check = ttk.Checkbutton(performance_frame, text="Enable Route List Cache (improves startup speed)", variable=self.cache_var, command=self.save_cache_setting)
        cache_check.pack(anchor="w")

        map_settings_frame = ttk.LabelFrame(general_frame, text="Map Settings", padding=10)
        map_settings_frame.pack(fill="x", pady=(10,0))
        ttk.Label(map_settings_frame, text="Weather Pin Distance (km):").grid(row=0, column=0, sticky="w", padx=5)
        self.pin_distance_var = tk.IntVar(value=self.config.get('pin_distance_km'))
        pin_spinbox = ttk.Spinbox(map_settings_frame, from_=5, to=100, increment=5, textvariable=self.pin_distance_var, command=self.save_pin_distance, width=8)
        pin_spinbox.grid(row=0, column=1, sticky="w")

        sound_frame = ttk.LabelFrame(general_frame, text="Sound System", padding=10)
        sound_frame.pack(fill="x", pady=(10,0))
        ttk.Button(sound_frame, text="Rescan `user_sounds` Folder", command=self.parent.sound_manager.discover_sounds).pack(fill="x")

        reset_frame = ttk.LabelFrame(general_frame, text="Application Reset", padding=10)
        reset_frame.pack(fill="x", pady=(10,0))
        ttk.Button(reset_frame, text="Reset All Settings to Default...", command=self.confirm_and_reset_settings).pack(fill="x")

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

    def save_cache_setting(self):
        self.config.set('use_route_cache', self.cache_var.get())

    def confirm_and_reset_settings(self):
        msg = "This will reset all application settings (like theme and pin distance) to their original defaults. Your Content Folders list will not be affected.\n\nAre you sure you want to continue?"
        if messagebox.askyesno("Confirm Reset", msg, icon='warning', parent=self):
            self.config.reset_to_defaults()
            self.theme_var.set(self.config.get('theme'))
            self.pin_distance_var.set(self.config.get('pin_distance_km'))
            self.cache_var.set(self.config.get('use_route_cache'))
            self.apply_theme()
            self.parent.geometry(self.config.get('window_geometry'))
            messagebox.showinfo("Success", "Settings have been reset to default.", parent=self)

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

    def clear_plot(self):
        if not MPL_AVAILABLE: return
        self.ax1.clear()
        self.ax2.clear()
        self.figure.suptitle("")
        self.update_theme()
        self.canvas.draw()
    
    def plot_data(self, hourly_data, title):
        if not MPL_AVAILABLE or not hourly_data or not hourly_data.get('time'):
            return
        
        self.clear_plot()

        times = hourly_data.get('time', [])
        x_labels = [t[-5:] for t in times]
        x_ticks = range(len(x_labels))

        self.figure.suptitle(title)

        def get_series(key, transform=lambda x: x):
            series = hourly_data.get(key, [])
            return [transform(v) if v is not None else None for v in series]

        self.ax1.plot(x_ticks, get_series('temperature_2m'), label='Temp (°C)', color='red')
        self.ax1.plot(x_ticks, get_series('cloudcover'), label='Cloud (%)', color='gray')
        self.ax1.plot(x_ticks, get_series('windspeed_10m'), label='Wind (km/h)', color='green', linestyle='--')
        self.ax1.plot(x_ticks, get_series('visibility', lambda v: v / 1000), label='Vis (km)', color='purple', linestyle=':')
        self.ax2.bar(x_ticks, get_series('precipitation'), label='Precip (mm)', color='blue', alpha=0.6)
        
        if x_ticks:
            self.ax1.set_xticks(x_ticks[::4])
            self.ax1.set_xticklabels(x_labels[::4])

        self.ax1.legend(loc='upper left')
        self.ax2.legend(loc='upper right')
        
        if any(v is not None and v > 0 for v in get_series('precipitation')):
            self.ax2.set_ylim(bottom=0)
        else:
            self.ax2.set_ylim(0, 1)

        self.figure.tight_layout(rect=[0, 0.03, 1, 0.95])

        self.update_theme()
        self.canvas.draw()

    def update_theme(self):
        if not MPL_AVAILABLE: return
        is_dark = sv_ttk.get_theme() == "dark"; bg_color = '#2B2B2B' if is_dark else '#F0F0F0'; text_color = 'white' if is_dark else 'black'
        self.figure.patch.set_facecolor(bg_color); self.ax1.set_facecolor('#3C3C3C' if is_dark else 'white')
        self.ax1.tick_params(axis='x', colors=text_color, labelrotation=45); self.ax1.tick_params(axis='y', colors=text_color)
        self.ax2.tick_params(axis='y', colors=text_color)
        for spine in self.ax1.spines.values(): spine.set_color(text_color)
        for spine in self.ax2.spines.values(): spine.set_color(text_color)
        if self.figure._suptitle is not None:
            self.figure.suptitle(self.figure._suptitle.get_text(), color=text_color)
        self.ax1.set_xlabel("Time", color=text_color); self.ax1.set_ylabel("Temp/Cloud/Wind/View", color=text_color); self.ax2.set_ylabel("Rain (mm/h)", color=text_color)
        
        for ax in [self.ax1, self.ax2]:
            legend = ax.get_legend()
            if legend:
                legend.get_frame().set_facecolor(bg_color)
                for text in legend.get_texts():
                    text.set_color(text_color)

        self.canvas.draw()