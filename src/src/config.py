"""NetDrop — Configuration persistante."""

import json
from dataclasses import dataclass, asdict, field
from pathlib import Path

CONFIG_DIR   = Path.home() / ".netdrop"
CONFIG_FILE  = CONFIG_DIR / "config.json"
CERT_FILE    = CONFIG_DIR / "cert.pem"
KEY_FILE     = CONFIG_DIR / "key.pem"
IDENTITY_FILE = CONFIG_DIR / "identity.json"
HISTORY_DB   = CONFIG_DIR / "history.db"
KNOWN_PEERS_FILE = CONFIG_DIR / "known_peers.json"


@dataclass
class NetDropConfig:
    # Réseau
    tcp_port: int = 5000
    udp_port: int = 5001
    bind_host: str = "0.0.0.0"

    # Sécurité
    ssl_enabled: bool = True
    password_enabled: bool = False
    tokens_enabled: bool = True
    token_lifetime_seconds: int = 3600

    # Découverte
    discovery_enabled: bool = True
    discovery_interval: int = 5
    lan_scan_enabled: bool = True

    # Transferts
    download_dir: str = str(Path.home() / "Downloads" / "NetDrop")
    auto_accept: bool = False
    max_file_size_mb: int = 0
    chunk_size: int = 65536

    # Général
    history_enabled: bool = True
    history_max_entries: int = 1000
    show_transfer_speed: bool = True
    show_peer_ip: bool = True
    confirm_before_send: bool = True
    theme: str = "dark"

    def save(self) -> None:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(asdict(self), f, indent=2, ensure_ascii=False)

    @classmethod
    def load(cls) -> "NetDropConfig":
        if not CONFIG_FILE.exists():
            cfg = cls(); cfg.save(); return cfg
        try:
            with open(CONFIG_FILE, encoding="utf-8") as f:
                data = json.load(f)
            valid = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
            return cls(**valid)
        except Exception:
            cfg = cls(); cfg.save(); return cfg

    def ensure_dirs(self) -> None:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        Path(self.download_dir).mkdir(parents=True, exist_ok=True)