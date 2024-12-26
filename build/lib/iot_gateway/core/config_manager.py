# Configuration management
from typing import Dict, Any
import json
from dataclasses import dataclass

@dataclass
class SystemConfig:
    device_configs: Dict[str, Any]
    protocol_configs: Dict[str, Any]
    processing_rules: Dict[str, Any]


class ConfigManager:
    def __init__(self, config_path: str):
        self.config_path = config_path
        self.config = self._load_config()

    def _load_config(self) -> SystemConfig:
        with open(self.config_path) as f:
            config_data = json.load(f)
        return SystemConfig(**config_data)