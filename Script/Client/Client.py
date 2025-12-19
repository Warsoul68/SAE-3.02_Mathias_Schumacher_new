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
        ip_dest, port_dest = cible 
        ids = list(self.annuaire_cache.keys())
        
        if not ids:
            journalisation_log("CLIENT", "ERREUR", "Annuaire vide. Envoi impossible.")
            return "Erreur"

        id_cible_dans_annuaire = None
        for rid, info in self.annuaire_cache.items():
            if str(info['port']) == str(port_dest):
                id_cible_dans_annuaire = rid
                break

        relais_pour_entree = [i for i in ids if i != id_cible_dans_annuaire]
        
        if not relais_pour_entree:
            id_entree = id_cible_dans_annuaire
            journalisation_log("CLIENT", "ALERTE", "Un seul nœud dispo : l'entrée sera la cible.")
        else:
            id_entree = random.choice(relais_pour_entree)

        autres_noeuds_dispos = [i for i in ids if i != id_entree]
        nb_relais_supp = min(nb_sauts - 1, len(autres_noeuds_dispos))
        chemin = [id_entree]
        if nb_relais_supp > 0:
            chemin += random.sample(autres_noeuds_dispos, nb_relais_supp)

        try:
            journalisation_log("CLIENT", "OIGNON", f"Circuit créé : {chemin} (Cible: {ip_dest}:{port_dest})")
            
            paquet = self.construire_oignon(
                message=message, 
                chemin_ids=chemin, 
                annuaire=self.annuaire_cache, 
                mode="CLIENT", 
                ip_c=ip_dest, 
                port_c=port_dest
            )
            
            info_entree = self.annuaire_cache[id_entree]
            if str(info_entree['port']) == str(self.Routeur_Port):
                ip_connexion = self.Routeur_IP # On utilise l'IP locale (10.x.x.x)
                interface_type = "LOCALE (Intnet)"
            else:
                ip_connexion = info_entree['ip'] # On utilise l'IP de l'annuaire (Bridge)
                interface_type = "PUBLIQUE (Bridge)"

            port_connexion = info_entree['port']
            journalisation_log("CLIENT", "ROUTAGE", f"Connexion via {interface_type} vers {ip_connexion}:{port_connexion}")
            
            socket_envoi = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            socket_envoi.settimeout(5.0) 
            socket_envoi.connect((ip_connexion, port_connexion))
            socket_envoi.sendall(paquet.encode('utf-8'))
            
            time.sleep(0.15) 
            socket_envoi.close()
            
            journalisation_log("CLIENT", "SUCCÈS", f"Paquet livré au premier saut : {id_entree}")
            return "Succès"

        except Exception as e:
            journalisation_log("CLIENT", "ERREUR", f"Échec de l'expédition : {e}")
            return f"Erreur : {e}"