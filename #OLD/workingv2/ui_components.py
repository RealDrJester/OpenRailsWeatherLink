# ui_components.py
import tkinter as tk
from tkinter import ttk
import sv_ttk

# Add matplotlib imports
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
        self.geometry("350x200")
        self.transient(parent)
        self.grab_set()

        main_frame = ttk.Frame(self, padding="20")
        main_frame.pack(expand=True, fill="both")

        ttk.Label(main_frame, text="ORTS WeatherLink", font=("", 14, "bold")).pack(pady=(0, 5))
        ttk.Label(main_frame, text="Version 1.1").pack()
        ttk.Label(main_frame, text="Real-world weather injector for Open Rails.").pack(pady=(0, 15))
        ttk.Label(main_frame, text="Developed with your valuable feedback.").pack()

        close_button = ttk.Button(main_frame, text="Close", command=self.destroy)
        close_button.pack(pady=(15, 0))


class ForecastChart(ttk.Frame):
    """A frame containing a matplotlib chart for weather data."""
    def __init__(self, parent):
        super().__init__(parent)
        
        if not MPL_AVAILABLE:
            ttk.Label(self, text="Matplotlib not found.\nPlease run: pip install matplotlib").pack(expand=True)
            return

        self.figure = Figure(figsize=(5, 4), dpi=100)
        self.ax = self.figure.add_subplot(111)
        
        self.canvas = FigureCanvasTkAgg(self.figure, self)
        self.canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.update_theme()

    def update_theme(self):
        if not MPL_AVAILABLE: return
        
        is_dark = sv_ttk.get_theme() == "dark"
        bg_color = '#2B2B2B' if is_dark else '#F0F0F0'
        text_color = 'white' if is_dark else 'black'
        
        self.figure.patch.set_facecolor(bg_color)
        self.ax.set_facecolor('#3C3C3C' if is_dark else 'white')
        self.ax.tick_params(axis='x', colors=text_color)
        self.ax.tick_params(axis='y', colors=text_color)
        self.ax.spines['left'].set_color(text_color)
        self.ax.spines['right'].set_color(text_color)
        self.ax.spines['top'].set_color(text_color)
        self.ax.spines['bottom'].set_color(text_color)
        self.ax.title.set_color(text_color)
        self.ax.xaxis.label.set_color(text_color)
        self.ax.yaxis.label.set_color(text_color)
        
        legend = self.ax.get_legend()
        if legend:
            legend.get_frame().set_facecolor(bg_color)
            for text in legend.get_texts():
                text.set_color(text_color)
        self.canvas.draw()


    def plot_data(self, hourly_data):
        if not MPL_AVAILABLE: return

        self.ax.clear()
        
        times = [t[-5:] for t in hourly_data['time'][:12]]
        temps = hourly_data['temperature_2m'][:12]
        clouds = hourly_data['cloudcover'][:12]
        winds = hourly_data['windspeed_10m'][:12]
        
        self.ax.plot(times, temps, marker='o', linestyle='-', label='Temp (°C)', color='#FF7F0E')
        self.ax.plot(times, clouds, marker='s', linestyle='--', label='Cloud Cover (%)', color='#1F77B4')
        self.ax.plot(times, winds, marker='^', linestyle=':', label='Wind (km/h)', color='#2CA02C')
        
        self.ax.set_title("12-Hour Forecast")
        self.ax.set_xlabel("Time")
        self.ax.grid(True, linestyle='--', alpha=0.6)
        self.ax.legend()
        self.figure.tight_layout()
        self.update_theme() # Apply theme colors after plotting

    def clear_plot(self):
        if not MPL_AVAILABLE: return
        self.ax.clear()
        self.ax.set_title("No data available")
        self.update_theme()