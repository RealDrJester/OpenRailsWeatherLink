# ui_components.py
import tkinter as tk
from tkinter import ttk
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
        super().__init__(parent); self.title("About ORTS WeatherLink"); self.geometry("350x200"); self.transient(parent); self.grab_set()
        main_frame = ttk.Frame(self, padding="20"); main_frame.pack(expand=True, fill="both")
        ttk.Label(main_frame, text="ORTS WeatherLink", font=("", 14, "bold")).pack(pady=(0, 5))
        ttk.Label(main_frame, text="Final Version").pack()
        ttk.Label(main_frame, text="Real-world weather injector for Open Rails.").pack(pady=(0, 15))
        ttk.Label(main_frame, text="Developed with your valuable feedback.").pack()
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
        self.ax1.title.set_color(text_color); self.ax1.set_xlabel("Time", color=text_color); self.ax1.set_ylabel("Temp/Cloud/Wind", color=text_color); self.ax2.set_ylabel("Rain (mm/h)", color=text_color)
        legend = self.ax1.get_legend()
        if legend:
            legend.get_frame().set_facecolor(bg_color)
            for text in legend.get_texts(): text.set_color(text_color)
        self.canvas.draw()
    def plot_data(self, hourly_data, date_str):
        if not MPL_AVAILABLE: return
        self.ax1.clear(); self.ax2.clear(); times = [t[-5:] for t in hourly_data['time'][:24]]; temps = hourly_data['temperature_2m'][:24]; clouds = hourly_data['cloudcover'][:24]; winds = hourly_data['windspeed_10m'][:24]; rain = hourly_data['precipitation'][:24]
        p1, = self.ax1.plot(times, temps, marker='o', linestyle='-', label='Temp (°C)', color='#FF7F0E')
        p2, = self.ax1.plot(times, clouds, marker='s', linestyle='--', label='Cloud Cover (%)', color='#1F77B4')
        p3, = self.ax1.plot(times, winds, marker='^', linestyle=':', label='Wind (km/h)', color='#2CA02C')
        p4, = self.ax2.plot(times, rain, marker='D', linestyle='-.', label='Rain (mm/h)', color='#D62728')
        self.ax1.set_title(f"24-Hour Forecast for {date_str}"); self.ax1.set_xlabel("Time"); self.ax1.set_ylabel("Temp / Cloud / Wind"); self.ax2.set_ylabel("Rain (mm/h)")
        self.ax1.grid(True, linestyle='--', alpha=0.6); self.ax1.legend(handles=[p1, p2, p3, p4]); self.figure.tight_layout(); self.update_theme()
    def clear_plot(self):
        if not MPL_AVAILABLE: return
        self.ax1.clear(); self.ax2.clear(); self.ax1.set_title("No data available"); self.update_theme()