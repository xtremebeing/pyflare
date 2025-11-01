"""
Configuration management for Flare
"""

import os
import json
from pathlib import Path


class Config:
    """Flare configuration"""

    def __init__(self):
        self.config_dir: Path = Path.home() / ".flare"
        self.config_file: Path = self.config_dir / "config.json"
        self._data: dict[str, str] = self._load()

    def _load(self) -> dict[str, str]:
        """Load config from file or create default"""
        if self.config_file.exists():
            with open(self.config_file, "r") as f:
                return json.load(f)
        return {}

    def save(self):
        """Save config to file"""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        with open(self.config_file, "w") as f:
            json.dump(self._data, f, indent=2)
        # Set file permissions to 0600 (user read/write only)
        self.config_file.chmod(0o600)

    @property
    def worker_url(self) -> str | None:
        """Get worker URL from config or environment"""
        return os.getenv("FLARE_WORKER_URL") or self._data.get("worker_url")

    @worker_url.setter
    def worker_url(self, value: str):
        """Set worker URL"""
        self._data["worker_url"] = value

    @property
    def api_key(self) -> str | None:
        """Get API key from config or environment"""
        return os.getenv("FLARE_API_KEY") or self._data.get("api_key")

    @api_key.setter
    def api_key(self, value: str):
        """Set API key"""
        self._data["api_key"] = value


def load_config() -> Config:
    """Load global config"""
    return Config()
