"""NetDrop — Protocole TCP et transfert de fichiers."""

import hashlib, json, os, socket, time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

PROTOCOL_VERSION = "1.0.0"
CHUNK_SIZE = 65536


# ── SocketIO ──────────────────────────────────────────────────────────────────

class SocketIO:
    """Wrapper socket avec buffer pour messages JSON + données brutes."""

    def __init__(self, sock: socket.socket):
        self.sock = sock
        self._buf = b""

    def send_msg(self, msg: dict) -> None:
        data = json.dumps(msg, ensure_ascii=False).encode("utf-8") + b"\n"
        self.sock.sendall(data)

    def recv_msg(self) -> dict:
        while b"\n" not in self._buf:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise ConnectionError("Connexion fermée par le pair")
            self._buf += chunk
        line, self._buf = self._buf.split(b"\n", 1)
        return json.loads(line.decode("utf-8"))

    def send_raw(self, data: bytes) -> None:
        self.sock.sendall(data)

    def recv_exact(self, n: int) -> bytes:
        result = bytearray()
        if self._buf:
            take = min(len(self._buf), n)
            result.extend(self._buf[:take])
            self._buf = self._buf[take:]
            n -= take
        while n > 0:
            chunk = self.sock.recv(min(n, CHUNK_SIZE))
            if not chunk:
                raise ConnectionError("Connexion fermée pendant la réception")
            result.extend(chunk)
            n -= len(chunk)
        return bytes(result)

    def close(self) -> None:
        try: self.sock.close()
        except Exception: pass


# ── Stats de transfert ────────────────────────────────────────────────────────

@dataclass
class TransferStats:
    filename: str
    total_bytes: int
    transferred_bytes: int = 0
    start_time: float = 0.0
    end_time: float = 0.0
    success: bool = False
    error: Optional[str] = None
    local_path: Optional[str] = None

    @property
    def progress(self) -> float:
        return (self.transferred_bytes / self.total_bytes) if self.total_bytes else 1.0

    @property
    def speed_bps(self) -> float:
        elapsed = (self.end_time or time.monotonic()) - self.start_time
        return (self.transferred_bytes / elapsed) if elapsed > 0 else 0.0

    @property
    def speed_human(self) -> str:
        bps = self.speed_bps
        if bps >= 1_048_576: return f"{bps/1_048_576:.1f} MB/s"
        if bps >= 1024: return f"{bps/1024:.1f} KB/s"
        return f"{bps:.0f} B/s"

    @property
    def eta_seconds(self) -> Optional[float]:
        remaining = self.total_bytes - self.transferred_bytes
        bps = self.speed_bps
        return (remaining / bps) if bps > 0 else None


ProgressCallback = Callable[[TransferStats], None]


# ── Checksum ──────────────────────────────────────────────────────────────────

def file_checksum(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(CHUNK_SIZE), b""):
            h.update(chunk)
    return h.hexdigest()


# ── Envoi d'un fichier ────────────────────────────────────────────────────────

def send_file(
    sio: SocketIO,
    filepath: Path,
    progress_cb: Optional[ProgressCallback] = None,
    chunk_size: int = CHUNK_SIZE,
) -> TransferStats:
    stat = TransferStats(
        filename=filepath.name,
        total_bytes=filepath.stat().st_size,
        start_time=time.monotonic(),
    )
    checksum = file_checksum(filepath)
    sio.send_msg({"msg": "file_meta", "name": filepath.name,
                  "size": stat.total_bytes, "checksum": checksum})

    resp = sio.recv_msg()
    if resp.get("msg") != "ready":
        stat.error = resp.get("reason", "Refusé par le serveur")
        stat.end_time = time.monotonic()
        return stat

    with open(filepath, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk: break
            sio.send_raw(chunk)
            stat.transferred_bytes += len(chunk)
            if progress_cb: progress_cb(stat)

    result = sio.recv_msg()
    stat.end_time = time.monotonic()
    if result.get("msg") == "transfer_ok":
        stat.success = True
    else:
        stat.error = result.get("reason", "Erreur inconnue")
    return stat


# ── Réception d'un fichier ────────────────────────────────────────────────────

def receive_file_from_meta(
    sio: SocketIO,
    meta: dict,
    dest_dir: Path,
    max_size_mb: int = 0,
    progress_cb: Optional[ProgressCallback] = None,
    chunk_size: int = CHUNK_SIZE,
) -> TransferStats:
    """Reçoit un fichier dont le message file_meta est déjà lu."""
    filename = sanitize_filename(meta["name"])
    total_size = int(meta.get("size", 0))
    expected_checksum = meta.get("checksum", "")

    stat = TransferStats(filename=filename, total_bytes=total_size, start_time=time.monotonic())

    if max_size_mb > 0 and total_size > max_size_mb * 1024 * 1024:
        sio.send_msg({"msg": "error", "reason": f"Fichier trop grand (max {max_size_mb} MB)"})
        stat.error = "Fichier trop grand"
        stat.end_time = time.monotonic()
        return stat

    sio.send_msg({"msg": "ready"})
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = _unique_path(dest_dir / filename)
    hasher = hashlib.sha256()

    with open(dest_path, "wb") as f:
        remaining = total_size
        while remaining > 0:
            chunk = sio.recv_exact(min(chunk_size, remaining))
            f.write(chunk)
            hasher.update(chunk)
            stat.transferred_bytes += len(chunk)
            remaining -= len(chunk)
            if progress_cb: progress_cb(stat)

    stat.end_time = time.monotonic()

    if expected_checksum and hasher.hexdigest() != expected_checksum:
        try: os.remove(dest_path)
        except Exception: pass
        sio.send_msg({"msg": "checksum_fail", "reason": "SHA-256 invalide"})
        stat.error = "Checksum invalide — fichier supprimé"
        return stat

    sio.send_msg({"msg": "transfer_ok"})
    stat.success = True
    stat.local_path = str(dest_path)
    return stat


# ── Utilitaires ───────────────────────────────────────────────────────────────

def sanitize_filename(name: str) -> str:
    bad = set('/\\:*?"<>|')
    cleaned = "".join(c if c not in bad else "_" for c in name).strip(". ")
    return cleaned or "fichier_recu"


def _unique_path(path: Path) -> Path:
    if not path.exists(): return path
    i = 1
    while True:
        candidate = path.parent / f"{path.stem}_{i}{path.suffix}"
        if not candidate.exists(): return candidate
        i += 1


def human_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024: return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"