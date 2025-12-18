from re import S
import socket
import threading
import sys
import datetime
import time

# Importation de ma classe de chiffrement RSA maison
try:
    from chiffrement_RSA import CryptoManager
except ImportError:
    print("ERREUR CRITIQUE : Le fichier chiffrement_RSA.py est introuvable !")
    sys.exit(1)

# Gestion des logs
def journalisation_log(qui, type_message, message):
    maintenant = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ligne_log = f"[{maintenant}] [{qui}] [{type_message}] {message}"
    print(ligne_log)
    nom_fichier = f"journal_{qui.lower()}.log"
    try:
        with open(nom_fichier, "a", encoding="utf-8") as f:
            f.write(ligne_log + "\n")
    except Exception as e:
        print(f"Erreur d'écriture log : {e}")

class Routeur:
    def __init__(self, port_local, ip_master, port_master):
        self.port_local = port_local
        self.ip_master = ip_master
        self.port_master = port_master
        
        self.nom_log = f"ROUTEUR_{port_local}"
        self.annuaire = {} 
        
        journalisation_log(self.nom_log, "INIT", "Démarrage du Nœud...")
        self.crypto = CryptoManager()
        
        if self.crypto.publique is None:
            journalisation_log(self.nom_log, "ERREUR", "Clé publique non chargée.")
    
    def demarrer(self):
        thread_ecoute = threading.Thread(target=self._module_ecoute_reseau, daemon=True)
        thread_ecoute.start()
        
        # 2. Lance le menu de l'interface client
        self._menu_client()
    
    # Module d'écoute
    def _module_ecoute_reseau(self):
        socketTCP_routeur= socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        socketTCP_routeur.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            socketTCP_routeur.bind(("0.0.0.0", self.port_local))
            socketTCP_routeur.listen(5)
            journalisation_log(self.nom_log, "ECOUTE", f"Prêt à relayer sur le port {self.port_local}")
        except Exception as e:
            journalisation_log(self.nom_log, "FATAL", f"Impossible d'ouvrir le port d'écoute : {e}")
            return

        while True:
            try:
                conn, addr = socketTCP_routeur.accept()
                donnees = self._recevoir_tout(conn)
                
                if donnees:
                    try:
                        msg_str = donnees.decode('utf-8').strip()
                        if "REQ_LIST_KEYS" in msg_str:
                            journalisation_log(self.nom_log, "CLIENT", f"Envoi de l'annuaire local à {addr[0]}")
                            lignes = []
                            for rid, info in self.annuaire.items():
                                k = info['cle']
                                lignes.append(f"ID:{rid};IP:{info['ip']};PORT:{info['port']};KEY:{k[0]},{k[1]}")
                            
                            reponse = "\n".join(lignes)
                            conn.sendall(reponse.encode('utf-8'))
                            conn.close()
                            continue
                    except: pass

                    threading.Thread(target=self._analyser_paquet, args=(donnees,)).start()

                try: conn.close()
                except: pass
            except Exception as e:
                print(f"Erreur boucle écoute : {e}")
    
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

    def _analyser_paquet(self, donnees_chiffrees):
        try:
            msg_str = donnees_chiffrees.decode('utf-8')
            message_clair = self.crypto.dechiffrer(msg_str)
            
            if not message_clair or "|" not in message_clair: return

            commande, reste_du_paquet = message_clair.split("|", 1)
            
            if "NEXT_IP" in commande:
                infos = self._parser_headers(commande)
                ip_suiv = infos['NEXT_IP']
                port_suiv = int(infos['NEXT_PORT'])
                journalisation_log(self.nom_log, "ROUTAGE", f"Relayage vers -> {ip_suiv}:{port_suiv}")
                self._envoyer_socket(ip_suiv, port_suiv, reste_du_paquet)

            elif "RELAY:CLIENT" in commande:
                infos = self._parser_headers(commande)
                ip_client = infos['IP']
                port_client = int(infos['PORT'])
                journalisation_log(self.nom_log, "SORTIE", f"Livraison finale au Client {ip_client}:{port_client}")
                self._envoyer_socket(ip_client, port_client, reste_du_paquet)
            
            elif "DEST:FINAL" in commande:
                journalisation_log(self.nom_log, "ARRIVEE", f"Message reçu pour le Routeur : {reste_du_paquet}")

        except Exception as e:
            journalisation_log(self.nom_log, "ERREUR", f"Analyse paquet : {e}")
    
    # Fonction client
    def client_inscription(self):
        try:
            if self.crypto.publique is None:
                print("Erreur : Clés non générées.")
                return

            e, n = self.crypto.publique
            
            try:
                socketTCP_client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                socketTCP_client.connect((self.ip_master, self.port_master))
                mon_ip = socketTCP_client.getsockname()[0]
                socketTCP_client.close()
            except:
                mon_ip = "127.0.0.1"

            requete = f"INSCRIPTION|{mon_ip}|{self.port_local}|{e},{n}"
            
            self._envoyer_socket(self.ip_master, self.port_master, requete)
            journalisation_log(self.nom_log, "MASTER", f"Inscription envoyée avec IP {mon_ip}.")
            print("Synchronisation automatique de l'annuaire...")
            time.sleep(0.5)
            self.client_recuperer_annuaire()
            
        except Exception as e:
            journalisation_log(self.nom_log, "ERREUR", f"Inscription impossible : {e}")
    
    def client_recuperer_annuaire(self):
        try:
            socketTCP_clientrecupere = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            socketTCP_clientrecupere.connect((self.ip_master, self.port_master))
            socketTCP_clientrecupere.sendall(b"REQ_LIST_KEYS")
            reponse = self._recevoir_tout(socketTCP_clientrecupere).decode('utf-8')
            socketTCP_clientrecupere.close()
            self.annuaire = {}
            lignes = reponse.split('\n')
            for ligne in lignes:
                if "ID:" in ligne:
                    d = self._parser_headers(ligne)
                    k_parts = d['KEY'].split(',')
                    self.annuaire[d['ID']] = {
                        'ip': d['IP'],
                        'port': int(d['PORT']),
                        'cle': (int(k_parts[0]), int(k_parts[1]))
                    }
            journalisation_log(self.nom_log, "ANNUAIRE", f"Mise à jour réussie : {len(self.annuaire)} nœuds connus.")
            
        except Exception as e:
            journalisation_log(self.nom_log, "ERREUR", f"Récupération annuaire : {e}")
    
    def _menu_client(self):
        time.sleep(1)
        while True:
            print(f"\nRouteur {self.port_local}")
            print("1. S'inscrire & Sync (Auto)")
            print("2. Forcer Mise à jour Annuaire")
            print("0. Quitter")
            c = input("Choix > ")
            if c == "1": self.client_inscription()
            elif c == "2": self.client_recuperer_annuaire()
            elif c == "0": break

    def _envoyer_socket(self, ip, port, message):
        try:
            socketTCPenvoyer = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            socketTCPenvoyer.connect((ip, port))
            socketTCPenvoyer.sendall(message.encode('utf-8'))
            socketTCPenvoyer.close()
        except Exception as e:
            print(f"Erreur envoi socket vers {ip}:{port} : {e}")

    def _parser_headers(self, chaine):
        res = {}
        parts = chaine.replace('|', ';').split(';')
        for p in parts:
            if ':' in p:
                k, v = p.split(':', 1)
                res[k.strip()] = v.strip()
        return res