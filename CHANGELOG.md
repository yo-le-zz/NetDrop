# Changelog

Toutes les modifications notables de ce projet sont documentées ici.

Le format suit [Keep a Changelog](https://keepachangelog.com/fr/1.0.0/)  
et ce projet respecte le [Versionnage Sémantique](https://semver.org/lang/fr/).

---

## [1.0.0] — 2026-03-27

### 🎉 Première version publique

#### Ajouté
- **Identités générées automatiquement** au format `MOT-MOT-XXXX` (ex. `SWIFT-EAGLE-4271`), stockées localement
- **Protection par mot de passe** : PBKDF2-HMAC-SHA256 avec sel aléatoire 32 octets et 310 000 itérations
- **Tokens de session temporaires** : UUID sécurisé avec durée de vie configurable (défaut : 1h)
- **SSL/TLS auto-signé** : certificats RSA 4096 bits générés automatiquement, TLS 1.2+ obligatoire
- **Découverte UDP broadcast** : annonce de présence automatique sur le réseau local toutes les 5 secondes
- **Scan actif du LAN** : balayage du sous-réseau `/24` pour trouver les pairs avec le port ouvert
- **Purge automatique** des pairs inactifs (timeout 15 secondes)
- **Envoi multi-fichiers** : file d'attente avec envoi séquentiel sur une même connexion TCP
- **Vérification SHA-256** de chaque fichier reçu — suppression automatique en cas d'échec
- **Noms de fichiers sécurisés** : suppression des caractères dangereux côté réception
- **Acceptation manuelle ou automatique** des fichiers entrants (configurable)
- **Historique SQLite** : enregistrement de tous les transferts (direction, taille, vitesse, pair, statut)
- **Recherche dans l'historique**, suppression individuelle, effacement global, export CSV
- **Statistiques globales** : nombre de transferts, volume total, répartition envoi/réception
- **Interface TUI Textual** avec 4 onglets : Accueil, Envoyer, Historique, Paramètres
- **Découverte en temps réel** dans l'onglet Accueil avec tableau mis à jour toutes les 3 secondes
- **Barres de progression** et affichage de la vitesse de transfert en temps réel
- **Modaux** : saisie de mot de passe, confirmation de réception, changement d'identité
- **Tous les paramètres configurables** depuis l'interface, sauvegardés en JSON
- **Raccourcis clavier** : `Ctrl+Q`, `Ctrl+S`, `Ctrl+H`, `F1`
- **Pairs connus** : mémorisation des pairs déjà rencontrés (`known_peers.json`)
- Configuration stockée dans `~/.netdrop/` (multiplateforme)

#### Sécurité
- Aucun mot de passe transmis en clair si SSL est activé
- Vérification d'intégrité SHA-256 systématique
- Tokens avec expiration automatique et révocation possible
- Certificats auto-signés acceptés uniquement côté LAN (pas de vérification CA)

---

## À venir (roadmap)

### [1.1.0] — prévu
- Drag & drop de fichiers depuis le gestionnaire de fichiers système
- Notification système (libnotify / macOS notify) à la réception d'un fichier
- Mode CLI sans interface TUI (`--send`, `--list-peers`)
- Reprise de transfert interrompu

### [1.2.0] — prévu
- Transfert de dossiers entiers (zip automatique côté client)
- Chiffrement end-to-end optionnel (clés asymétriques par pair)
- Interface Web légère (optionnelle, localhost uniquement)
- Support IPv6

### [2.0.0] — vision
- Relais NAT traversal pour transferts hors LAN
- Plugins / hooks post-réception
- API REST locale pour intégration dans des scripts