"""NetDrop — Découverte UDP LAN."""

import json, socket, threading, time
from dataclasses import dataclass, asdict
from typing import Callable, Optional

from .crypto import get_local_ip

BROADCAST_ADDR    = "255.255.255.255"
DISCOVERY_TIMEOUT = 15   # secondes avant qu'un pair soit considéré mort


@dataclass
class DiscoveredPeer:
    identity_id: str
    ip: str
    tcp_port: int
    has_password: bool
    last_seen: float
    version: str = "1.0.0"

    @property
    def is_alive(self) -> bool:
        return (time.monotonic() - self.last_seen) < DISCOVERY_TIMEOUT

    @property
    def last_seen_str(self) -> str:
        age = int(time.monotonic() - self.last_seen)
        if age < 5: return "maintenant"
        if age < 60: return f"il y a {age}s"
        return f"il y a {age // 60}m"

    def to_dict(self) -> dict: return asdict(self)


PeerCallback = Callable[[DiscoveredPeer, str], None]


class DiscoveryService:
    def __init__(self, identity_id: str, tcp_port: int, udp_port: int,
                 has_password: bool, on_peer_change: Optional[PeerCallback] = None,
                 interval: int = 5):
        self.identity_id  = identity_id
        self.tcp_port     = tcp_port
        self.udp_port     = udp_port
        self.has_password = has_password
        self.on_peer_change = on_peer_change
        self.interval     = interval
        self._peers: dict[str, DiscoveredPeer] = {}
        self._lock    = threading.Lock()
        self._running = False

    def start(self) -> None:
        self._running = True
        threading.Thread(target=self._announce_loop, daemon=True, name="nd-announce").start()
        threading.Thread(target=self._listen_loop,   daemon=True, name="nd-listen").start()

    def stop(self) -> None:
        self._running = False

    def get_peers(self) -> list[DiscoveredPeer]:
        with self._lock:
            return [p for p in self._peers.values() if p.is_alive]

    def update_password_status(self, has_password: bool) -> None:
        self.has_password = has_password

    def update_identity(self, identity_id: str) -> None:
        self.identity_id = identity_id

    # ── Annonce ───────────────────────────────────────────────────────────────

    def _announce_loop(self) -> None:
        while self._running:
            try:
                self._broadcast()
                self._purge_dead()
            except Exception:
                pass
            time.sleep(self.interval)

    def _broadcast(self) -> None:
        msg = json.dumps({
            "msg": "nd_announce",
            "identity": self.identity_id,
            "tcp_port": self.tcp_port,
            "has_password": self.has_password,
            "version": "1.0.0",
            "ip": get_local_ip(),
        }).encode()
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            s.settimeout(1)
            try: s.sendto(msg, (BROADCAST_ADDR, self.udp_port))
            except Exception: pass

    # ── Écoute ────────────────────────────────────────────────────────────────

    def _listen_loop(self) -> None:
        while self._running:
            try:
                self._listen_once()
            except OSError:
                time.sleep(1)
            except Exception:
                time.sleep(0.5)

    def _listen_once(self) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try: s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
            except AttributeError: pass
            s.bind(("", self.udp_port))
            s.settimeout(2.0)
            while self._running:
                try:
                    data, addr = s.recvfrom(2048)
                    self._handle(data, addr[0])
                except socket.timeout:
                    continue
                except Exception:
                    break

    def _handle(self, data: bytes, sender_ip: str) -> None:
        try: msg = json.loads(data.decode())
        except Exception: return
        if msg.get("msg") != "nd_announce": return
        identity = msg.get("identity", "")
        if not identity or identity == self.identity_id: return

        peer = DiscoveredPeer(
            identity_id=identity,
            ip=msg.get("ip", sender_ip),
            tcp_port=int(msg.get("tcp_port", 5000)),
            has_password=bool(msg.get("has_password", False)),
            last_seen=time.monotonic(),
            version=msg.get("version", "?"),
        )
        with self._lock:
            event = "update" if identity in self._peers else "add"
            self._peers[identity] = peer

        if self.on_peer_change:
            try: self.on_peer_change(peer, event)
            except Exception: pass

    def _purge_dead(self) -> None:
        with self._lock:
            dead = [iid for iid, p in self._peers.items() if not p.is_alive]
        for iid in dead:
            with self._lock:
                peer = self._peers.pop(iid, None)
            if peer and self.on_peer_change:
                try: self.on_peer_change(peer, "remove")
                except Exception: pass


# ── Scan actif ────────────────────────────────────────────────────────────────

def scan_lan_range(tcp_port: int, timeout: float = 0.3,
                   on_found: Optional[Callable[[str, int], None]] = None) -> list[str]:
    local_ip = get_local_ip()
    parts = local_ip.split(".")
    if len(parts) != 4: return []
    base = ".".join(parts[:3])
    found: list[str] = []
    lock = threading.Lock()

    def check(host: str) -> None:
        if host == local_ip: return
        try:
            with socket.create_connection((host, tcp_port), timeout=timeout):
                with lock: found.append(host)
                if on_found:
                    try: on_found(host, tcp_port)
                    except Exception: pass
        except Exception: pass

    threads = [threading.Thread(target=check, args=(f"{base}.{i}",), daemon=True)
               for i in range(1, 255)]
    for t in threads: t.start()
    for t in threads: t.join(timeout=timeout + 0.5)
    return sorted(found)