# manual_editor.py
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
import random

class ManualWeatherEditor(tk.Toplevel):
    def __init__(self, parent, parser, sound_manager, original_path, player_start_time):
        super().__init__(parent)
        self.transient(parent)
        self.grab_set()
        self.title("Manual Weather Event Editor")
        self.minsize(800, 600)

        self.parser = parser
        self.sound_manager = sound_manager
        self.original_path = original_path
        self.player_start_time = player_start_time
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
                (0, 10, 50000, 0.0, 1.0, 30, "None"),
            ],
            "Gradual Storm": [
                (0, 20, 30000, 0.0, 1.0, 60, "wind"),
                (1800, 80, 10000, 2.0, 1.0, 1800, "everywhere_light_rain"),
                (3600, 100, 5000, 8.0, 1.0, 1800, "everywhere_heavy_rain"),
                (5400, 100, 3000, 12.0, 1.0, 1800, "thunder"),
                (7200, 70, 15000, 1.0, 1.0, 3600, "wind")
            ],
            "Passing Shower": [
                (0, 30, 25000, 0.0, 1.0, 60, "None"),
                (600, 90, 8000, 5.0, 1.0, 300, "everywhere_medium_rain"),
                (1800, 40, 20000, 0.5, 1.0, 1200, "None"),
            ],
            "Snow Storm": [
                (0, 70, 10000, 1.0, 0.2, 60, "blizzard"),
                (1800, 100, 2000, 8.0, 0.1, 1800, "blizzard"),
                (9000, 80, 5000, 2.0, 0.1, 3600, "wind")
            ]
        }

    def setup_ui(self):
        action_button_frame = ttk.Frame(self)
        action_button_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=10)
        ttk.Button(action_button_frame, text="Generate Manual Activity File", command=self._generate_activity).pack(side=tk.RIGHT, padx=5)
        ttk.Button(action_button_frame, text="Cancel", command=self._cancel).pack(side=tk.RIGHT)

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

        columns = ("time", "overcast", "fog", "precip", "liquidity", "transition", "sound")
        self.tree = ttk.Treeview(tree_frame, columns=columns, show="headings")
        self.tree.heading("time", text="Time (s)"); self.tree.heading("overcast", text="Overcast (%)"); self.tree.heading("fog", text="Fog (m)"); self.tree.heading("precip", text="Precip. (mm/h)"); self.tree.heading("liquidity", text="Liquidity"); self.tree.heading("transition", text="Transition (s)"); self.tree.heading("sound", text="Sound")
        self.tree.column("time", width=80, anchor="center"); self.tree.column("overcast", width=100, anchor="center"); self.tree.column("fog", width=80, anchor="center"); self.tree.column("precip", width=100, anchor="center"); self.tree.column("liquidity", width=80, anchor="center"); self.tree.column("transition", width=100, anchor="center"); self.tree.column("sound", width=120, anchor="center")
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

        self.event_vars = { "time": tk.StringVar(), "overcast": tk.StringVar(), "fog": tk.StringVar(), "precip": tk.StringVar(), "liquidity": tk.StringVar(), "transition": tk.StringVar(), "sound": tk.StringVar() }
        labels = ["Time (seconds)", "Overcast (0-100)", "Fog Distance (meters)", "Precipitation (mm/h)", "Liquidity (0.0 for Snow, 1.0 for Rain)", "Transition Time (seconds)", "Sound Category"]
        keys = ["time", "overcast", "fog", "precip", "liquidity", "transition", "sound"]
        
        sound_categories = ["None"] + sorted(self.sound_manager.sounds.keys())

        for i, (label_text, key) in enumerate(zip(labels, keys)):
            ttk.Label(details_frame, text=f"{label_text}:").grid(row=i + 1, column=0, sticky="w", padx=5, pady=5)
            if key == "sound":
                widget = ttk.Combobox(details_frame, textvariable=self.event_vars[key], values=sound_categories, state="readonly")
            else:
                widget = ttk.Entry(details_frame, textvariable=self.event_vars[key])
            widget.grid(row=i + 1, column=1, sticky="ew", padx=5, pady=5)
        details_frame.grid_columnconfigure(1, weight=1)

        ttk.Button(details_frame, text="Add/Update Event in List", command=self._add_or_update_event).grid(row=len(labels) + 1, column=0, columnspan=2, pady=10)

    def _on_preset_selected(self, preset_name):
        if preset_name == "Select a preset...": return
        if self.tree.get_children() and not messagebox.askyesno("Confirm Overwrite", "Loading a preset will overwrite all current events. Continue?", parent=self):
            self.preset_var.set("Select a preset..."); return
        
        self.tree.delete(*self.tree.get_children())
        for event_data in self.presets[preset_name]:
            adjusted_data = (event_data[0] + self.player_start_time,) + event_data[1:]
            self.tree.insert("", "end", values=adjusted_data)
        self.preset_var.set("Select a preset...")

    def _on_tree_select(self, event):
        selected_items = self.tree.selection()
        if selected_items: self.selected_item = selected_items[0]; self._edit_selected_event()

    def _clear_fields(self):
        for var in self.event_vars.values(): var.set("")
        self.event_vars["sound"].set("None")
        if self.selected_item: self.tree.selection_remove(self.selected_item)
        self.selected_item = None

    def _add_new_event(self):
        self._clear_fields()
        if not self.tree.get_children(): self.event_vars["time"].set(str(self.player_start_time))
        details_frame = self.winfo_children()[1].winfo_children()[1].winfo_children()[0]
        details_frame.winfo_children()[3].focus_set()

    def _edit_selected_event(self):
        if not self.selected_item: return
        values = self.tree.item(self.selected_item, "values")
        keys = ["time", "overcast", "fog", "precip", "liquidity", "transition", "sound"]
        for key, value in zip(keys, values): self.event_vars[key].set(value)

    def _delete_selected_event(self):
        if not self.selected_item: messagebox.showwarning("No Selection", "Please select an event to delete.", parent=self); return
        if messagebox.askyesno("Confirm Deletion", "Are you sure you want to delete the selected event?", parent=self):
            self.tree.delete(self.selected_item); self._clear_fields()

    def _add_or_update_event(self):
        try:
            values = { "time": int(self.event_vars["time"].get()), "overcast": int(self.event_vars["overcast"].get()), "fog": int(self.event_vars["fog"].get()), "precip": float(self.event_vars["precip"].get()), "liquidity": float(self.event_vars["liquidity"].get()), "transition": int(self.event_vars["transition"].get()), "sound": self.event_vars["sound"].get() }
            if not (0 <= values["overcast"] <= 100): raise ValueError("Overcast must be between 0 and 100.")
            if not (0.0 <= values["liquidity"] <= 1.0): raise ValueError("Liquidity must be between 0.0 and 1.0.")
        except ValueError as e: messagebox.showerror("Invalid Input", f"Please enter valid numbers.\n\n{e}", parent=self); return

        formatted_values = (values["time"], values["overcast"], values["fog"], values["precip"], values["liquidity"], values["transition"], values["sound"])
        if self.selected_item: self.tree.item(self.selected_item, values=formatted_values)
        else: self.tree.insert("", "end", values=formatted_values)
        self._clear_fields()

    def _generate_activity(self):
        weather_event_blocks = []; sound_event_blocks = []
        sound_channels = {}; sound_playlists = {}
        global_sound_counter = 0

        items_with_time = [(int(self.tree.item(item, 'values')[0]), item) for item in self.tree.get_children()]
        if not items_with_time: messagebox.showwarning("No Events", "There are no weather events to generate.", parent=self); return
        
        sorted_items = sorted(items_with_time, key=lambda x: x[0])

        for i, (time_val, item_id) in enumerate(sorted_items):
            values = self.tree.item(item_id, 'values')
            time_s, overcast_val, fog_m, precip_mmh, liquidity_val, transition_s, sound_category = values
            time_s, overcast_val, fog_m, precip_mmh, liquidity_val, transition_s = map(float, (time_s, overcast_val, fog_m, precip_mmh, liquidity_val, transition_s))

            weather_block = f"""        EventCategoryTime (
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
            weather_event_blocks.append(weather_block)

            if sound_category and sound_category != "None":
                sound_def = next((s for s in self.sound_manager.sound_definitions if s['category'] == sound_category), None)
                if not sound_def: continue

                start_time = int(time_s)
                end_time = sorted_items[i+1][0] if i + 1 < len(sorted_items) else start_time + 7200 # Default to 2 hours duration
                current_time = start_time

                if sound_def['condition'] == 'thunderstorm': # Handle one-shot sounds
                    if self.sound_manager.sounds.get(sound_category):
                        sound_info = random.choice(self.sound_manager.sounds[sound_category])
                        schedule_time = random.randint(start_time, end_time - int(sound_info['duration']))
                        sound_filename = self.sound_manager.copy_sound_to_route(sound_info['path'], self.parser.content_path)
                        if sound_filename:
                            sound_event_blocks.append(f"""        EventCategoryTime ( ID ( 9{global_sound_counter} ) Name ( WTHLINK_ManualSound_{global_sound_counter} ) Time ( {schedule_time} ) Outcomes ( ORTSActivitySound ( ORTSActSoundFile ( \"{sound_filename}\" {sound_info['sound_type']} ) ) ) )""")
                            global_sound_counter += 1
                else: # Handle continuous sounds
                    sound_channels.setdefault(sound_category, start_time)
                    current_time = max(current_time, sound_channels[sound_category])
                    
                    while current_time < end_time:
                        if not sound_playlists.get(sound_category):
                            all_sounds = self.sound_manager.sounds.get(sound_category, [])
                            if not all_sounds: break
                            sound_playlists[sound_category] = random.sample(all_sounds, len(all_sounds))
                        
                        sound_info = sound_playlists[sound_category].pop()
                        sound_filename = self.sound_manager.copy_sound_to_route(sound_info['path'], self.parser.content_path)
                        if sound_filename:
                            sound_event_blocks.append(f"""        EventCategoryTime ( ID ( 9{global_sound_counter} ) Name ( WTHLINK_ManualSound_{global_sound_counter} ) Time ( {current_time} ) Outcomes ( ORTSActivitySound ( ORTSActSoundFile ( \"{sound_filename}\" {sound_info['sound_type']} ) ) ) )""")
                            global_sound_counter += 1
                            current_time += sound_info['duration']
                    sound_channels[sound_category] = current_time

        event_string = "\n".join(weather_event_blocks + sound_event_blocks)
        new_path, msg = self.parser.modify_and_save_activity(self.original_path, event_string, manual_suffix="MANUAL")
        if new_path:
            messagebox.showinfo("Success", f"New manual activity file created:\n\n{new_path.name}", parent=self)
            self.generation_successful = True
            self.destroy()
        else:
            messagebox.showerror("Error", f"Failed to create activity file:\n\n{msg}", parent=self)

    def _cancel(self):
        self.destroy()