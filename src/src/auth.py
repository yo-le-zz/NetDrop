"""NetDrop — Authentification, identités, mots de passe salés, tokens."""

import hashlib, hmac, json, os, secrets
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from .config import CONFIG_DIR, IDENTITY_FILE, KNOWN_PEERS_FILE

_ADJECTIVES = [
    "SWIFT","BOLD","DARK","IRON","NOVA","FROST","SONIC","TITAN","BLAZE","STORM",
    "GHOST","STEEL","NEON","ULTRA","PIXEL","CYBER","ALPHA","OMEGA","LASER","TURBO",
]
_NOUNS = [
    "EAGLE","WOLF","BEAR","HAWK","LION","VIPER","FALCON","PANTHER","COBRA","TIGER",
    "RAVEN","SHARK","LYNX","PUMA","HYDRA","CIPHER","NEBULA","QUASAR","PHOTON","VERTEX",
]


def _generate_id() -> str:
    return f"{secrets.choice(_ADJECTIVES)}-{secrets.choice(_NOUNS)}-{secrets.randbelow(9000)+1000}"


def _hash_password(password: str, salt: bytes) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 310_000).hex()


@dataclass
class Identity:
    identity_id: str
    password_hash: Optional[str] = None
    salt: Optional[str] = None
    created_at: str = ""

    def has_password(self) -> bool:
        return self.password_hash is not None

    def check_password(self, password: str) -> bool:
        if not self.has_password():
            return True
        return hmac.compare_digest(self.password_hash, _hash_password(password, bytes.fromhex(self.salt)))

    def set_password(self, password: str) -> None:
        salt = os.urandom(32)
        self.salt = salt.hex()
        self.password_hash = _hash_password(password, salt)

    def remove_password(self) -> None:
        self.password_hash = None
        self.salt = None

    def to_dict(self) -> dict: return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Identity":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class KnownPeer:
    identity_id: str
    last_ip: str
    last_port: int
    has_password: bool
    first_seen: str
    last_seen: str
    friendly_name: Optional[str] = None

    def to_dict(self) -> dict: return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "KnownPeer":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


class IdentityManager:
    def __init__(self):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        self._identity: Optional[Identity] = None
        self._tokens: dict[str, tuple[str, datetime]] = {}

    def get_or_create(self) -> Identity:
        if self._identity:
            return self._identity
        if IDENTITY_FILE.exists():
            try:
                with open(IDENTITY_FILE, encoding="utf-8") as f:
                    self._identity = Identity.from_dict(json.load(f))
                return self._identity
            except Exception:
                pass
        return self.create_new()

    def create_new(self, identity_id: Optional[str] = None) -> Identity:
        self._identity = Identity(
            identity_id=identity_id or _generate_id(),
            created_at=datetime.now().isoformat(),
        )
        self._save()
        return self._identity

    def _save(self) -> None:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(IDENTITY_FILE, "w", encoding="utf-8") as f:
            json.dump(self._identity.to_dict(), f, indent=2)

    def set_password(self, password: str) -> None:
        self.get_or_create().set_password(password)
        self._save()

    def remove_password(self) -> None:
        self.get_or_create().remove_password()
        self._save()

    def change_identity(self, new_id: Optional[str] = None) -> Identity:
        return self.create_new(new_id)

    # ── Tokens ─────────────────────────────────────────────────────────────

    def generate_token(self, identity_id: str, lifetime: int = 3600) -> str:
        token = secrets.token_urlsafe(48)
        self._tokens[token] = (identity_id, datetime.now() + timedelta(seconds=lifetime))
        return token

    def validate_token(self, token: str, identity_id: str) -> bool:
        if token not in self._tokens:
            return False
        stored_id, expiry = self._tokens[token]
        if datetime.now() > expiry:
            del self._tokens[token]; return False
        return stored_id == identity_id

    def revoke_all_tokens(self) -> None:
        self._tokens.clear()

    def cleanup_expired_tokens(self) -> int:
        now = datetime.now()
        expired = [t for t, (_, e) in self._tokens.items() if now > e]
        for t in expired: del self._tokens[t]
        return len(expired)

    # ── Pairs connus ────────────────────────────────────────────────────────

    def get_known_peers(self) -> dict[str, KnownPeer]:
        if not KNOWN_PEERS_FILE.exists():
            return {}
        try:
            with open(KNOWN_PEERS_FILE, encoding="utf-8") as f:
                return {k: KnownPeer.from_dict(v) for k, v in json.load(f).items()}
        except Exception:
            return {}

    def upsert_known_peer(self, identity_id: str, ip: str, port: int, has_password: bool) -> None:
        peers = self.get_known_peers()
        now = datetime.now().isoformat()
        if identity_id in peers:
            p = peers[identity_id]
            p.last_ip, p.last_port, p.has_password, p.last_seen = ip, port, has_password, now
        else:
            peers[identity_id] = KnownPeer(identity_id, ip, port, has_password, now, now)
        self._save_peers(peers)

    def set_peer_friendly_name(self, identity_id: str, name: str) -> None:
        peers = self.get_known_peers()
        if identity_id in peers:
            peers[identity_id].friendly_name = name
            self._save_peers(peers)

    def forget_peer(self, identity_id: str) -> None:
        peers = self.get_known_peers()
        peers.pop(identity_id, None)
        self._save_peers(peers)

    def _save_peers(self, peers: dict) -> None:
        with open(KNOWN_PEERS_FILE, "w", encoding="utf-8") as f:
            json.dump({k: v.to_dict() for k, v in peers.items()}, f, indent=2)


# Singleton
identity_manager = IdentityManager()