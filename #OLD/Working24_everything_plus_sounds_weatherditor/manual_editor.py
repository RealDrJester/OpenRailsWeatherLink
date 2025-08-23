# manual_editor.py
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from datetime import datetime
import random
import json
from pathlib import Path
import re

class PresetManagerWindow(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.transient(parent)
        self.grab_set()
        self.parent = parent
        self.title("Manage Presets")
        self.geometry("350x300")

        ttk.Label(self, text="Your Custom Presets:").pack(padx=10, pady=(10,0))
        
        list_frame = ttk.Frame(self)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        self.listbox = tk.Listbox(list_frame)
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.listbox.yview)
        self.listbox.config(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.populate_list()

        button_frame = ttk.Frame(self)
        button_frame.pack(fill=tk.X, padx=10, pady=5)
        ttk.Button(button_frame, text="Rename...", command=self.rename_preset).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0,5))
        ttk.Button(button_frame, text="Delete", command=self.delete_preset).pack(side=tk.LEFT, expand=True, fill=tk.X)
        
        ttk.Button(self, text="Close", command=self.destroy).pack(pady=5)

    def populate_list(self):
        self.listbox.delete(0, tk.END)
        for preset_name in sorted(self.parent.user_presets.keys()):
            self.listbox.insert(tk.END, preset_name)

    def rename_preset(self):
        selection = self.listbox.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a preset to rename.", parent=self)
            return
        
        old_name = self.listbox.get(selection[0])
        new_name = simpledialog.askstring("Rename Preset", f"Enter new name for '{old_name}':", parent=self)

        if new_name and new_name != old_name:
            if new_name in self.parent.user_presets:
                messagebox.showerror("Name Exists", "A preset with that name already exists.", parent=self)
                return
            self.parent.user_presets[new_name] = self.parent.user_presets.pop(old_name)
            self.parent._save_user_presets()
            self.populate_list()
            self.parent._refresh_preset_menu()

    def delete_preset(self):
        selection = self.listbox.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a preset to delete.", parent=self)
            return
        
        preset_name = self.listbox.get(selection[0])
        if messagebox.askyesno("Confirm Deletion", f"Are you sure you want to delete the preset '{preset_name}'?", parent=self):
            del self.parent.user_presets[preset_name]
            self.parent._save_user_presets()
            self.populate_list()
            self.parent._refresh_preset_menu()

