import socket 
import threading
import datetime
from chiffrement_RSA import CryptoManager 

# Fonction global

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


# Class Routeur
class Routeur:
    
    def __init__(self, master_ip, port_routeur, recherche_port_client, port_ecoute_client):
        
        self.Master_IP = master_ip
        self.Port_Routeur = port_routeur
        self.Recherche_Port_client = recherche_port_client
        self.Port_ecoute_client = port_ecoute_client
        self.Port_TCP_master = 6000  
        self.Port_UDP_master = 50000 
        
        self.mon_crypto = CryptoManager()
        self.cle_publique = self.mon_crypto.get_pub_avec_str()
        self.mon_id_interne = "?" 
        self.mon_ip_locale = self._trouver_mon_ip_locale()

        if self.mon_ip_locale == "127.0.0.1": 
            journalisation_log("RTR_ID", "CRITIQUE", "Échec détection IP locale. Abandon.")
            return

        if self._enregistrement_Master():
            self._lancer_services()
        else:
            journalisation_log("RTR_ID", "CRITIQUE", "Abandon : Échec enregistrement Master.")
    
# Methode interne 
    def _trouver_mon_ip_locale(self):
        try:
            socketUDP = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            socketUDP.connect(("8.8.8.8", 80)) 
            mon_ip = socketUDP.getsockname()[0]
            socketUDP.close()
            return mon_ip
        except:
            return "127.0.0.1"

    def _enregistrement_Master(self):
        # Ancienne fonction 'enregistrement_Master'
        try:
            socketTCP = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            socketTCP.settimeout(5)
            socketTCP.connect((self.Master_IP, self.Port_TCP_master))
            
            message = f"{self.mon_ip_locale}|{self.Port_Routeur}|{self.cle_publique}"
            socketTCP.sendall(message.encode())
            
            ack = socketTCP.recv(1024).decode()
            if "ACK|" in ack:
                self.mon_id_interne = ack.split('|')[1]
                journalisation_log(self.mon_id_interne, "INSCRIPTION", f"Enregistrement OK. ID : {self.mon_id_interne}")
                socketTCP.close()
                return True
            
            journalisation_log(self.mon_id_interne, "ERREUR", f"Échec inscription (ACK) : {ack}")
            return False
            
        except Exception as e:
            journalisation_log("RTR_ID", "ERREUR", f"Échec connexion Master : {e}")
            return False

    def _lancer_services(self):
        threading.Thread(target=self.ecouter_recherche_clients, daemon=True).start()
        self._demarrer_ecoute_tcp()

