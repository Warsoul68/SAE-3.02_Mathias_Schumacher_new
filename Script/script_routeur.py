import socket 
import threading
import sys
from chiffrement_RSA import CryptoManager

# Config
Port_TCP_master = 6000
Port_UDP_master = 50000

# Ports du Routeur
Port_Routeur = 8080        
Recherche_Port_client = 50001 
Port_ecoute_client = 8888

# Lancement crypto
print("Chargement du module de crytptographie...")
mon_crypto = CryptoManager()

cle_publique = mon_crypto.get_pub_avec_str()
mon_id_interne = "?"

# recherche du master
def trouver_master_et_mon_ip(ip_forcee=None):
    print("[Auto-Config] Recherche intelligente des IPs...")
    
    if ip_forcee:
        return None, ip_forcee
    
    liste_ips = []

    try:
        hostname = socket.gethostname()
        res = socket.gethostbyname_ex(hostname)[2]
        for ip in res:
            if not ip.startswith("127."):
                liste_ips.append(ip)
    except: pass

    try:
        socketUDP = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        socketUDP.connect(("10.0.0.1", 80)) 
        ip_detectee = socketUDP.getsockname()[0]
        if ip_detectee not in liste_ips: liste_ips.append(ip_detectee)
        socketUDP.close()
    except: pass
        
    if not liste_ips:
        liste_ips.append("10.0.0.1")
        liste_ips.append("10.0.0.2")

    print(f"[DEBUG] Liste finale à scanner : {liste_ips}")

    for ip_test in liste_ips:
        if ip_test.startswith("127."): continue

        socketmasterUDP = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        socketmasterUDP.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        socketmasterUDP.settimeout(2)

        try:
            socketmasterUDP.bind((ip_test, 0))
            
            if ip_test.startswith("10."):
                parts = ip_test.split('.')
                broadcast_cible = f"{parts[0]}.{parts[1]}.{parts[2]}.255"
            else:
                broadcast_cible = "<broadcast>"
            
            socketmasterUDP.sendto(b"Ou_est_le_master?", (broadcast_cible, Port_UDP_master))
            
            data, addr = socketmasterUDP.recvfrom(1024)
            if data.decode() == "Je_suis_le_master":
                master_ip = addr[0]
                print(f"[Succès] Master trouvé ({master_ip}) via {ip_test} !")
                socketmasterUDP.close()
                return master_ip, ip_test
        except: pass
        finally:
            socketmasterUDP.close()
            
    return None, None
    
# Enregistrement
def enregistrement_Master(master_ip, mon_ip):
    global mon_id_interne
    try:
        socketTCP = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        socketTCP.settimeout(5)
        socketTCP.connect((master_ip, Port_TCP_master))
        
        message = f"{mon_ip}|{Port_Routeur}|{cle_publique}"
        socketTCP.sendall(message.encode())
        
        ack = socketTCP.recv(1024).decode()
        if "ACK|" in ack:
            mon_id_interne = ack.split('|')[1]
            print(f"[Master] Enregistrement OK. Je suis l'Agent ID : {mon_id_interne}")
            socketTCP.close()
            return True
        else:
            print(f"[Master] Erreur ACK : {ack}")
            return False
    except Exception as e:
        print(f"[Erreur Enregistrement] {e}")
        return False

def demander_ip_au_master(master_ip, id_cible):
    try:
        socketmasterTCP = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        socketmasterTCP.settimeout(3)
        socketmasterTCP.connect((master_ip, Port_TCP_master))
        socketmasterTCP.sendall(f"REQ_RESOLVE_ID|{id_cible}".encode())
        reponse = socketmasterTCP.recv(1024).decode().strip()
        socketmasterTCP.close()
        
        if "ERROR" in reponse: return None, None
        
        parties = reponse.split('|')
        return parties[0], int(parties[1])
    except:
        return None, None
        
def recuperer_annuaire_master(master_ip):
    try:
        socketTCP = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        socketTCP.settimeout(3)
        socketTCP.connect((master_ip, Port_TCP_master))
        socketTCP.sendall(b"REQ_LIST_IDS")
        liste = socketTCP.recv(4096).decode().strip()
        socketTCP.close()
        return liste
    except: 
        return "ERROR"

def recuperer_annuaire_cles(master_ip):
    try:
        socketTCPcle = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        socketTCPcle.settimeout(3)
        socketTCPcle.connect((master_ip, Port_TCP_master))
        socketTCPcle.sendall(b"REQ_LIST_KEYS")
        liste = socketTCPcle.recv(8192).decode().strip()
        socketTCPcle.close()
        return liste
    except: return "ERROR"

def livrer_au_client_final(dest_ip, message):
    print(f"[Livraison] Connexion au Client final {dest_ip}:{Port_ecoute_client}...")
    try:
        socketTCPclient = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        socketTCPclient.settimeout(3)
        socketTCPclient.connect((dest_ip, Port_ecoute_client))
        socketTCPclient.sendall(message.encode())
        socketTCPclient.close()
        print("[Livraison] Succés !")
    except Exception as e:
        print(f"[Livraison] Echec : {e}")