class ManualWeatherEditor(tk.Toplevel):
    def __init__(self, parent, parser, sound_manager, original_path, player_start_time, initial_season):
        super().__init__(parent)
        self.transient(parent); self.grab_set()
        self.title("Manual Weather Event Editor"); self.minsize(800, 600)

        self.parser = parser; self.sound_manager = sound_manager; self.original_path = original_path
        self.player_start_time = player_start_time
        self.initial_season_val = initial_season
        self.generation_successful = False; self.result_string = None; self.selected_item = None
        self.user_presets_path = Path("user_presets.json")
        
        self._define_presets()
        self._load_user_presets()
        self.setup_ui()
        self.protocol("WM_DELETE_WINDOW", self._cancel)

    def _define_presets(self):
        self.presets = {
            "Clear Day": {"season": 1, "events": [(0, 10, 50000, 0.0, 1.0, 30, "None")]},
            "Gradual Storm": {"season": 0, "events": [(0, 20, 30000, 0.0, 1.0, 60, "wind"), (1800, 80, 10000, 2.0, 1.0, 1800, "everywhere_light_rain"), (3600, 100, 5000, 8.0, 1.0, 1800, "everywhere_heavy_rain"), (5400, 100, 3000, 12.0, 1.0, 1800, "thunder"), (7200, 70, 15000, 1.0, 1.0, 3600, "wind")]},
            "Passing Shower": {"season": 2, "events": [(0, 30, 25000, 0.0, 1.0, 60, "None"), (600, 90, 8000, 5.0, 1.0, 300, "everywhere_medium_rain"), (1800, 40, 20000, 0.5, 1.0, 1200, "None")]},
            "Snow Storm": {"season": 3, "events": [(0, 70, 10000, 1.0, 0.2, 60, "blizzard"), (1800, 100, 2000, 8.0, 0.1, 1800, "blizzard"), (9000, 80, 5000, 2.0, 0.1, 3600, "wind")]}
        }

    def _load_user_presets(self):
        self.user_presets = {}
        if self.user_presets_path.exists():
            try:
                with open(self.user_presets_path, 'r') as f: self.user_presets = json.load(f)
            except (json.JSONDecodeError, OSError):
                self.user_presets = {}

    def _save_user_presets(self):
        try:
            with open(self.user_presets_path, 'w') as f: json.dump(self.user_presets, f, indent=4)
        except OSError:
            messagebox.showerror("Error", "Could not save user presets.", parent=self)
            
    def _refresh_preset_menu(self):
        menu = self.preset_menu["menu"]
        menu.delete(0, "end")
        
        all_presets = ["Select a preset..."] + sorted(self.presets.keys())
        if self.user_presets:
            all_presets.append("--- My Presets ---")
            all_presets.extend(sorted(self.user_presets.keys()))

        self.preset_var.set("Select a preset...")
        for preset_name in all_presets:
            if "---" in preset_name:
                menu.add_separator()
            else:
                menu.add_command(label=preset_name, command=lambda value=preset_name: self._on_preset_selected(value))

    def setup_ui(self):
        action_button_frame = ttk.Frame(self); action_button_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=10)
        ttk.Button(action_button_frame, text="Generate Manual Activity File", command=self._generate_activity).pack(side=tk.RIGHT, padx=5)
        ttk.Button(action_button_frame, text="Cancel", command=self._cancel).pack(side=tk.RIGHT)

        main_paned = ttk.PanedWindow(self, orient=tk.VERTICAL); main_paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=(10, 0))
        top_pane = ttk.Frame(main_paned); main_paned.add(top_pane, weight=3); top_pane.grid_columnconfigure(0, weight=1); top_pane.grid_rowconfigure(0, weight=1)
        tree_frame = ttk.Frame(top_pane); tree_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 5)); tree_frame.grid_rowconfigure(0, weight=1); tree_frame.grid_columnconfigure(0, weight=1)

        columns = ("time", "overcast", "fog", "precip", "liquidity", "transition", "sound"); self.tree = ttk.Treeview(tree_frame, columns=columns, show="headings")
        self.tree.heading("time", text="Time (s)"); self.tree.heading("overcast", text="Overcast (%)"); self.tree.heading("fog", text="Fog (m)"); self.tree.heading("precip", text="Precip. (mm/h)"); self.tree.heading("liquidity", text="Liquidity"); self.tree.heading("transition", text="Transition (s)"); self.tree.heading("sound", text="Sound")
        self.tree.column("time", width=80, anchor="center"); self.tree.column("overcast", width=100, anchor="center"); self.tree.column("fog", width=80, anchor="center"); self.tree.column("precip", width=100, anchor="center"); self.tree.column("liquidity", width=80, anchor="center"); self.tree.column("transition", width=100, anchor="center"); self.tree.column("sound", width=120, anchor="center")
        self.tree.grid(row=0, column=0, sticky="nsew"); self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)

        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview); self.tree.configure(yscrollcommand=scrollbar.set); scrollbar.grid(row=0, column=1, sticky="ns")
        tree_buttons_frame = ttk.Frame(top_pane); tree_buttons_frame.grid(row=0, column=1, sticky="ns", padx=(5, 0))
        ttk.Button(tree_buttons_frame, text="Add New Event", command=self._add_new_event).pack(fill=tk.X, pady=2)
        ttk.Button(tree_buttons_frame, text="Edit Selected Event", command=self._edit_selected_event).pack(fill=tk.X, pady=2)
        ttk.Button(tree_buttons_frame, text="Delete Selected Event", command=self._delete_selected_event).pack(fill=tk.X, pady=2)

        bottom_pane = ttk.Frame(main_paned); main_paned.add(bottom_pane, weight=2)
        details_frame = ttk.LabelFrame(bottom_pane, text="Event Details", padding=10); details_frame.pack(fill=tk.BOTH, expand=True)

        season_frame = ttk.Frame(details_frame); season_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        ttk.Label(season_frame, text="Activity Season:").pack(side=tk.LEFT, padx=(5, 10))
        self.season_var = tk.StringVar()
        seasons = ["Spring (0)", "Summer (1)", "Autumn (2)", "Winter (3)"]
        self.season_menu = ttk.Combobox(season_frame, textvariable=self.season_var, values=seasons, state="readonly"); self.season_menu.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.season_menu.set(seasons[self.initial_season_val])

        preset_frame = ttk.Frame(details_frame); preset_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0,10))
        ttk.Label(preset_frame, text="Load Preset:").pack(side=tk.LEFT, padx=(5,10)); self.preset_var = tk.StringVar(value="Select a preset...")
        self.preset_menu = ttk.OptionMenu(preset_frame, self.preset_var, "Select a preset..."); self.preset_menu.pack(side=tk.LEFT, fill=tk.X, expand=True); self._refresh_preset_menu()
        ttk.Button(preset_frame, text="Save Current as Preset...", command=self._save_preset).pack(side=tk.LEFT, padx=(5,0))
        ttk.Button(preset_frame, text="Manage Presets...", command=self._manage_presets).pack(side=tk.LEFT, padx=(5,0))
        
        self.event_vars = { "time": tk.StringVar(), "overcast": tk.StringVar(), "fog": tk.StringVar(), "precip": tk.StringVar(), "liquidity": tk.StringVar(), "transition": tk.StringVar(), "sound": tk.StringVar() }
        labels = ["Time (seconds)", "Overcast (0-100)", "Fog Distance (meters)", "Precipitation (mm/h)", "Liquidity (0.0 for Snow, 1.0 for Rain)", "Transition Time (seconds)", "Sound Category"]
        keys = ["time", "overcast", "fog", "precip", "liquidity", "transition", "sound"]
        sound_categories = ["None"] + sorted(self.sound_manager.sounds.keys())

        for i, (label_text, key) in enumerate(zip(labels, keys)):
            ttk.Label(details_frame, text=f"{label_text}:").grid(row=i + 2, column=0, sticky="w", padx=5, pady=5)
            widget = ttk.Combobox(details_frame, textvariable=self.event_vars[key], values=sound_categories, state="readonly") if key == "sound" else ttk.Entry(details_frame, textvariable=self.event_vars[key])
            widget.grid(row=i + 2, column=1, sticky="ew", padx=5, pady=5)
        details_frame.grid_columnconfigure(1, weight=1)
        ttk.Button(details_frame, text="Add/Update Event in List", command=self._add_or_update_event).grid(row=len(labels) + 2, column=0, columnspan=2, pady=10)

    def _on_preset_selected(self, preset_name):
        self.preset_var.set(preset_name)
        if preset_name == "Select a preset..." or "---" in preset_name: return
        if self.tree.get_children() and not messagebox.askyesno("Confirm Overwrite", "Loading a preset will overwrite all current events. Continue?", parent=self):
            self.preset_var.set("Select a preset..."); return
        
        self.tree.delete(*self.tree.get_children())
        preset_data = self.presets.get(preset_name) or self.user_presets.get(preset_name)
        
        season_val = preset_data.get("season", self.initial_season_val)
        # --- FIX: Use the widget's ['values'] property to get the list ---
        self.season_var.set(self.season_menu['values'][season_val])

        for event_data in preset_data["events"]:
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
        self.winfo_children()[1].winfo_children()[1].winfo_children()[0].winfo_children()[5].focus_set()

    def _edit_selected_event(self):
        if not self.selected_item: return
        values = self.tree.item(self.selected_item, "values"); keys = ["time", "overcast", "fog", "precip", "liquidity", "transition", "sound"]
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

    def _save_preset(self):
        if not self.tree.get_children(): messagebox.showwarning("No Events", "There is no weather sequence to save.", parent=self); return
        
        name = simpledialog.askstring("Save Preset", "Enter a name for this preset:", parent=self)
        if not name: return
        if name in self.presets or name in self.user_presets:
            if not messagebox.askyesno("Confirm Overwrite", "A preset with this name already exists. Overwrite it?", parent=self): return
        
        event_data = []
        for item_id in self.tree.get_children():
            values = self.tree.item(item_id, 'values')
            time_val = int(values[0])
            relative_time = time_val - self.player_start_time
            event_data.append((relative_time,) + values[1:])
        
        season_str = self.season_var.get()
        season_val = int(re.search(r'\((\d)\)', season_str).group(1))

        self.user_presets[name] = {"season": season_val, "events": event_data}
        self._save_user_presets()
        self._refresh_preset_menu()
        messagebox.showinfo("Success", f"Preset '{name}' saved successfully.", parent=self)

    def _manage_presets(self):
        PresetManagerWindow(self)

    def _generate_activity(self):
        weather_event_blocks, sound_event_blocks = [], []
        sound_channels, sound_playlists = {}, {}
        global_sound_counter = 0

        items_with_time = [(int(self.tree.item(item, 'values')[0]), item) for item in self.tree.get_children()]
        if not items_with_time: messagebox.showwarning("No Events", "There are no weather events to generate.", parent=self); return
        sorted_items = sorted(items_with_time, key=lambda x: x[0])

        for i, (time_val, item_id) in enumerate(sorted_items):
            values = self.tree.item(item_id, 'values')
            time_s, overcast_val, fog_m, precip_mmh, liquidity_val, transition_s, sound_category = values
            time_s, overcast_val, fog_m, precip_mmh, liquidity_val, transition_s = map(float, (time_s, overcast_val, fog_m, precip_mmh, liquidity_val, transition_s))
            weather_event_blocks.append(f"""        EventCategoryTime ( ID ( {1000 + i} ) Name ( WTHLINK_Manual_{i} ) Time ( {int(time_s)} ) Outcomes ( ORTSWeatherChange ( ORTSOvercast ( {overcast_val / 100.0:.2f} {int(transition_s)} ) ORTSFog ( {int(fog_m)} {int(transition_s)} ) ORTSPrecipitationIntensity ( {precip_mmh / 1000.0:.5f} {int(transition_s)} ) ORTSPrecipitationLiquidity ( {liquidity_val:.1f} {int(transition_s)} ) ) ) )""")

            if sound_category and sound_category != "None":
                sound_def = next((s for s in self.sound_manager.sound_definitions if s['category'] == sound_category), None)
                if not sound_def: continue
                start_time, end_time = int(time_s), sorted_items[i+1][0] if i + 1 < len(sorted_items) else int(time_s) + 7200
                if sound_def['condition'] == 'thunderstorm':
                    if self.sound_manager.sounds.get(sound_category):
                        sound_info = random.choice(self.sound_manager.sounds[sound_category])
                        if end_time > start_time + sound_info['duration']:
                            schedule_time = random.randint(start_time, int(end_time - sound_info['duration']))
                            sound_filename = self.sound_manager.copy_sound_to_route(sound_info['path'], self.parser.content_path)
                            if sound_filename:
                                sound_event_blocks.append(f"""        EventCategoryTime ( ID ( 9{global_sound_counter} ) Name ( WTHLINK_ManualSound_{global_sound_counter} ) Time ( {schedule_time} ) Outcomes ( ORTSActivitySound ( ORTSActSoundFile ( \"{sound_filename}\" {sound_info['sound_type']} ) ) ) )""")
                                global_sound_counter += 1
                else:
                    sound_channels.setdefault(sound_category, start_time)
                    current_time = max(start_time, sound_channels[sound_category])
                    while current_time < end_time:
                        if not sound_playlists.get(sound_category) or not sound_playlists[sound_category]:
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
        
        season_str = self.season_var.get()
        season_val = int(re.search(r'\((\d)\)', season_str).group(1))

        event_string = "\n".join(weather_event_blocks + sound_event_blocks)
        new_path, msg = self.parser.modify_and_save_activity(self.original_path, event_string, manual_suffix="MANUAL", season=season_val)
        if new_path:
            messagebox.showinfo("Success", f"New manual activity file created:\n\n{new_path.name}", parent=self); self.generation_successful = True; self.destroy()
        else:
            messagebox.showerror("Error", f"Failed to create activity file:\n\n{msg}", parent=self)

    def _cancel(self):
        self.destroy()