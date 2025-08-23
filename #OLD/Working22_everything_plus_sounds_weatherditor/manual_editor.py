# manual_editor.py
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime

class ManualWeatherEditor(tk.Toplevel):
    def __init__(self, parent, parser, original_path):
        super().__init__(parent)
        self.transient(parent)
        self.grab_set()
        self.title("Manual Weather Event Editor")
        self.geometry("800x600")

        self.parser = parser
        self.original_path = original_path
        self.generation_successful = False
        self.result_string = None
        self.selected_item = None

        self._define_presets()
        self.setup_ui()
        self.protocol("WM_DELETE_WINDOW", self._cancel)

    def _define_presets(self):
        self.presets = {
            "Select a preset...": [],
            "Clear Day": [
                (0, 10, 50000, 0.0, 1.0, 30),
                (7200, 5, 60000, 0.0, 1.0, 1800)
            ],
            "Gradual Storm": [
                (0, 20, 30000, 0.0, 1.0, 60),
                (1800, 50, 20000, 0.1, 1.0, 1800),
                (3600, 80, 10000, 2.0, 1.0, 1800),
                (5400, 100, 5000, 8.0, 1.0, 1800),
                (7200, 70, 15000, 1.0, 1.0, 3600)
            ],
            "Passing Shower": [
                (0, 30, 25000, 0.0, 1.0, 60),
                (600, 90, 8000, 5.0, 1.0, 300),
                (1800, 100, 3000, 10.0, 1.0, 600),
                (2400, 40, 20000, 0.5, 1.0, 1200),
                (3600, 20, 40000, 0.0, 1.0, 1800)
            ],
            "Snow Storm": [
                (0, 70, 10000, 1.0, 0.2, 60),
                (1800, 100, 2000, 8.0, 0.1, 1800),
                (5400, 100, 1000, 12.0, 0.0, 1800),
                (9000, 80, 5000, 2.0, 0.1, 3600)
            ]
        }

    def setup_ui(self):
        main_paned = ttk.PanedWindow(self, orient=tk.VERTICAL)
        main_paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=(10, 0))

        top_pane = ttk.Frame(main_paned)
        main_paned.add(top_pane, weight=3)
        top_pane.grid_columnconfigure(0, weight=1)
        top_pane.grid_rowconfigure(0, weight=1)

        tree_frame = ttk.Frame(top_pane)
        tree_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

        columns = ("time", "overcast", "fog", "precip", "liquidity", "transition")
        self.tree = ttk.Treeview(tree_frame, columns=columns, show="headings")
        self.tree.heading("time", text="Time (s)"); self.tree.heading("overcast", text="Overcast (%)"); self.tree.heading("fog", text="Fog (m)"); self.tree.heading("precip", text="Precip. (mm/h)"); self.tree.heading("liquidity", text="Liquidity"); self.tree.heading("transition", text="Transition (s)")
        self.tree.column("time", width=80, anchor="center"); self.tree.column("overcast", width=100, anchor="center"); self.tree.column("fog", width=80, anchor="center"); self.tree.column("precip", width=100, anchor="center"); self.tree.column("liquidity", width=80, anchor="center"); self.tree.column("transition", width=100, anchor="center")
        self.tree.grid(row=0, column=0, sticky="nsew")
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)

        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.grid(row=0, column=1, sticky="ns")

        tree_buttons_frame = ttk.Frame(top_pane)
        tree_buttons_frame.grid(row=0, column=1, sticky="ns", padx=(5, 0))
        ttk.Button(tree_buttons_frame, text="Add New Event", command=self._add_new_event).pack(fill=tk.X, pady=2)
        ttk.Button(tree_buttons_frame, text="Edit Selected Event", command=self._edit_selected_event).pack(fill=tk.X, pady=2)
        ttk.Button(tree_buttons_frame, text="Delete Selected Event", command=self._delete_selected_event).pack(fill=tk.X, pady=2)

        bottom_pane = ttk.Frame(main_paned)
        main_paned.add(bottom_pane, weight=2)
        
        details_frame = ttk.LabelFrame(bottom_pane, text="Event Details", padding=10)
        details_frame.pack(fill=tk.BOTH, expand=True)

        preset_frame = ttk.Frame(details_frame)
        preset_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0,10))
        ttk.Label(preset_frame, text="Load Preset:").pack(side=tk.LEFT, padx=(5,10))
        self.preset_var = tk.StringVar(value="Select a preset...")
        preset_menu = ttk.OptionMenu(preset_frame, self.preset_var, *self.presets.keys(), command=self._on_preset_selected)
        preset_menu.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.event_vars = { "time": tk.StringVar(), "overcast": tk.StringVar(), "fog": tk.StringVar(), "precip": tk.StringVar(), "liquidity": tk.StringVar(), "transition": tk.StringVar() }
        labels = ["Time (seconds)", "Overcast (0-100)", "Fog Distance (meters)", "Precipitation (mm/h)", "Liquidity (0.0 for Snow, 1.0 for Rain)", "Transition Time (seconds)"]
        keys = ["time", "overcast", "fog", "precip", "liquidity", "transition"]

        for i, (label_text, key) in enumerate(zip(labels, keys)):
            ttk.Label(details_frame, text=f"{label_text}:").grid(row=i + 1, column=0, sticky="w", padx=5, pady=5)
            entry = ttk.Entry(details_frame, textvariable=self.event_vars[key])
            entry.grid(row=i + 1, column=1, sticky="ew", padx=5, pady=5)
        details_frame.grid_columnconfigure(1, weight=1)

        ttk.Button(details_frame, text="Add/Update Event in List", command=self._add_or_update_event).grid(row=len(labels) + 1, column=0, columnspan=2, pady=10)

        action_button_frame = ttk.Frame(self)
        action_button_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Button(action_button_frame, text="Generate Manual Activity File", command=self._generate_activity).pack(side=tk.RIGHT, padx=5)
        ttk.Button(action_button_frame, text="Cancel", command=self._cancel).pack(side=tk.RIGHT)

    def _on_preset_selected(self, preset_name):
        if preset_name == "Select a preset...":
            return
        if self.tree.get_children():
            if not messagebox.askyesno("Confirm Overwrite", "Loading a preset will overwrite all current events. Continue?", parent=self):
                self.preset_var.set("Select a preset...")
                return
        
        self.tree.delete(*self.tree.get_children())
        for event_data in self.presets[preset_name]:
            self.tree.insert("", "end", values=event_data)
        self.preset_var.set("Select a preset...")

    def _on_tree_select(self, event):
        selected_items = self.tree.selection()
        if selected_items: self.selected_item = selected_items[0]; self._edit_selected_event()

    def _clear_fields(self):
        for var in self.event_vars.values(): var.set("")
        if self.selected_item: self.tree.selection_remove(self.selected_item)
        self.selected_item = None

    def _add_new_event(self):
        self._clear_fields()
        details_frame = self.winfo_children()[0].winfo_children()[1].winfo_children()[0]
        details_frame.winfo_children()[3].focus_set()

    def _edit_selected_event(self):
        if not self.selected_item: return
        values = self.tree.item(self.selected_item, "values")
        keys = ["time", "overcast", "fog", "precip", "liquidity", "transition"]
        for key, value in zip(keys, values): self.event_vars[key].set(value)

    def _delete_selected_event(self):
        if not self.selected_item: messagebox.showwarning("No Selection", "Please select an event to delete.", parent=self); return
        if messagebox.askyesno("Confirm Deletion", "Are you sure you want to delete the selected event?", parent=self):
            self.tree.delete(self.selected_item); self._clear_fields()

    def _add_or_update_event(self):
        try:
            values = { "time": int(self.event_vars["time"].get()), "overcast": int(self.event_vars["overcast"].get()), "fog": int(self.event_vars["fog"].get()), "precip": float(self.event_vars["precip"].get()), "liquidity": float(self.event_vars["liquidity"].get()), "transition": int(self.event_vars["transition"].get()) }
            if not (0 <= values["overcast"] <= 100): raise ValueError("Overcast must be between 0 and 100.")
            if not (0.0 <= values["liquidity"] <= 1.0): raise ValueError("Liquidity must be between 0.0 and 1.0.")
        except ValueError as e: messagebox.showerror("Invalid Input", f"Please enter valid numbers.\n\n{e}", parent=self); return

        formatted_values = (values["time"], values["overcast"], values["fog"], values["precip"], values["liquidity"], values["transition"])
        if self.selected_item: self.tree.item(self.selected_item, values=formatted_values)
        else: self.tree.insert("", "end", values=formatted_values)
        self._clear_fields()

    def _generate_activity(self):
        event_blocks = []
        items_with_time = [(int(self.tree.item(item, 'values')[0]), item) for item in self.tree.get_children()]
        sorted_items = sorted(items_with_time, key=lambda x: x[0])

        for i, (time_val, item_id) in enumerate(sorted_items):
            values = self.tree.item(item_id, 'values')
            time_s, overcast_val, fog_m, precip_mmh, liquidity_val, transition_s = map(float, values)
            event_block = f"""        EventCategoryTime (
            EventTypeTime ( )
            ID ( {1000 + i} )
            Activation_Level ( 1 )
            Name ( WTHLINK_Manual_{i} )
            Time ( {int(time_s)} )
            Outcomes (
                ORTSWeatherChange (
                    ORTSOvercast ( {overcast_val / 100.0:.2f} {int(transition_s)} )
                    ORTSFog ( {int(fog_m)} {int(transition_s)} )
                    ORTSPrecipitationIntensity ( {precip_mmh / 1000.0:.5f} {int(transition_s)} )
                    ORTSPrecipitationLiquidity ( {liquidity_val:.1f} {int(transition_s)} )
                )
            )
        )"""
            event_blocks.append(event_block)
        
        event_string = "\n".join(event_blocks)
        new_path, msg = self.parser.modify_and_save_activity(self.original_path, event_string, manual_suffix="MANUAL")
        if new_path:
            messagebox.showinfo("Success", f"New manual activity file created:\n\n{new_path.name}", parent=self)
            self.generation_successful = True
            self.destroy()
        else:
            messagebox.showerror("Error", f"Failed to create activity file:\n\n{msg}", parent=self)

    def _cancel(self):
        self.destroy()