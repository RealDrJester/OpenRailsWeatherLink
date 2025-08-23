# sound_manager.py
import wave
import contextlib
from pathlib import Path
import random
import shutil

class SoundManager:
    def __init__(self, log_callback=print):
        self.log = log_callback
        self.base_path = Path("user_sounds")
        self.sounds = {
            "thunder": [],
            "wind": [],
            "blizzard": [],
            "light_rain": [],
            "medium_rain": []
        }
        self.copied_sounds = set()
        self._discover_sounds()

    def _discover_sounds(self):
        if not self.base_path.is_dir():
            self.log(f"[SoundManager] Creating directory: {self.base_path}")
            self.base_path.mkdir()
        
        sound_map = {
            "thunder": "Thundersound*.wav",
            "wind": "wind*.wav",
            "blizzard": "PolarWind*.wav",
            "light_rain": "LightRain*.wav",
            "medium_rain": "MediumRain*.wav"
        }

        for category, pattern in sound_map.items():
            for sound_file in self.base_path.glob(pattern):
                duration = self._get_wav_duration(sound_file)
                if duration:
                    self.sounds[category].append({"path": sound_file, "duration": duration})
        
        self.log("[SoundManager] Discovered sounds:")
        for category, sound_list in self.sounds.items():
            self.log(f"  > {category.replace('_', ' ').capitalize()}: {len(sound_list)} files")

    def _get_wav_duration(self, wav_path):
        try:
            with contextlib.closing(wave.open(str(wav_path), 'r')) as f:
                frames = f.getnframes()
                rate = f.getframerate()
                return frames / float(rate)
        except wave.Error as e:
            self.log(f"[ERROR] Could not read .wav file: {wav_path.name} - {e}")
            return None

    def get_random_sound(self, category):
        if not self.sounds.get(category):
            return None
        sound_info = random.choice(self.sounds[category])
        return sound_info

    def copy_sound_to_route(self, sound_path, route_path_str):
        try:
            route_path = Path(route_path_str)
            sound_folder = route_path / "SOUND"
            sound_folder.mkdir(parents=True, exist_ok=True)

            # --- CHANGE: Create new filename with WEATHERLINK_ prefix ---
            new_filename = f"WEATHERLINK_{sound_path.name}"
            
            destination = sound_folder / new_filename
            
            # Check if this exact file has already been copied in this session
            if str(destination) in self.copied_sounds:
                return new_filename # Return the prefixed name for the .act file

            # Copy the source file to the destination with the new prefixed name
            shutil.copy2(sound_path, destination)
            self.copied_sounds.add(str(destination))
            self.log(f"[SoundManager] Copied {sound_path.name} to {destination}")
            
            # Return the new filename to be used in the event
            return new_filename
        except Exception as e:
            self.log(f"[ERROR] Failed to copy sound file: {e}")
            return None