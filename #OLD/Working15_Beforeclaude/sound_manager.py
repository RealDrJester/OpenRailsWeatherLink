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
                        "hash": file_hash, "looping": definition.get("looping", False)
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

    def provision_sound_files_for_route(self, route_path_str):
        self.log(f"[Info] Provisioning all sound files for route '{route_path_str}'")
        route_path = Path(route_path_str)
        sound_folder = route_path / "SOUND"
        sound_folder.mkdir(parents=True, exist_ok=True)
        
        ssource_path = route_path / "ssource.dat"
        if not ssource_path.exists():
            self.log(f"[Warning] ssource.dat not found in route. Cannot add sounds.")
            return

        new_ssource_lines = []
        for category, sound_list in self.sounds.items():
            if not sound_list or not sound_list[0]['looping']:
                continue

            # Provision all WAV files for this category
            wav_filenames = []
            for sound in sound_list:
                wav_filename = f"WEATHERLINK_{sound['path'].name}"
                wav_dest = sound_folder / wav_filename
                if not wav_dest.exists() or self._calculate_hash(wav_dest) != sound['hash']:
                    shutil.copy2(sound['path'], wav_dest)
            
            # Generate the master SMS file for this category
            sms_filename = f"WEATHERLINK_{category}.sms"
            sms_dest = sound_folder / sms_filename
            
            sound_type = sound_list[0]['sound_type']
            activation = ""
            if sound_type == "Cab": activation = "CabCam()"
            elif sound_type == "Pass": activation = "PassengerCam()"
            elif sound_type == "Everywhere": activation = "ExternalCam()"
            
            # This is a special condition based on how ORTS seems to handle rain
            if "rain" in category and sound_type == "Everywhere":
                activation = "ExternalCam() CabCam() PassengerCam()"

            file_lines = '\n'.join([f'\t\t\t\t\t\t\tFile ( "WEATHERLINK_{s["path"].name}" -1 )' for s in sound_list])
            sms_content = (
                "SIMISA@@@@@@@@@@JINX0x1t______\n\nTr_SMS (\n"
                f"\tScalabiltyGroup( 2\n\t\tActivation ( {activation} )\n"
                f"\t\tStreams ( 1\n\t\t\tStream (\n\t\t\t\tPriority ( 2 )\n\t\t\t\tTriggers ( 1\n"
                f"\t\t\t\t\tInitial_Trigger ( StartLoop ( {len(sound_list)}\n{file_lines}\n"
                f"\t\t\t\t\t\t\tSelectionMethod ( RandomSelection ) ) ) )\n\t\t\t)\n\t\t)\n\t)\n)"
            )
            with open(sms_dest, 'w', encoding='utf-8-sig') as f: f.write(sms_content)
            
            # Add the line for ssource.dat
            ssource_entry = f'Sound ( Name ( "{category}" ) FileName ( "{sms_filename}" ) )'
            new_ssource_lines.append(ssource_entry)

        # Safely modify ssource.dat
        backup_path = ssource_path.with_suffix('.dat.bak')
        if not backup_path.exists():
            shutil.copy2(ssource_path, backup_path)
            self.log(f"[Success] Created backup of original '{ssource_path.name}'")

        content, encoding = (None, None)
        try:
            with open(ssource_path, 'r', encoding='utf-16-le', errors='strict') as f:
                content = f.read(); encoding = 'utf-16-le'
        except (UnicodeError, UnicodeDecodeError):
            with open(ssource_path, 'r', encoding='utf-8-sig', errors='strict') as f:
                content = f.read(); encoding = 'utf-8-sig'
        
        lines_to_add_str = ""
        for line in new_ssource_lines:
            if line not in content:
                lines_to_add_str += line + "\n"
        
        if lines_to_add_str:
            content += "\n" + lines_to_add_str
            with open(ssource_path, 'w', encoding=encoding) as f:
                f.write(content)
            self.log(f"[Success] Appended {len(lines_to_add_str.strip().splitlines())} sound definitions to '{ssource_path.name}'")

    def provision_sound_category(self, category, route_path_str): # For one-shot thunder
        sound_info_list = self.sounds.get(category, [])
        if not sound_info_list: return None, None
        
        sound_info = random.choice(sound_info_list)
        source_path = sound_info['path']
        
        route_path = Path(route_path_str)
        sound_folder = route_path / "SOUND"
        sound_folder.mkdir(parents=True, exist_ok=True)
        wav_filename = f"WEATHERLINK_{source_path.name}"
        destination = sound_folder / wav_filename

        if not destination.exists() or self._calculate_hash(destination) != sound_info['hash']:
            shutil.copy2(source_path, destination)
        return wav_filename, sound_info