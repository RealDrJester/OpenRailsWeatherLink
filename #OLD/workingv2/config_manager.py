# config_manager.py
import json
from pathlib import Path

class ConfigManager:
    """Handles saving and loading of application settings."""
    def __init__(self, config_file='config.json'):
        self.config_path = Path(config_file)
        self.defaults = {
            'theme': 'light',
            'content_paths': [],
            'last_content_path': None,
            'window_geometry': '1200x800'
        }
        self.config = self.load_config()

    def load_config(self):
        if self.config_path.exists():
            with open(self.config_path, 'r') as f:
                try:
                    config = json.load(f)
                    # Ensure all keys from defaults are present
                    for key, value in self.defaults.items():
                        config.setdefault(key, value)
                    return config
                except json.JSONDecodeError:
                    return self.defaults
        return self.defaults

    def save_config(self):
        with open(self.config_path, 'w') as f:
            json.dump(self.config, f, indent=4)

    def get(self, key):
        return self.config.get(key, self.defaults.get(key))

    def set(self, key, value):
        self.config[key] = value
        self.save_config()

    def add_content_path(self, path):
        if path and path not in self.config['content_paths']:
            self.config['content_paths'].append(path)
            self.save_config()