def demander_nb_hops(master_ip):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(3)
        s.connect((master_ip, Port_TCP_master))
        s.sendall(b"REQ_NB_ROUTEURS")
        nb = s.recv(1024).decode().strip()
        s.close()
        return nb
    except: return "?"
        
# Recherche client
def ecouter_recherche_clients():
    socketUDPclient = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    socketUDPclient.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    try:
        socketUDPclient.bind(('0.0.0.0', Recherche_Port_client))
        print(f"[UDP Clients] Prêt. ID diffusé : {mon_id_interne}")
        while True:
            data, addr = socketUDPclient.recvfrom(1024)
            if data.decode().strip() == "Ou_est_le_routeur?":
                reponse = f"Je_suis_le_routeur|{mon_id_interne}"
                socketUDPclient.sendto(reponse.encode(), addr)
    except Exception as e:
        print(f"[UDP Clients] Erreur : {e}")

def handle_connection(conn, addr, master_ip):
    try:
        while True:
            data = conn.recv(8192)
            if not data: break
            commande = data.decode().strip()
            
            if commande == "REQ_LIST_IDS":
                conn.sendall(recuperer_annuaire_master(master_ip).encode())
            
            elif commande.startswith("CMD_OIGNON"):
                try:
                    parties = commande.split('|')
                    blob_chiffre = parties[1]
                    
                    print(f"Oignon reçu de {addr[0]}. Déchiffrement...")
                    
                    message_clair = mon_crypto.dechiffrer(blob_chiffre)
                    
                    if "[Erreur]" in message_clair or not message_clair:
                        print("Echec déchiffremnt. Paquet rejeté.")
                        conn.sendall(b"Erreur Crypto")
                        continue
                        
                    if message_clair.startswith("CMD_FINAL"):
                        p = message_clair.split('|')
                        dest_ip = p[1]
                        contenu = p[2]
                        print(f"Oignon ouvert : Instruction CMD_FINAL -> {dest_ip}")
                        livrer_au_client_final(dest_ip, contenu)
                        conn.sendall(b"Message Livre")
                        
                    elif message_clair.startswith("CMD_RELAY"):
                        p = message_clair.split('|')
                        prochaine_id = p[1]
                        reste_blob = p[2]
                        
                        print(f"🔄 Relais vers ID {prochaine_id}...")
                        
                        prochaine_ip, prochain_port = demander_ip_au_master(master_ip, prochaine_id)
                        
                        if prochaine_ip and prochain_port:
                            try:
                                prochaine_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                                prochaine_socket.connect((prochaine_ip, prochain_port))
                                prochaine_socket.sendall(f"CMD_OIGNON|{reste_blob}".encode())
                                prochaine_socket.close()
                                
                                conn.sendall(f"Relaye vers {prochaine_id}".encode())
                            except Exception as e:
                                print(f"❌ Erreur connexion relais : {e}")
                                conn.sendall(b"Erreur Relais")
                        else:
                            print(f"❌ ID {prochaine_id} inconnu")
                            conn.sendall(b"Erreur ID")

                except Exception as e:
                    print(f"❌ Crash traitement Oignon : {e}")
                                
            elif commande == "CMD_GET_HOPS":
                nb = demander_nb_hops(master_ip)
                conn.sendall(f"Routeurs disponibles : {nb}".encode())

            elif commande == "CMD_GET_KEYS":
                conn.sendall(b"[TODO] Liste des cles publiques...")
            
            elif commande == "REQ_LIST_KEYS":
                conn.sendall(recuperer_annuaire_cles(master_ip).encode())

            elif commande.startswith("CMD_MSG"):
                print(f"[Alerte Sécurité] {addr[0]} a tenté d'envoyer un message en clair !")
                
                conn.sendall("Erreur : Protocole non sécurisé interdit. Utilisez le mode Oignon.".encode())
            else:
                conn.sendall(b"Commande inconnue")
    except Exception as e:
            print(f"[{addr}] Erreur Socket : {e}")
    finally: conn.close()

def start_routeur():
    global Port_Routeur
    
    if len(sys.argv) > 1:
        Port_Routeur = int(sys.argv[1])
    
    print(f"Lancement du routeur sur le port {Port_Routeur}")
    
    master_ip, mon_ip = trouver_master_et_mon_ip()
    if not master_ip: 
        print("Abandon : Pas de Master.")
        return
    
    if not enregistrement_Master(master_ip, mon_ip):
        return

    threading.Thread(target=ecouter_recherche_clients, daemon=True).start()

    serveurSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    serveurSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        serveurSocket.bind(('0.0.0.0', Port_Routeur))
        serveurSocket.listen(20)
        print(f"[Ecoute TCP] Prêt sur le port {Port_Routeur}...")
        while True:
            conn, addr = serveurSocket.accept()
            threading.Thread(target=handle_connection, args=(conn, addr, master_ip), daemon=True).start()
    except Exception as e:
        print(f"Erreur Serveur : {e}")
    finally:
        serveurSocket.close()

if __name__ == "__main__":
    start_routeur()
