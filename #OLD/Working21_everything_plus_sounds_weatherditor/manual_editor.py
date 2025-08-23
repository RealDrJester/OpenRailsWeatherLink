# manual_editor.py
import tkinter as tk
from tkinter import ttk, messagebox

class ManualWeatherEditor(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.transient(parent)
        self.grab_set()
        self.title("Manual Weather Event Editor")
        self.geometry("800x600")

        self.result_string = None
        self.selected_item = None

        self.setup_ui()
        self.protocol("WM_DELETE_WINDOW", self._cancel)

    def setup_ui(self):
        # --- Main Paned Window ---
        main_paned = ttk.PanedWindow(self, orient=tk.VERTICAL)
        main_paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=(10, 0))

        # --- Top Pane (Event List) ---
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

        # Define headings
        self.tree.heading("time", text="Time (s)")
        self.tree.heading("overcast", text="Overcast (%)")
        self.tree.heading("fog", text="Fog (m)")
        self.tree.heading("precip", text="Precip. (mm/h)")
        self.tree.heading("liquidity", text="Liquidity")
        self.tree.heading("transition", text="Transition (s)")

        # Define column properties
        self.tree.column("time", width=80, anchor="center")
        self.tree.column("overcast", width=100, anchor="center")
        self.tree.column("fog", width=80, anchor="center")
        self.tree.column("precip", width=100, anchor="center")
        self.tree.column("liquidity", width=80, anchor="center")
        self.tree.column("transition", width=100, anchor="center")

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

        # --- Bottom Pane (Editing Area) ---
        bottom_pane = ttk.Frame(main_paned)
        main_paned.add(bottom_pane, weight=2)
        
        details_frame = ttk.LabelFrame(bottom_pane, text="Event Details", padding=10)
        details_frame.pack(fill=tk.BOTH, expand=True)

        self.event_vars = {
            "time": tk.StringVar(), "overcast": tk.StringVar(), "fog": tk.StringVar(),
            "precip": tk.StringVar(), "liquidity": tk.StringVar(), "transition": tk.StringVar()
        }

        labels = ["Time (seconds)", "Overcast (0-100)", "Fog Distance (meters)", 
                  "Precipitation (mm/h)", "Liquidity (0.0 for Snow, 1.0 for Rain)", "Transition Time (seconds)"]
        keys = ["time", "overcast", "fog", "precip", "liquidity", "transition"]

        for i, (label_text, key) in enumerate(zip(labels, keys)):
            ttk.Label(details_frame, text=f"{label_text}:").grid(row=i, column=0, sticky="w", padx=5, pady=5)
            entry = ttk.Entry(details_frame, textvariable=self.event_vars[key])
            entry.grid(row=i, column=1, sticky="ew", padx=5, pady=5)
        details_frame.grid_columnconfigure(1, weight=1)

        ttk.Button(details_frame, text="Add/Update Event in List", command=self._add_or_update_event).grid(row=len(labels), column=0, columnspan=2, pady=10)

        # --- Main Action Buttons ---
        action_button_frame = ttk.Frame(self)
        action_button_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Button(action_button_frame, text="Generate Events", command=self._generate_events).pack(side=tk.RIGHT, padx=5)
        ttk.Button(action_button_frame, text="Cancel", command=self._cancel).pack(side=tk.RIGHT)

    def _on_tree_select(self, event):
        selected_items = self.tree.selection()
        if selected_items:
            self.selected_item = selected_items[0]
            self._edit_selected_event()

    def _clear_fields(self):
        for var in self.event_vars.values():
            var.set("")
        if self.selected_item:
            self.tree.selection_remove(self.selected_item)
        self.selected_item = None

    def _add_new_event(self):
        self._clear_fields()
        # Find the first entry widget to set focus
        for child in self.winfo_children():
            if isinstance(child, ttk.PanedWindow):
                bottom_pane = child.panes()[1]
                details_frame = child.nametowidget(bottom_pane).winfo_children()[0]
                details_frame.winfo_children()[1].focus_set()
                break

    def _edit_selected_event(self):
        if not self.selected_item:
            return
        
        values = self.tree.item(self.selected_item, "values")
        keys = ["time", "overcast", "fog", "precip", "liquidity", "transition"]
        for key, value in zip(keys, values):
            self.event_vars[key].set(value)

    def _delete_selected_event(self):
        if not self.selected_item:
            messagebox.showwarning("No Selection", "Please select an event to delete.", parent=self)
            return
        
        if messagebox.askyesno("Confirm Deletion", "Are you sure you want to delete the selected event?", parent=self):
            self.tree.delete(self.selected_item)
            self._clear_fields()

    def _add_or_update_event(self):
        try:
            values = {
                "time": int(self.event_vars["time"].get()),
                "overcast": int(self.event_vars["overcast"].get()),
                "fog": int(self.event_vars["fog"].get()),
                "precip": float(self.event_vars["precip"].get()),
                "liquidity": float(self.event_vars["liquidity"].get()),
                "transition": int(self.event_vars["transition"].get())
            }
            
            # Additional validation
            if not (0 <= values["overcast"] <= 100):
                raise ValueError("Overcast must be between 0 and 100.")
            if not (0.0 <= values["liquidity"] <= 1.0):
                raise ValueError("Liquidity must be between 0.0 and 1.0.")

        except ValueError as e:
            messagebox.showerror("Invalid Input", f"Please enter valid numbers.\n\n{e}", parent=self)
            return

        formatted_values = (values["time"], values["overcast"], values["fog"], 
                            values["precip"], values["liquidity"], values["transition"])

        if self.selected_item:
            self.tree.item(self.selected_item, values=formatted_values)
        else:
            self.tree.insert("", "end", values=formatted_values)
        
        self._clear_fields()

    def _generate_events(self):
        event_blocks = []
        all_items = self.tree.get_children()
        
        # Sort items by time before generating
        items_with_time = []
        for item in all_items:
            values = self.tree.item(item, 'values')
            items_with_time.append((int(values[0]), item))
        
        sorted_items = sorted(items_with_time, key=lambda x: x[0])

        for i, (time_val, item_id) in enumerate(sorted_items):
            values = self.tree.item(item_id, 'values')
            
            time_s = int(values[0])
            overcast_val = int(values[1]) / 100.0
            fog_m = int(values[2])
            precip_mmh = float(values[3]) / 1000.0
            liquidity_val = float(values[4])
            transition_s = int(values[5])

            event_block = f"""        EventCategoryTime (
            EventTypeTime ( )
            ID ( {1000 + i} )
            Activation_Level ( 1 )
            Name ( WTHLINK_Manual_{i} )
            Time ( {time_s} )
            Outcomes (
                ORTSWeatherChange (
                    ORTSOvercast ( {overcast_val:.2f} {transition_s} )
                    ORTSFog ( {fog_m} {transition_s} )
                    ORTSPrecipitationIntensity ( {precip_mmh:.5f} {transition_s} )
                    ORTSPrecipitationLiquidity ( {liquidity_val:.1f} {transition_s} )
                )
            )
        )"""
            event_blocks.append(event_block)
        
        self.result_string = "\n".join(event_blocks)
        self.destroy()

    def _cancel(self):
        self.result_string = None
        self.destroy()