# Methode service
    def demander_ip_au_master(self, id_cible):
        # Remplacer master_ip par self.Master_IP
        try:
            socketmasterTCP = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            socketmasterTCP.settimeout(3)
            socketmasterTCP.connect((self.Master_IP, self.Port_TCP_master))
            socketmasterTCP.sendall(f"REQ_RESOLVE_ID|{id_cible}".encode())
            reponse = socketmasterTCP.recv(1024).decode().strip()
            socketmasterTCP.close()
            if "ERROR" in reponse: return None, None
            parties = reponse.split('|')
            return parties[0], int(parties[1])
        except:
            return None, None
    
    def recuperer_annuaire_master(self):
        try:
            socketTCP = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            socketTCP.settimeout(3)
            socketTCP.connect((self.Master_IP, self.Port_TCP_master))
            socketTCP.sendall(b"REQ_LIST_IDS")
            liste = socketTCP.recv(4096).decode().strip()
            socketTCP.close()
            return liste
        except: 
            return "ERROR"
        
    def recuperer_annuaire_cles(self):
        try:
            socketTCPcle = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            socketTCPcle.settimeout(3)
            socketTCPcle.connect((self.Master_IP, self.Port_TCP_master))
            socketTCPcle.sendall(b"REQ_LIST_KEYS")
            liste = socketTCPcle.recv(8192).decode().strip()
            socketTCPcle.close()
            return liste
        except: return "ERROR"

    def demander_nb_hops(self):
        try:
            socketTCPsaut = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            socketTCPsaut.settimeout(3)
            socketTCPsaut.connect((self.Master_IP, self.Port_TCP_master))
            socketTCPsaut.sendall(b"REQ_NB_ROUTEURS")
            nb = socketTCPsaut.recv(1024).decode().strip()
            socketTCPsaut.close()
            return nb
        except: return "?"
    
    def livrer_au_client_final(self, dest_ip, message):
        journalisation_log(self.mon_id_interne, "LIVRAISON", f"Tente de livrer à {dest_ip}:{self.Port_ecoute_client}")
        try:
            socketTCPclient = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            socketTCPclient.settimeout(3)
            socketTCPclient.connect((dest_ip, self.Port_ecoute_client))
            socketTCPclient.sendall(message.encode())
            socketTCPclient.close()
            journalisation_log(self.mon_id_interne, "LIVRAISON", "Message livré avec succès.")
        except Exception as e:
            journalisation_log(self.mon_id_interne, "ERREUR", f"Échec livraison client final : {e}")
    
    def ecouter_recherche_clients(self):
        socketUDPclient = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        socketUDPclient.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        try:
            socketUDPclient.bind(('0.0.0.0', self.Recherche_Port_client))
            journalisation_log(self.mon_id_interne, "UDP Clients", f"Prêt. ID diffusé : {self.mon_id_interne}")
            while True:
                data, addr = socketUDPclient.recvfrom(1024)
                if data.decode().strip() == "Ou_est_le_routeur?":
                    reponse = f"Je_suis_le_routeur|{self.mon_id_interne}|{self.Port_Routeur}"
                    socketUDPclient.sendto(reponse.encode(), addr)
        except Exception as e:
            journalisation_log(self.mon_id_interne, "ERREUR", f"Erreur UDP Client : {e}")
    
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
                        
                        journalisation_log(module_id, "RECEPTION", f"Oignon reçu de {addr[0]} ({len(data_raw)} octets)")
                        
                        message_clair = self.mon_crypto.dechiffrer(blob_chiffre)
                        
                        if "[Erreur]" in message_clair or not message_clair:
                            journalisation_log(module_id, "PAQUET REJETE", "Échec déchiffrement (mauvaise clé ou format).")
                            conn.sendall(b"Erreur Crypto")
                            continue
                            
                        if message_clair.startswith("CMD_FINAL"):
                            p = message_clair.split('|')
                            dest_ip = p[1]
                            contenu = p[2]
                            journalisation_log(module_id, "CONTENU", f"CMD_FINAL. Destinataire : {dest_ip}")
                            self.livrer_au_client_final(dest_ip, contenu)
                            conn.sendall(b"Message Livre")
                            
                        elif message_clair.startswith("CMD_RELAY"):
                            p = message_clair.split('|')
                            prochaine_id = p[1]
                            reste_blob = p[2]
                            
                            journalisation_log(module_id, "RELAIS", f"Relais vers le nœud ID {prochaine_id}")
                            
                            prochaine_ip, prochain_port = self.demander_ip_au_master(prochaine_id)
                            
                            if prochaine_ip and prochain_port:
                                try:
                                    prochaine_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                                    prochaine_socket.settimeout(15)
                                    prochaine_socket.connect((prochaine_ip, prochain_port))
                                    prochaine_socket.sendall(f"CMD_OIGNON|{reste_blob}".encode())
                                    prochaine_socket.close()
                                    conn.sendall(f"Relaye vers {prochaine_id}".encode())
                                except Exception as e:
                                    journalisation_log(module_id, "ERREUR", f"Échec connexion relais vers {prochaine_id} : {e}")
                                    conn.sendall(b"Erreur Relais")
                            else:
                                journalisation_log(module_id, "ERREUR", f"ID de relais {prochaine_id} inconnu du Master.")
                                conn.sendall(b"Erreur ID")

                    except Exception as e:
                        journalisation_log(module_id, "CRASH TRAITEMENT", f"Erreur fatale de l'oignon : {e}")
                            
                elif commande == "CMD_GET_HOPS":
                    nb = self.demander_nb_hops() 
                    conn.sendall(f"Routeurs disponibles : {nb}".encode())

                elif commande == "CMD_GET_KEYS":
                    conn.sendall(b"[TODO] Liste des cles publiques...")
                
                elif commande == "REQ_LIST_KEYS":
                    conn.sendall(self.recuperer_annuaire_cles().encode())

                elif commande.startswith("CMD_MSG"):
                    journalisation_log(module_id, "ALERTE", f"{addr[0]} a tenté un protocole non sécurisé (CMD_MSG).")
                    conn.sendall("Erreur : Protocole non sécurisé interdit. Utilisez le mode Oignon.".encode())
                
                else:
                    conn.sendall(b"Commande inconnue")
        
        except Exception as e:
            journalisation_log(module_id, "ERREUR", f"Erreur Socket {addr}: {e}")
        finally: 
            conn.close()
    
    def _demarrer_ecoute_tcp(self):
        # C'est l'ancienne boucle principale de start_routeur()
        journalisation_log(self.mon_id_interne, "TCP", f"Prêt à accepter des connexions sur {self.Port_Routeur}")
        serveurSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        serveurSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            serveurSocket.bind(('0.0.0.0', self.Port_Routeur))
            serveurSocket.listen(20)
            while True:
                conn, addr = serveurSocket.accept()
                # On passe seulement conn et addr, l'IP Master est dans self.
                threading.Thread(target=self.handle_connection, args=(conn, addr), daemon=True).start()
        except Exception as e:
            journalisation_log(self.mon_id_interne, "CRASH", f"Erreur Serveur : {e}")
        finally:
            serveurSocket.close()
    