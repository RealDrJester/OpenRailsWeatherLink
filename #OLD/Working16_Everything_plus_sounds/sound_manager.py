# sound_manager.py
import wave
import contextlib
from pathlib import Path
import random
import shutil
import json

class SoundManager:
    def __init__(self, log_callback=print):
        self.log = log_callback
        self.base_path = Path("user_sounds")
        self.sound_definitions = []
        self.sounds = {}
        self.copied_sounds = set()
        self.log("[Debug] SoundManager initialized.")
        self._load_definitions()
        self._discover_sounds()

    def _load_definitions(self):
        definitions_path = Path("sounds.json")
        self.log(f"[Debug] Loading sound definitions from '{definitions_path}'")
        if not definitions_path.exists():
            self.log(f"[ERROR] CRITICAL: '{definitions_path}' not found. No sounds will be loaded.")
            return
        try:
            with open(definitions_path, 'r') as f:
                self.sound_definitions = json.load(f)
            self.log(f"[Info] Loaded {len(self.sound_definitions)} sound definitions.")
        except json.JSONDecodeError as e:
            self.log(f"[ERROR] CRITICAL: Failed to parse '{definitions_path}'. Error: {e}")
        except Exception as e:
            self.log(f"[ERROR] CRITICAL: Could not read '{definitions_path}'. Reason: {e}")

    def _discover_sounds(self):
        self.log("[Debug] Discovering user sound files based on definitions...")
        if not self.base_path.is_dir():
            self.log(f"[Info] User sounds directory not found. Creating at: '{self.base_path.resolve()}'")
            self.base_path.mkdir()
        
        for definition in self.sound_definitions:
            category = definition.get("category")
            pattern = definition.get("pattern")
            if not category or not pattern:
                continue

            self.sounds[category] = [] # Initialize category
            self.log(f"[Debug] Searching for '{pattern}' for category '{category}'")
            found_files = list(self.base_path.glob(pattern))
            
            for sound_file in found_files:
                duration = self._get_wav_duration(sound_file)
                if duration:
                    self.sounds[category].append({
                        "path": sound_file,
                        "duration": duration,
                        "sound_type": definition.get("sound_type", "Everywhere")
                    })
            self.log(f"[Info] Found {len(self.sounds[category])} file(s) for category '{category}'.")

    def _get_wav_duration(self, wav_path):
        try:
            with contextlib.closing(wave.open(str(wav_path), 'r')) as f:
                frames = f.getnframes()
                rate = f.getframerate()
                return frames / float(rate)
        except wave.Error as e:
            self.log(f"[ERROR] Could not read .wav file: {wav_path.name} - {e}")
            return None

    def get_sounds_for_condition(self, condition):
        matching_sounds = []
        for definition in self.sound_definitions:
            if definition.get("condition") == condition:
                category = definition["category"]
                if self.sounds.get(category):
                    matching_sounds.append(category)
        return matching_sounds

    def get_random_sound(self, category):
        if not self.sounds.get(category):
            self.log(f"[Debug] No sounds available for category '{category}'. Cannot select a sound.")
            return None
        sound_info = random.choice(self.sounds[category])
        self.log(f"[Debug] Randomly selected '{sound_info['path'].name}' for category '{category}'.")
        return sound_info

    def copy_sound_to_route(self, sound_path, route_path_str):
        self.log(f"[Debug] Initiating copy for '{sound_path.name}' to route '{route_path_str}'")
        try:
            route_path = Path(route_path_str)
            sound_folder = route_path / "SOUND"
            sound_folder.mkdir(parents=True, exist_ok=True)

            new_filename = f"WEATHERLINK_{sound_path.name}"
            destination = sound_folder / new_filename
            self.log(f"[Debug] Source file: '{sound_path.resolve()}'")
            self.log(f"[Debug] Destination file: '{destination.resolve()}'")
            
            if str(destination) in self.copied_sounds:
                self.log(f"[Info] File '{new_filename}' already copied in this session. Skipping.")
                return new_filename

            shutil.copy2(sound_path, destination)
            self.copied_sounds.add(str(destination))
            self.log(f"[Success] Copied '{sound_path.name}' to '{destination}'")
            
            return new_filename
        except Exception as e:
            self.log(f"[ERROR] CRITICAL: Failed to copy sound file '{sound_path.name}'. Reason: {e}")
            return None