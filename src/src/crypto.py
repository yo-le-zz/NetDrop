"""NetDrop — Certificats SSL auto-signés."""

import ipaddress, socket, ssl, datetime
from pathlib import Path
from typing import Optional

from .config import CERT_FILE, KEY_FILE, CONFIG_DIR


def generate_self_signed_cert(cert_path: Path = CERT_FILE, key_path: Path = KEY_FILE) -> None:
    try:
        from cryptography import x509
        from cryptography.x509.oid import NameOID
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
    except ImportError:
        raise RuntimeError("Installez 'cryptography' : pip install cryptography")

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    key = rsa.generate_private_key(public_exponent=65537, key_size=4096)
    local_ip = _get_local_ip()

    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "FR"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "NetDrop"),
        x509.NameAttribute(NameOID.COMMON_NAME, "netdrop.local"),
    ])

    san = [x509.DNSName("localhost"), x509.DNSName("netdrop.local"),
           x509.IPAddress(ipaddress.IPv4Address("127.0.0.1"))]
    if local_ip and local_ip != "127.0.0.1":
        try: san.append(x509.IPAddress(ipaddress.IPv4Address(local_ip)))
        except ValueError: pass

    cert = (
        x509.CertificateBuilder()
        .subject_name(subject).issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.utcnow())
        .not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=3650))
        .add_extension(x509.SubjectAlternativeName(san), critical=False)
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )

    with open(cert_path, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))
    with open(key_path, "wb") as f:
        f.write(key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ))


def ensure_certs() -> bool:
    try:
        if not CERT_FILE.exists() or not KEY_FILE.exists():
            generate_self_signed_cert()
        return True
    except Exception:
        return False


def create_server_ssl_context() -> ssl.SSLContext:
    ensure_certs()
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(certfile=str(CERT_FILE), keyfile=str(KEY_FILE))
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    return ctx


def create_client_ssl_context() -> ssl.SSLContext:
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    return ctx


def _get_local_ip() -> Optional[str]:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"


def get_local_ip() -> str:
    return _get_local_ip() or "127.0.0.1"