import socket 
import threading
import time
import random
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

# Classe client

class Client:
    def __init__(self, routeur_ip, routeur_port, port_en_ecoute):
        self.Routeur_IP_Passerelle = routeur_ip
        self.Port_Routeur_Passerelle = routeur_port
        self.Port_en_ecoute = port_en_ecoute
        self.crypto_outils = CryptoManager()
        self._lancer_ecoute_reception()
        journalisation_log("CLIENT", "INIT", f"Client prêt. Écoute sur port {self.Port_en_ecoute}. Passerelle : {routeur_ip}:{routeur_port}")

    # Methode interne
    
    def _lancer_ecoute_reception(self):
        threading.Thread(target=self._ecouter_message_entrants, daemon=True).start()

    def _ecouter_message_entrants(self):
        try:
            socket_serveur = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            socket_serveur.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            # Utilisation de self.Port_en_ecoute
            socket_serveur.bind(("0.0.0.0", self.Port_en_ecoute)) 
            socket_serveur.listen(5)

            while True:
                conn, addr = socket_serveur.accept()
                # Votre code de réception ici...
                data = conn.recv(4096) 
                message = data.decode("utf-8")
                journalisation_log("CLIENT", "RECEPTION", f"Message reçu de {addr[0]}. Contenu : {message[:20]}...")
                print("Appuyer sur Entrée pour rafraîchir le menu...")
                conn.close()
        except: 
            journalisation_log("CLIENT", "ERREUR", "Erreur lors de l'écoute du port de réception.")
            pass
    
    def _envoyer_commande_routeur(self, commande):
        try:
            socketTCP = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            socketTCP.settimeout(20)
            socketTCP.connect((self.Routeur_IP_Passerelle, self.Port_Routeur_Passerelle))
            socketTCP.sendall(commande.encode("utf-8"))
            reponse = socketTCP.recv(4096).decode("utf-8")
            socketTCP.close()
            return reponse
        except Exception as e:
            journalisation_log("CLIENT", "ERREUR", f"Échec envoi commande Master via Passerelle : {e}")
            return "ERROR"
    
    def recuperer_annuaire_complet(self):
        journalisation_log("CLIENT", "ANNUAIRE", f"Demande d'annuaire au routeur {self.Routeur_IP_Passerelle}")
        
        try:
            socketTCP = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            socketTCP.settimeout(20)
            
            # Utilisation des attributs de la classe (self.)
            socketTCP.connect((self.Routeur_IP_Passerelle, self.Port_Routeur_Passerelle))
            
            socketTCP.sendall(b"REQ_LIST_KEYS")
            reponse = socketTCP.recv(65536).decode("utf-8")
            socketTCP.close()
            
        except Exception as e:
            journalisation_log("CLIENT", "ERREUR", f"Échec récupération annuaire : {e}")
            return {}
        
        annuaire = {}
        if not reponse or "ERROR" in reponse: 
            return annuaire

        lignes_routeurs = reponse.split('|')

        for ligne in lignes_routeurs:
            if not ligne.strip(): continue
            try:
                if ';' in ligne:
                    champs = ligne.split(';')
                else:
                    champs = ligne.split(',')

                infos = {}
                for champ in champs:
                    if ':' in champ:
                        parties = champ.split(':', 1)
                        if len(parties) == 2:
                            infos[parties[0]] = parties[1]
                
                if 'ID' in infos and 'KEY' in infos:
                    id_r = infos['ID']
                    cle_str = infos['KEY'].strip()

                    parts_cle = cle_str.split(',')
                    
                    if len(parts_cle) >= 2:
                        e_val = parts_cle[0]
                        n_val = parts_cle[1]
                        
                        annuaire[id_r] = {
                            'ip': infos.get('IP', ''),
                            'port': int(infos.get('PORT', self.Port_Routeur_Passerelle)),
                            'cle': (int(e_val), int(n_val))
                        }
                    else:
                        print(f"Clé ignorée (format incorrect) : {cle_str}")

            except Exception as e:
                print(f"Erreur parsing ligne : {e}")
                pass

        return annuaire
    
    def construire_oignon(self, message, chemin_ids, annuaire_complet, id_dest_final):
        blob = f"CMD_FINAL|{id_dest_final}|{message}"

        dernier_id = chemin_ids[-1]
        cle_derniere = annuaire_complet[dernier_id]['cle']
        blob_chiffre = self.crypto_outils.chiffrer(blob, cle_derniere)

        routeur_restants = list(reversed(chemin_ids[:-1]))

        prochain_saut = dernier_id

        for id_routeur in routeur_restants:
            cle = annuaire_complet[id_routeur]['cle']
            nouvelle_instruction = f"CMD_RELAY|{prochain_saut}|{blob_chiffre}"
            blob_chiffre = self.crypto_outils.chiffrer(nouvelle_instruction, cle)
            prochain_saut = id_routeur

        return f"CMD_OIGNON|{blob_chiffre}"
    
    def envoyer_message(self, dest_ip, message, nb_sauts):
        
        annuaire = self.recuperer_annuaire_complet()
        ids_dispo = list(annuaire.keys())
        nb_routeurs_total = len(ids_dispo)

        if nb_routeurs_total == 0:
            journalisation_log("CLIENT", "ERREUR", "Impossible d'envoyer. Annuaire vide.")
            return "ERROR: Annuaire vide."
            
        if not (1 <= nb_sauts <= nb_routeurs_total):
            journalisation_log("CLIENT", "ERREUR", f"Nombre de sauts invalide ({nb_sauts}). Max: {nb_routeurs_total}.")
            return "ERROR: Nombre de sauts invalide."
        chemin = random.sample(ids_dispo, nb_sauts)
        
        try:
            journalisation_log("CLIENT", "ENVOI", f"Construction Oignon ({nb_sauts} sauts) via {chemin} vers {dest_ip}")
            paquet_final = self.construire_oignon(message, chemin, annuaire, dest_ip) 

            premier_id = chemin[0]

            ip_cible = annuaire[premier_id]['ip']
            port_cible = annuaire[premier_id]['port']

            journalisation_log("CLIENT", "ENVOI", f"Connexion 1er saut ID {premier_id} ({ip_cible}:{port_cible})")
            socketTCP = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            socketTCP.settimeout(20)
            socketTCP.connect((ip_cible, port_cible)) 
            socketTCP.sendall(paquet_final.encode())
            rep = socketTCP.recv(4096).decode()
            socketTCP.close()

            journalisation_log("CLIENT", "SUCCES", f"Message envoyé. Réponse du 1er saut : {rep[:15]}...")
            return "SUCCES"

        except Exception as e:
            journalisation_log("CLIENT", "ERREUR", f"Crash envoi/reception du message : {e}")
            return f"ERREUR: {e}"