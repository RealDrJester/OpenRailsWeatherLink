# sound_manager.py
import wave
import contextlib
from pathlib import Path
import random
import shutil
import json
import hashlib

class SoundManager:
    def __init__(self, log_callback=print):
        self.log = log_callback
        self.base_path = Path("user_sounds")
        self.sound_definitions = []
        self.sounds = {}
        self.copied_sounds = set()
        self.log("[Debug] SoundManager initialized.")
        self.discover_sounds()

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

    def discover_sounds(self):
        self._load_definitions()
        self.log("[Debug] Discovering user sound files based on definitions...")
        if not self.base_path.is_dir():
            self.log(f"[Info] User sounds directory not found. Creating at: '{self.base_path.resolve()}'")
            self.base_path.mkdir()
        
        self.sounds.clear()
        for definition in self.sound_definitions:
            category = definition.get("category")
            pattern = definition.get("pattern")
            if not category or not pattern: continue

            self.sounds[category] = []
            self.log(f"[Debug] Searching for '{pattern}' for category '{category}'")
            found_files = list(self.base_path.glob(pattern))
            
            for sound_file in found_files:
                duration = self._get_wav_duration(sound_file)
                file_hash = self._calculate_hash(sound_file)
                if duration and file_hash:
                    self.sounds[category].append({
                        "path": sound_file, "duration": duration,
                        "sound_type": definition.get("sound_type", "Everywhere"),
                        "hash": file_hash
                    })
            self.log(f"[Info] Found {len(self.sounds[category])} file(s) for category '{category}'.")

    def _get_wav_duration(self, wav_path):
        try:
            with contextlib.closing(wave.open(str(wav_path), 'r')) as f:
                return f.getnframes() / float(f.getframerate())
        except wave.Error as e:
            self.log(f"[ERROR] Could not read duration from .wav file: {wav_path.name} - {e}")
            return None
    
    def _calculate_hash(self, filepath):
        try:
            hasher = hashlib.sha256()
            with open(filepath, 'rb') as f:
                buf = f.read(65536)
                while len(buf) > 0:
                    hasher.update(buf)
                    buf = f.read(65536)
            return hasher.hexdigest()
        except Exception as e:
            self.log(f"[ERROR] Could not calculate hash for {filepath.name}: {e}")
            return None

    def get_sounds_for_condition(self, condition):
        return [s['category'] for s in self.sound_definitions if s['condition'] == condition]

    def copy_sound_to_route(self, source_path, route_path_str):
        try:
            route_path = Path(route_path_str)
            sound_folder = route_path / "SOUND"
            sound_folder.mkdir(parents=True, exist_ok=True)

            sound_filename = f"WEATHERLINK_{source_path.name}"
            destination = sound_folder / sound_filename
            
            # Use a cache to avoid copying the same file multiple times per run
            if destination not in self.copied_sounds:
                shutil.copy2(source_path, destination)
                self.copied_sounds.add(destination)

            return f"..\\\\SOUND\\\\{sound_filename}"
        except Exception as e:
            self.log(f"[ERROR] Could not copy sound file {source_path.name}: {e}")
            return None