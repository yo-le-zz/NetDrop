# 📦 NetDrop

> **Transfert de fichiers LAN sécurisé avec interface TUI**  
> Version **1.0.0** — Python 3.11+

NetDrop permet de s'identifier sur un réseau local, de découvrir automatiquement les pairs présents et d'envoyer des fichiers entre machines de façon **chiffrée**, **authentifiée** et **historisée** — le tout dans un terminal.

---

## ✨ Fonctionnalités

| Catégorie | Fonctionnalité |
|-----------|---------------|
| 🔐 **Sécurité** | SSL/TLS auto-signé, mots de passe salés (PBKDF2-SHA256 × 310 000), tokens temporaires |
| 🌐 **Réseau** | Découverte UDP broadcast, scan actif du LAN (`/24`), port configurable |
| 🖥️ **Interface** | TUI Textual complète : onglets, tableaux, barres de progression, modaux |
| 📁 **Transferts** | Multi-fichiers, vérification SHA-256, reprise propre sur erreur |
| 📋 **Historique** | SQLite, recherche, export CSV, statistiques globales |
| ⚙️ **Paramètres** | Chaque fonctionnalité peut être activée/désactivée individuellement |

---

## 🚀 Installation

```bash
# Cloner le dépôt
git clone https://github.com/votre-pseudo/NetDrop.git
cd NetDrop

# Installer les dépendances
pip install -r requirements.txt

# Lancer NetDrop
python main.py
```

### Prérequis

- Python **3.11+**
- `textual >= 0.47` — interface TUI
- `cryptography >= 41.0` — certificats SSL

---

## 🎮 Utilisation

### Lancement

```bash
python main.py
```

Au premier démarrage, NetDrop :
1. Génère une **identité unique** (`SWIFT-EAGLE-4271`) stockée dans `~/.netdrop/identity.json`
2. Crée un **certificat SSL auto-signé** dans `~/.netdrop/cert.pem`
3. Démarre le **serveur de réception** sur le port TCP `5000`
4. Lance la **découverte UDP** sur le port `5001`

### Navigation

| Raccourci | Action |
|-----------|--------|
| `Ctrl+Q` | Quitter |
| `Ctrl+S` | Scanner le LAN |
| `Ctrl+H` | Aller à l'historique |
| `F1` | Aide rapide |

### Envoyer des fichiers

1. Onglet **📤 Envoyer** → cliquer **➕ Ajouter fichiers**
2. Renseigner le chemin complet du fichier
3. Choisir le destinataire (IP ou identité) et le port
4. Cliquer **📤 Envoyer**

Si le pair est protégé par un mot de passe, une fenêtre de saisie apparaît.

### Recevoir des fichiers

Le serveur tourne en arrière-plan dès le démarrage. Si **Acceptation automatique** est désactivée, une fenêtre de confirmation apparaît à chaque fichier entrant.

---

## 📁 Structure du projet

```
NetDrop/
├── main.py                 # Point d'entrée
├── requirements.txt
├── netdrop/
│   ├── __init__.py
│   ├── config.py           # Configuration persistante (JSON)
│   ├── auth.py             # Identités, mots de passe, tokens
│   ├── crypto.py           # Certificats SSL auto-signés
│   ├── protocol.py         # Protocole TCP + transfert fichiers
│   ├── discovery.py        # Découverte UDP LAN
│   ├── server.py           # Serveur de réception
│   ├── client.py           # Client d'envoi
│   ├── history.py          # Historique SQLite
│   └── ui/
│       ├── __init__.py
│       └── app.py          # Interface Textual
└── ~/.netdrop/             # Données utilisateur (auto-créé)
    ├── config.json
    ├── identity.json
    ├── known_peers.json
    ├── history.db
    ├── cert.pem
    └── key.pem
```

---

## 🔐 Sécurité

### Chiffrement
- **SSL/TLS 1.2+** sur toutes les connexions (activable/désactivable)
- Certificats RSA 4096 bits auto-signés, valides 10 ans
- Les certificats sont acceptés sans vérification CA (contexte LAN interne)

### Authentification
- Mots de passe hashés avec **PBKDF2-HMAC-SHA256** + sel aléatoire 32 octets (310 000 itérations, recommandation OWASP 2024)
- **Tokens temporaires** (durée configurable, 1h par défaut) pour les sessions
- Un mot de passe configuré est **obligatoire** — impossible de s'authentifier sans

### Intégrité des fichiers
- Chaque fichier est vérifié par son **checksum SHA-256** à la réception
- En cas d'échec, le fichier reçu est automatiquement supprimé

---

## ⚙️ Configuration

Tous les paramètres sont modifiables depuis l'onglet **⚙️ Paramètres** ou directement dans `~/.netdrop/config.json`.

| Paramètre | Défaut | Description |
|-----------|--------|-------------|
| `tcp_port` | `5000` | Port d'écoute serveur |
| `udp_port` | `5001` | Port de découverte UDP |
| `ssl_enabled` | `true` | Chiffrement SSL/TLS |
| `password_enabled` | `false` | Protection par mot de passe |
| `tokens_enabled` | `true` | Tokens de session temporaires |
| `token_lifetime_seconds` | `3600` | Durée de vie des tokens |
| `discovery_enabled` | `true` | Découverte automatique LAN |
| `lan_scan_enabled` | `true` | Scan actif du réseau |
| `auto_accept` | `false` | Accepter les fichiers sans confirmation |
| `download_dir` | `~/Downloads/NetDrop` | Répertoire de réception |
| `max_file_size_mb` | `0` | Taille max (0 = illimité) |
| `history_enabled` | `true` | Enregistrement de l'historique |
| `history_max_entries` | `1000` | Nombre max d'entrées historique |

---

## 📜 Protocole

NetDrop utilise un protocole TCP maison basé sur des messages **JSON ligne** suivis de données binaires brutes pour les fichiers.

```
CLIENT → SERVEUR : {"msg": "hello", "identity": "...", "version": "1.0.0"}
SERVEUR → CLIENT : {"msg": "auth_info", "password_required": false, "identity": "..."}
[si mot de passe requis :]
CLIENT → SERVEUR : {"msg": "auth", "password": "..."}
SERVEUR → CLIENT : {"msg": "auth_ok", "token": "..."}
[pour chaque fichier :]
CLIENT → SERVEUR : {"msg": "file_meta", "name": "...", "size": 12345, "checksum": "sha256..."}
SERVEUR → CLIENT : {"msg": "ready"}
CLIENT stream raw bytes (size octets)
SERVEUR → CLIENT : {"msg": "transfer_ok"}
CLIENT → SERVEUR : {"msg": "bye"}
```

---

## 🤝 Contribuer

Les contributions sont bienvenues ! Ouvrez une *issue* ou une *pull request*.

---

## 📄 Licence

Voir [LICENSE](LICENSE).