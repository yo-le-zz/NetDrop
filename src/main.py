#!/usr/bin/env python3
"""NetDrop v1.0.0 — Point d'entrée. Usage: python main.py"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def check_dependencies() -> bool:
    missing = []
    try:
        import textual       # noqa: F401
    except ImportError:
        missing.append("textual>=0.47.0")
    try:
        import cryptography  # noqa: F401
    except ImportError:
        missing.append("cryptography>=41.0.0")
    if missing:
        print("❌  Dépendances manquantes :")
        for m in missing:
            print(f"       • {m}")
        print(f"\n   Installez avec : pip install {' '.join(missing)}")
        return False
    return True


def main() -> None:
    if not check_dependencies():
        sys.exit(1)

    from src.config  import NetDropConfig
    from src.auth    import identity_manager
    from src.history import history_db
    from src.crypto  import ensure_certs, get_local_ip
    from src.ui.app  import NetDropApp

    config   = NetDropConfig.load()
    config.ensure_dirs()
    identity = identity_manager.get_or_create()

    if config.ssl_enabled:
        if not ensure_certs():
            print("⚠   Certificats SSL indisponibles — SSL désactivé")
            config.ssl_enabled = False

    ip    = get_local_ip()
    pw    = "🔐 protégé" if (identity.has_password() and config.password_enabled) else "🔓 ouvert"
    ssl_s = "🔒 SSL ON"  if config.ssl_enabled else "⚠  SSL OFF"
    print()
    print("  ███╗   ██╗███████╗████████╗██████╗ ██████╗  ██████╗ ██████╗ ")
    print("  ████╗  ██║██╔════╝╚══██╔══╝██╔══██╗██╔══██╗██╔═══██╗██╔══██╗")
    print("  ██╔██╗ ██║█████╗     ██║   ██║  ██║██████╔╝██║   ██║██████╔╝")
    print("  ██║╚██╗██║██╔══╝     ██║   ██║  ██║██╔══██╗██║   ██║██╔═══╝ ")
    print("  ██║ ╚████║███████╗   ██║   ██████╔╝██║  ██║╚██████╔╝██║     ")
    print("  ╚═╝  ╚═══╝╚══════╝   ╚═╝   ╚═════╝ ╚═╝  ╚═╝ ╚═════╝ ╚═╝  v1.0.0")
    print()
    print(f"  Identité  : {identity.identity_id}")
    print(f"  IP locale : {ip}:{config.tcp_port}")
    print(f"  Sécurité  : {pw}  {ssl_s}")
    print(f"  Répertoire: {config.download_dir}")
    print()

    app = NetDropApp(config=config, im=identity_manager, history=history_db)
    app.run()


if __name__ == "__main__":
    main()