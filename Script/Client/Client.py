import socket 
import threading
import time
import random
import datetime
import sys

# Import de la classe de chiffrement maison
try:
    from chiffrement_RSA import CryptoManager 
except ImportError:
    print("ERREUR : chiffrement_RSA.py manquant.")
    sys.exit(1)

# definition du callback pour les logs
CALLBACK_LOG_CLIENT = None
def definir_callback_client(fonction):
    global CALLBACK_LOG_CLIENT
    CALLBACK_LOG_CLIENT = fonction

def journalisation_log(qui, type_message, message):
    maintenant = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ligne_log = f"[{maintenant}] [{qui}] [{type_message}] {message}"
    print(ligne_log)
    
    if CALLBACK_LOG_CLIENT:
        try: CALLBACK_LOG_CLIENT(ligne_log)
        except: pass

    try:
        with open(f"journal_{qui.lower()}.log", "a", encoding="utf-8") as f:
            f.write(ligne_log + "\n")
    except: pass

def recevoir_tout(sock):
    donnees = b""
    sock.settimeout(5)
    try:
        while True:
            chunk = sock.recv(4096)
            if not chunk: break
            donnees += chunk
    except: pass
    return donnees

# Classe Client
class Client:
    def __init__(self, ip_routeur, port_routeur, port_ecoute_local):
        self.Ip_Routeur = ip_routeur
        self.Port_Routeur = port_routeur
        self.Port_en_ecoute = port_ecoute_local
        
        self.crypto_outils = CryptoManager()
        self.arret_ecoute = False
        
        self._lancer_ecoute_reception()
        journalisation_log("CLIENT", "INIT", f"Client connecté à la passerelle {self.Ip_Routeur}:{self.Port_Routeur}")

    def _lancer_ecoute_reception(self):
        t = threading.Thread(target=self._ecouter_message_entrants, daemon=True)
        t.start()

    def _ecouter_message_entrants(self):
        socketTCP = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        socketTCP.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            socketTCP.bind(("0.0.0.0", self.Port_en_ecoute)) 
            socketTCP.listen(5)
            while not self.arret_ecoute:
                try:
                    conn, addr = socketTCP.accept()
                    data = recevoir_tout(conn)
                    if data:
                        msg = data.decode('utf-8', errors='ignore')
                        journalisation_log("CLIENT", "RECEPTION", f"Réponse reçue : {msg}")
                    conn.close()
                except: pass
        except Exception as e:
            journalisation_log("CLIENT", "ERREUR", f"Erreur écoute : {e}")
    
    def recuperer_annuaire_complet(self):
        journalisation_log("CLIENT", "ANNUAIRE", f"Demande envoyée au Routeur {self.Ip_Routeur}...")
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((self.Ip_Routeur, self.Port_Routeur))
            s.sendall(b"REQ_LIST_KEYS")
            reponse = recevoir_tout(s).decode("utf-8")
            s.close()
            
            annuaire = {}
            if not reponse: return {}

            for ligne in reponse.split('\n'):
                if "ID:" in ligne:
                    parties = ligne.replace('|', ';').split(';')
                    infos = {}
                    for p in parties:
                        if ':' in p:
                            k, v = p.split(':', 1)
                            infos[k.strip()] = v.strip()
                    
                    if 'KEY' in infos:
                        k = infos['KEY'].split(',')
                        annuaire[infos['ID']] = {
                            'ip': infos['IP'],
                            'port': int(infos['PORT']),
                            'cle': (int(k[0]), int(k[1]))
                        }
            journalisation_log("CLIENT", "INFO", f"{len(annuaire)} nœuds reçus du routeur.")
            return annuaire
        except Exception as e:
            journalisation_log("CLIENT", "ERREUR", f"Impossible de joindre le Routeur : {e}")
            return {}
    
    def construire_oignon(self, message, chemin_ids, annuaire):
        id_dest = chemin_ids[-1]
        cle_dest = annuaire[id_dest]['cle']
        payload = f"DEST:FINAL|{message}"
        paquet_chiffre = self.crypto_outils.chiffrer(payload, cle_dest)
        routeurs_intermediaires = list(reversed(chemin_ids[:-1]))
        id_suivant = id_dest 

        for id_actuel in routeurs_intermediaires:
            info_suivant = annuaire[id_suivant]
            cle_actuel = annuaire[id_actuel]['cle']
            
            instruction = f"NEXT_IP:{info_suivant['ip']};NEXT_PORT:{info_suivant['port']}|{paquet_chiffre}"
            paquet_chiffre = self.crypto_outils.chiffrer(instruction, cle_actuel)
            id_suivant = id_actuel

        return paquet_chiffre
    
    def envoyer_message_oignon(self, id_entree, id_sortie, message, relais_intermediaires=[]):
        annuaire = self.recuperer_annuaire_complet()
        if not annuaire: return "Annuaire vide ou Routeur injoignable"

        chemin = [id_entree] + relais_intermediaires + [id_sortie]
        
        for pid in chemin:
            if pid not in annuaire: return f"ID inconnu : {pid}"

        try:
            journalisation_log("CLIENT", "OIGNON", f"Construction du circuit : {chemin}")
            paquet_final = self.construire_oignon(message, chemin, annuaire)
            ip_entree = annuaire[id_entree]['ip']
            port_entree = annuaire[id_entree]['port']
            
            journalisation_log("CLIENT", "ENVOI", f"Expédition au nœud d'entrée {id_entree} ({ip_entree}:{port_entree})")
            
            socketTCPclient = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            socketTCPclient.connect((ip_entree, port_entree))
            socketTCPclient.sendall(paquet_final.encode('utf-8'))
            socketTCPclient.close()
            return "Oignon expédié au routeur."
            
        except Exception as e:
            journalisation_log("CLIENT", "ERREUR", f"Echec envoi : {e}")
            return f"Erreur : {e}"