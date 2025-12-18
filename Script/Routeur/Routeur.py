import socket 
import threading
import datetime
import sys

try:
    from chiffrement_RSA import CryptoManager 
except ImportError:
    print("ERREUR : Le fichier chiffrement_RSA.py est manquant.")
    sys.exit()

# Fonctions globale

def journalisation_log(qui, type_message, message):
    maintenant = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ligne_log = f"[{maintenant}] [{qui}] [{type_message}] {message}"
    print(ligne_log)
    try:
        nom_fichier = f"journal_{qui.lower()}.log"
        with open(nom_fichier, "a", encoding="utf-8") as f:
            f.write(ligne_log + "\n")
    except:
        pass

def recevoir_tout(socket_conn):
    donnees = b""
    while True:
        try:
            partie = socket_conn.recv(65536)
            if not partie: break
            donnees += partie
            if len(partie) < 65536: break
        except socket.timeout: break
        except Exception: break
    return donnees

# --- CLASSE ROUTEUR ---

class Routeur:
    def __init__(self, master_ip, master_port, port_routeur, recherche_port_client=5002, port_ecoute_client=5003):
        self.Master_IP = master_ip
        self.Port_TCP_master = master_port
        self.Port_Routeur = port_routeur
        self.Recherche_Port_client = recherche_port_client
        self.Port_ecoute_client = port_ecoute_client
        self.Port_UDP_master = 50000 
        self.mon_crypto = CryptoManager()
        self.cle_publique = self.mon_crypto.get_pub_avec_str()
        self.mon_id_interne = "?" 
        self.mon_ip_locale = self._trouver_mon_ip_locale()

        if self.mon_ip_locale == "127.0.0.1": 
            journalisation_log("RTR_INIT", "ALERTE", "IP locale 127.0.0.1 détectée. Test en local uniquement.")

        # Phase d'enregistrement
        if self._enregistrement_Master():
            self._lancer_services()
        else:
            journalisation_log("RTR_ID", "CRITIQUE", "Abandon : Impossible de s'enregistrer auprès du Master.")

    # Méthode interne

    def _trouver_mon_ip_locale(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80)) 
            mon_ip = s.getsockname()[0]
            s.close()
            return mon_ip
        except:
            return "127.0.0.1"

    def _enregistrement_Master(self):
        try:
            socketTCP = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            socketTCP.settimeout(5)
            socketTCP.connect((self.Master_IP, self.Port_TCP_master))
            message = f"INSCRIPTION|{self.mon_ip_locale}|{self.Port_Routeur}|{self.cle_publique}"
            socketTCP.sendall(message.encode())
            
            ack = socketTCP.recv(1024).decode()
            if "ACK|" in ack:
                self.mon_id_interne = ack.split('|')[1]
                journalisation_log(self.mon_id_interne, "INSCRIPTION", f"Succès ! Mon ID réseau est : {self.mon_id_interne}")
                socketTCP.close()
                return True
            
            journalisation_log("RTR_ID", "ERREUR", f"Réponse Master invalide : {ack}")
            return False
        except Exception as e:
            journalisation_log("RTR_ID", "ERREUR", f"Connexion Master impossible ({self.Master_IP}:{self.Port_TCP_master}) : {e}")
            return False

    def _lancer_services(self):
        threading.Thread(target=self.ecouter_recherche_clients, daemon=True).start()
        self._demarrer_ecoute_tcp()

    # Services de communication

    def demander_ip_au_master(self, id_cible):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(3)
            s.connect((self.Master_IP, self.Port_TCP_master))
            s.sendall(f"REQ_RESOLVE_ID|{id_cible}".encode())
            reponse = s.recv(1024).decode().strip()
            s.close()
            if "ERROR" in reponse: return None, None
            parties = reponse.split('|')
            return parties[0], int(parties[1])
        except:
            return None, None
    
    def recuperer_annuaire_master(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(3)
            s.connect((self.Master_IP, self.Port_TCP_master))
            s.sendall(b"REQ_LIST_IDS")
            liste = s.recv(4096).decode().strip()
            s.close()
            return liste
        except: 
            return "ERROR"
        
    def recuperer_annuaire_cles(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(3)
            s.connect((self.Master_IP, self.Port_TCP_master))
            s.sendall(b"REQ_LIST_KEYS")
            liste = s.recv(8192).decode().strip()
            s.close()
            return liste
        except: return "ERROR"

    def demander_nb_hops(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(3)
            s.connect((self.Master_IP, self.Port_TCP_master))
            s.sendall(b"REQ_NB_ROUTEURS")
            nb = s.recv(1024).decode().strip()
            s.close()
            return nb
        except: return "?"
    
    def livrer_au_client_final(self, dest_ip, message):
        journalisation_log(self.mon_id_interne, "LIVRAISON", f"Relais final vers client {dest_ip}")
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(3)
            s.connect((dest_ip, self.Port_ecoute_client))
            s.sendall(message.encode())
            s.close()
            journalisation_log(self.mon_id_interne, "LIVRAISON", "Succès.")
        except Exception as e:
            journalisation_log(self.mon_id_interne, "ERREUR", f"Échec livraison finale : {e}")

    def ecouter_recherche_clients(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(('0.0.0.0', self.Recherche_Port_client))
            journalisation_log(self.mon_id_interne, "UDP", f"Écoute clients sur port {self.Recherche_Port_client}")
            while True:
                data, addr = s.recvfrom(1024)
                if data.decode().strip() == "Ou_est_le_routeur?":
                    reponse = f"Je_suis_le_routeur|{self.mon_id_interne}|{self.Port_Routeur}"
                    s.sendto(reponse.encode(), addr)
        except Exception as e:
            journalisation_log(self.mon_id_interne, "ERREUR", f"Erreur UDP : {e}")

    # Traitement des messages

    def handle_connection(self, conn, addr):
        module_id = self.mon_id_interne 
        try:
            while True:
                data_raw = recevoir_tout(conn)
                if not data_raw: break
                commande = data_raw.decode().strip()
                
                if commande == "REQ_LIST_IDS":
                    conn.sendall(self.recuperer_annuaire_master().encode())
        
                elif commande.startswith("CMD_OIGNON"):
                    try:
                        parties = commande.split('|')
                        blob_chiffre = parties[1]
                        journalisation_log(module_id, "RECEPTION", f"Oignon reçu de {addr[0]}")
                        message_clair = self.mon_crypto.dechiffrer(blob_chiffre)
                        
                        if "[Erreur]" in message_clair or not message_clair:
                            journalisation_log(module_id, "ERREUR", "Déchiffrement échoué.")
                            conn.sendall(b"Erreur Crypto")
                            continue
                            
                        if message_clair.startswith("CMD_FINAL"):
                            p = message_clair.split('|')
                            self.livrer_au_client_final(p[1], p[2])
                            conn.sendall(b"Message Livre")
                            
                        elif message_clair.startswith("CMD_RELAY"):
                            p = message_clair.split('|')
                            prochaine_id = p[1]
                            reste_blob = p[2]
                            
                            journalisation_log(module_id, "RELAIS", f"Vers ID {prochaine_id}")
                            prox_ip, prox_port = self.demander_ip_au_master(prochaine_id)
                            
                            if prox_ip and prox_port:
                                try:
                                    s_prox = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                                    s_prox.settimeout(10)
                                    s_prox.connect((prox_ip, prox_port))
                                    s_prox.sendall(f"CMD_OIGNON|{reste_blob}".encode())
                                    s_prox.close()
                                    conn.sendall(b"Relaye")
                                except Exception as e:
                                    journalisation_log(module_id, "ERREUR", f"Relais impossible : {e}")
                                    conn.sendall(b"Erreur Relais")
                            else:
                                conn.sendall(b"ID Inconnue")

                    except Exception as e:
                        journalisation_log(module_id, "CRASH", f"Erreur oignon : {e}")
                
                elif commande == "CMD_GET_HOPS":
                    conn.sendall(f"Routeurs : {self.demander_nb_hops()}".encode())

                elif commande == "REQ_LIST_KEYS":
                    conn.sendall(self.recuperer_annuaire_cles().encode())
                
                else:
                    conn.sendall(b"Commande inconnue")
        
        except Exception as e:
            journalisation_log(module_id, "ERREUR", f"Socket error : {e}")
        finally: 
            conn.close()

    def _demarrer_ecoute_tcp(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(('0.0.0.0', self.Port_Routeur))
            s.listen(20)
            journalisation_log(self.mon_id_interne, "TCP", f"Prêt sur port {self.Port_Routeur}")
            while True:
                conn, addr = s.accept()
                threading.Thread(target=self.handle_connection, args=(conn, addr), daemon=True).start()
        except Exception as e:
            journalisation_log(self.mon_id_interne, "CRASH", f"Serveur TCP : {e}")
        finally:
            s.close()
