"""Agent configuration stored in the platform config directory."""

from __future__ import annotations

import json
import os
import secrets
import sys
import uuid
from dataclasses import asdict, dataclass, fields
from pathlib import Path


def config_dir() -> Path:
    """%APPDATA%\\AirTrain on Windows, $XDG_CONFIG_HOME/airtrain (~/.config/airtrain) on Linux."""
    override = os.environ.get("AIRTRAIN_HOME")
    if override:
        return Path(override)
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(base) / "AirTrain"
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "airtrain"


def new_token() -> str:
    return secrets.token_urlsafe(9)


@dataclass
class Config:
    device_id: str = ""
    token: str = ""
    name: str = ""  # shown in the app; defaults to the hostname
    port: int = 8765
    gpu_index: int = 0
    idle_minutes: float = 5.0  # no keyboard/mouse input for this long counts as idle
    max_temp_c: float = 83.0  # pause training above this GPU (or CPU) temperature
    resume_temp_margin_c: float = 5.0  # resume once temp is this far below max_temp_c
    min_battery_pct: float = 50.0  # on battery below this, the device is busy
    gpu_busy_util: float = 30.0  # another process using the GPU above this % makes it busy

    @property
    def path(self) -> Path:
        return config_dir() / "config.json"

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(asdict(self), indent=2))
        if sys.platform != "win32":
            try:
                os.chmod(self.path, 0o600)
            except OSError:
                pass

    def set(self, key: str, value: str) -> None:
        types = {f.name: f.type for f in fields(self)}
        if key not in types or key == "device_id":
            raise KeyError(key)
        current = getattr(self, key)
        if isinstance(current, bool):
            setattr(self, key, value.lower() in ("1", "true", "yes", "on"))
        elif isinstance(current, int):
            setattr(self, key, int(value))
        elif isinstance(current, float):
            setattr(self, key, float(value))
        else:
            setattr(self, key, value)


def load_config() -> tuple[Config, bool]:
    """Load the config, creating it (with a new pairing token) on first run.

    Returns (config, created).
    """
    cfg = Config()
    created = False
    if cfg.path.exists():
        try:
            data = json.loads(cfg.path.read_text())
            known = {f.name for f in fields(Config)}
            cfg = Config(**{k: v for k, v in data.items() if k in known})
        except (OSError, ValueError, TypeError):
            cfg = Config()
    if not cfg.device_id:
        cfg.device_id = uuid.uuid4().hex[:12]
        created = True
    if not cfg.token:
        cfg.token = new_token()
        created = True
    if created or not cfg.path.exists():
        cfg.save()
    return cfg, created
