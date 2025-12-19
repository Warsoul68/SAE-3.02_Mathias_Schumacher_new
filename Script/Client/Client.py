import socket 
import threading
import random
import datetime
import sys
import time

# Importation de ma classe de chiffrement RSA maison
try:
    from chiffrement_RSA import CryptoManager 
except ImportError:
    print("ERREUR : chiffrement_RSA.py manquant.")
    sys.exit(1)

# Système de callback pour les logs
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
        with open("journal_client.log", "a", encoding="utf-8") as f:
            f.write(ligne_log + "\n")
    except: pass

# Classe Client 
class Client:
    def __init__(self, routeur_ip, routeur_port, port_ecoute_local):
        self.Routeur_IP = routeur_ip
        self.Routeur_Port = routeur_port
        self.Port_en_ecoute = port_ecoute_local
        self.crypto_outils = CryptoManager()
        self.annuaire_cache = {}
        
        self._lancer_ecoute_reception()
        journalisation_log("CLIENT", "INIT", f"Connecté à la Passerelle {self.Routeur_IP}:{self.Routeur_Port}")

    def _lancer_ecoute_reception(self):
        t = threading.Thread(target=self._ecouter_message_entrants, daemon=True)
        t.start()

    def _recevoir_tout(self, sock):
        contenu = b""
        sock.settimeout(2.0)
        try:
            while True:
                partie = sock.recv(8192)
                if not partie: break
                contenu += partie
                if len(partie) < 8192:
                    break
        except: pass
        return contenu

    def _ecouter_message_entrants(self):
        socketTCPentrant = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        socketTCPentrant.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            socketTCPentrant.bind(("0.0.0.0", self.Port_en_ecoute)) 
            socketTCPentrant.listen(5)
            journalisation_log("CLIENT", "ECOUTE", f"Client prêt à recevoir sur le port {self.Port_en_ecoute}")
            while True:
                try:
                    conn, addr = socketTCPentrant.accept()
                    data = self._recevoir_tout(conn)
                    if data:
                        message = data.decode('utf-8', errors='ignore')
                        journalisation_log("CLIENT", "RECEPTION", f"Message reçu : {message}")
                    conn.close()
                except: pass
        except Exception as e:
            journalisation_log("CLIENT", "ERREUR", f"Erreur écoute réception : {e}")
    
    def recuperer_annuaire_complet(self):
        try:
            socketTCPannuaire = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            socketTCPannuaire.settimeout(5.0)
            socketTCPannuaire.connect((self.Routeur_IP, self.Routeur_Port))
            socketTCPannuaire.sendall(b"REQ_LIST_KEYS")
            reponse_bytes = self._recevoir_tout(socketTCPannuaire)
            socketTCPannuaire.close()
            
            reponse = reponse_bytes.decode("utf-8")
            annuaire = {}
            for ligne in reponse.split('\n'):
                if "ID:" in ligne:
                    parties = ligne.replace('|', ';').split(';')
                    infos = {p.split(':')[0]: p.split(':')[1] for p in parties if ':' in p}
                    k = infos['KEY'].split(',')
                    annuaire[infos['ID']] = {
                        'ip': infos['IP'], 
                        'port': int(infos['PORT']),
                        'cle': (int(k[0]), int(k[1]))
                    }
            self.annuaire_cache = annuaire
            journalisation_log("CLIENT", "INFO", f"{len(annuaire)} nœuds réseau chargés.")
            return annuaire
        except Exception as e:
            journalisation_log("CLIENT", "ERREUR", f"Impossible de récupérer l'annuaire : {e}")
            return {}
    
    def construire_oignon(self, message, chemin_ids, annuaire, mode="CLIENT", ip_c=None, port_c=None):
        id_sortie = chemin_ids[-1]
        cle_sortie = annuaire[id_sortie]['cle']
        
        if mode == "CLIENT":
            header = f"RELAY:CLIENT;IP:{ip_c};PORT:{port_c}"
        else:
            header = "DEST:FINAL"
            
        payload = f"{header}|{message}"
        paquet_chiffre = self.crypto_outils.chiffrer(payload, cle_sortie)
        routeurs_intermediaires = list(reversed(chemin_ids[:-1]))
        id_suivant = id_sortie 

        for id_actuel in routeurs_intermediaires:
            info_suiv = annuaire[id_suivant]
            cle_actu = annuaire[id_actuel]['cle']
            instruction = f"NEXT_IP:{info_suiv['ip']};NEXT_PORT:{info_suiv['port']}|{paquet_chiffre}"
            paquet_chiffre = self.crypto_outils.chiffrer(instruction, cle_actu)
            id_suivant = id_actuel

        return paquet_chiffre
    
    def envoyer_message(self, cible, message, nb_sauts):
        self.recuperer_annuaire_complet()
            
        ids = list(self.annuaire_cache.keys())
        
        if len(ids) < nb_sauts: 
            nb_sauts = len(ids)
            journalisation_log("CLIENT", "INFO", f"Adaptation à {nb_sauts} sauts (max dispo).")
            
        if nb_sauts == 0:
             journalisation_log("CLIENT", "ERREUR", "Aucun routeur disponible.")
             return "Erreur: Annuaire vide"

        dest_id = random.choice(ids)
        relais_possibles = [i for i in ids if i != dest_id]
        chemin = random.sample(relais_possibles, min(nb_sauts-1, len(relais_possibles))) + [dest_id]
        
        try:
            journalisation_log("CLIENT", "OIGNON", f"Création circuit anonyme : {chemin}")
            ip_dest, port_dest = cible 
            
            paquet = self.construire_oignon(message, chemin, self.annuaire_cache, "CLIENT", ip_dest, port_dest)
            
            id_entree = chemin[0]
            ip_entree = self.annuaire_cache[id_entree]['ip']
            port_entree = self.annuaire_cache[id_entree]['port']
            socket_envoi = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            socket_envoi.settimeout(5.0) # 5s pour se connecter (réseau bridge parfois lent)
            socket_envoi.connect((ip_entree, port_entree))
            socket_envoi.sendall(paquet.encode('utf-8'))
            time.sleep(0.1) # CRUCIAL : Flush du buffer avant fermeture
            socket_envoi.close()
            
            journalisation_log("CLIENT", "ENVOI", f"Paquet expédié vers l'entrée {id_entree}")
            return "Succès"

        except Exception as e:
            journalisation_log("CLIENT", "ERREUR", f"Échec de l'envoi : {e}")
            return f"Erreur : {e}"