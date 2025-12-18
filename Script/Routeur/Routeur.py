import socket
import threading
import sys
import datetime
import time

# Import de la classe de chiffrement
try:
    from chiffrement_RSA import CryptoManager
except ImportError:
    print("ERREUR : Le fichier chiffrement_RSA.py est introuvable !")
    sys.exit()

# Fonction des logs
def journalisation_log(qui, type_message, message):
    maintenant = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # On ajoute le port dans le nom pour différencier les fichiers logs
    ligne_log = f"[{maintenant}] [{qui}] [{type_message}] {message}"
    
    # Affichage console
    print(ligne_log)

    # Écriture fichier
    nom_fichier = f"journal_{qui.lower()}.log"
    try:
        with open(nom_fichier, "a", encoding="utf-8") as f:
            f.write(ligne_log + "\n")
    except Exception as e:
        print(f"Erreur d'écriture log : {e}")

class Routeur:
    def __init__(self, port_local, master_ip, master_port):
        self.port_local = port_local
        self.master_ip = master_ip
        self.master_port = master_port
        self.nom_log = f"ROUTEUR_{port_local}" # Identifiant pour les logs
        self.annuaire = {} 
        
        journalisation_log(self.nom_log, "INIT", f"Démarrage sur port {self.port_local}...")
        self.crypto = CryptoManager()
        
    def demarrer(self):
        # 1. Thread Serveur (Relais)
        thread_reception = threading.Thread(target=self._ecouter_reseau, daemon=True)
        thread_reception.start()
        
        # 2. Menu interactif (Client)
        self._menu_interactif()

    # --- LOGIQUE RÉSEAU (SERVEUR) ---
    def _ecouter_reseau(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(("0.0.0.0", self.port_local))
            s.listen(5)
            journalisation_log(self.nom_log, "RESEAU", f"Écoute active sur le port {self.port_local}")
        except Exception as e:
            journalisation_log(self.nom_log, "ERREUR", f"Liaison port impossible : {e}")
            return

        while True:
            client, addr = s.accept()
            donnees = self._recevoir_tout(client)
            if donnees:
                journalisation_log(self.nom_log, "FLUX", f"Paquet reçu de {addr[0]}")
                threading.Thread(target=self._traiter_message, args=(donnees,)).start()
            client.close()

    def _recevoir_tout(self, sock):
        contenu = b""
        sock.settimeout(2)
        try:
            while True:
                partie = sock.recv(4096)
                if not partie: break
                contenu += partie
        except: pass
        return contenu

    def _traiter_message(self, donnees_brutes):
        try:
            # Déchiffrement avec ta classe CryptoManager
            message_clair = self.crypto.dechiffrer(donnees_brutes)
            
            if not message_clair or "|" not in message_clair:
                journalisation_log(self.nom_log, "ALERTE", "Message illisible ou mal chiffré.")
                return

            commande, reste = message_clair.split("|", 1)
            
            if "NEXT_IP" in commande:
                # CAS : RELAIS
                infos = self._parser_headers(commande)
                journalisation_log(self.nom_log, "RELAIS", f"➡️ Transmission vers {infos['NEXT_IP']}:{infos['NEXT_PORT']}")
                self._envoyer_socket(infos['NEXT_IP'], int(infos['NEXT_PORT']), reste)
                
            elif "DEST:FINAL" in commande:
                # CAS : DESTINATION FINALE
                journalisation_log(self.nom_log, "RECEPTION", f"🏁 Message final reçu : {reste}")
                print("\n(Appuyez sur Entrée pour revenir au menu)")

        except Exception as e:
            journalisation_log(self.nom_log, "ERREUR", f"Déchiffrement impossible : {e}")

    # --- LOGIQUE INTERFACE (CLIENT) ---
    def _menu_interactif(self):
        while True:
            print(f"\n--- 🌐 MODE HYBRIDE (Port: {self.port_local}) ---")
            print("1. S'inscrire au Master")
            print("2. Actualiser l'annuaire")
            print("3. Envoyer un message (Oignon)")
            print("q. Quitter")
            
            choix = input("\nAction > ")
            if choix == "1": self.action_inscription()
            elif choix == "2": self.action_recuperer_annuaire()
            elif choix == "3": self.action_envoyer_oignon()
            elif choix == "q": break

    def action_inscription(self):
        try:
            e, n = self.crypto.c_pub
            # Format attendu par ton Master : INSCRIPTION|IP|PORT|CLE
            mon_ip = socket.gethostbyname(socket.gethostname())
            requete = f"INSCRIPTION|{mon_ip}|{self.port_local}|{e},{n}"
            
            self._envoyer_socket(self.master_ip, self.master_port, requete)
            journalisation_log(self.nom_log, "MASTER", "Demande d'inscription envoyée.")
        except Exception as e:
            journalisation_log(self.nom_log, "ERREUR", f"Échec inscription : {e}")

    def action_recuperer_annuaire(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((self.master_ip, self.master_port))
            s.sendall(b"REQ_LIST_KEYS")
            reponse = self._recevoir_tout(s).decode('utf-8')
            s.close()

            # Parsing l'annuaire
            self.annuaire = {}
            for ligne in reponse.split('\n'):
                if "ID:" in ligne:
                    d = self._parser_headers(ligne)
                    k = d['KEY'].split(',')
                    self.annuaire[d['ID']] = {
                        'ip': d['IP'], 'port': int(d['PORT']),
                        'cle': (int(k[0]), int(k[1]))
                    }
            journalisation_log(self.nom_log, "ANNUAIRE", f"{len(self.annuaire)} routeurs chargés.")
        except Exception as e:
            journalisation_log(self.nom_log, "ERREUR", f"Échec annuaire : {e}")

    def action_envoyer_oignon(self):
        if not self.annuaire:
            print("❌ Annuaire vide.")
            return
        
        print("\n--- Routeurs Disponibles ---")
        for rid, info in self.annuaire.items():
            print(f"ID {rid} | {info['ip']}:{info['port']}")
        
        id_dest = input("\nID destination finale : ")
        msg_final = input("Message secret : ")

        try:
            # 1. Couche finale
            cle_dest = self.annuaire[id_dest]['cle']
            paquet = self.crypto.chiffrer(f"DEST:FINAL|{msg_final}", cle_dest)

            # 2. Couche relais
            id_relais = input("ID du relais intermédiaire : ")
            cle_relais = self.annuaire[id_relais]['cle']
            info_dest = self.annuaire[id_dest]
            
            instruction = f"NEXT_IP:{info_dest['ip']};NEXT_PORT:{info_dest['port']}|{paquet}"
            paquet_complet = self.crypto.chiffrer(instruction, cle_relais)

            # 3. Envoi
            journalisation_log(self.nom_log, "ENVOI", f"Envoi oignon vers {id_relais}")
            self._envoyer_socket(self.annuaire[id_relais]['ip'], self.annuaire[id_relais]['port'], paquet_complet)
        except Exception as e:
            journalisation_log(self.nom_log, "ERREUR", f"Construction oignon échouée : {e}")

    def _envoyer_socket(self, ip, port, message):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((ip, port))
        s.sendall(message.encode('utf-8') if isinstance(message, str) else message)
        s.close()

    def _parser_headers(self, chaine):
        res = {}
        parties = chaine.replace('|', ';').split(';')
        for p in parties:
            if ':' in p:
                k, v = p.split(':', 1)
                res[k.strip()] = v.strip()
        return res