import socket
import threading
import sys
import datetime
import time
import random

# Importation de ma classe de chiffrement RSA maison
try:
    from chiffrement_RSA import CryptoManager
except ImportError:
    print("ERREUR CRITIQUE : Le fichier chiffrement_RSA.py est introuvable !")
    sys.exit(1)

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

# Classe Client
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
        self._menu_interactif()
    
    # Module réseaux
    def _module_ecoute_reseau(self):
        socketTCP_Routeur = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        socketTCP_Routeur.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            socketTCP_Routeur.bind(("0.0.0.0", self.port_local))
            socketTCP_Routeur.listen(5)
            journalisation_log(self.nom_log, "ECOUTE", f"Prêt à relayer sur le port {self.port_local}")
        except Exception as e:
            journalisation_log(self.nom_log, "FATAL", f"Impossible d'ouvrir le port d'écoute : {e}")
            return

        while True:
            try:
                conn, addr = socketTCP_Routeur.accept()
                donnees = self._recevoir_tout(conn)
                
                if donnees:
                    try:
                        message_str = donnees.decode('utf-8').strip()
                        if "REQ_LIST_KEYS" in message_str:
                            lignes = []
                            for rid, info in self.annuaire.items():
                                k = info['cle']
                                lignes.append(f"ID:{rid};IP:{info['ip']};PORT:{info['port']};KEY:{k[0]},{k[1]}")
                            conn.sendall("\n".join(lignes).encode('utf-8'))
                            conn.close()
                            continue
                    except: pass

                    threading.Thread(target=self._analyser_paquet, args=(donnees,)).start()

                conn.close()
            except Exception as e:
                pass
    
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
            message_str = donnees_chiffrees.decode('utf-8')

            message_clair = self.crypto.dechiffrer(message_str)

            if not message_clair:
                print(f"[{self.nom_log}] [DEBUG] ❌ Échec déchiffrement (Clé incorrecte ou message corrompu)")
                return

            if "|" not in message_clair: return

            commande, reste_du_paquet = message_clair.split("|", 1)
            
            # Routage vers un autre noeud
            if "NEXT_IP" in commande:
                infos = self._parser_headers(commande)
                journalisation_log(self.nom_log, "ROUTAGE", f"Relayage vers -> {infos['NEXT_IP']}:{infos['NEXT_PORT']}")
                self._envoyer_socket(infos['NEXT_IP'], int(infos['NEXT_PORT']), reste_du_paquet)

            # Sortie vers le client
            elif "RELAY:CLIENT" in commande:
                infos = self._parser_headers(commande)
                dest_ip = infos['IP']
                dest_port = int(infos['PORT'])

                if dest_port == self.port_local:
                    journalisation_log(self.nom_log, "Arrivé", f"Message reçu : {reste_du_paquet}")
                else:
                    journalisation_log(self.nom_log, "Sortie", f"Livraison à {dest_ip}:{dest_port}")
                    self._envoyer_socket(dest_ip, dest_port, reste_du_paquet)

            # Arrivée classique
            elif "DEST:FINAL" in commande:
                journalisation_log(self.nom_log, "ARRIVEE", f"Message reçu : {reste_du_paquet}")

        except Exception as e:
            journalisation_log(self.nom_log, "ERREUR", f"Analyse paquet : {e}")

    # Envoie de message
    def construire_oignon(self, message, chemin_ids, annuaire, mode="CLIENT", ip_c=None, port_c=None):
        id_sortie = chemin_ids[-1]
        cle_sortie = annuaire[id_sortie]['cle']
        
        if mode == "CLIENT":
            header = f"RELAY:CLIENT;IP:{ip_c};PORT:{port_c}"
        else:
            header = "DEST:FINAL"
            
        payload = f"{header}|{message}"
        paquet_chiffre = self.crypto.chiffrer(payload, cle_sortie)
        routeurs_intermediaires = list(reversed(chemin_ids[:-1]))
        id_suivant = id_sortie 

        for id_actuel in routeurs_intermediaires:
            info_suiv = annuaire[id_suivant]
            cle_actu = annuaire[id_actuel]['cle']
            instruction = f"NEXT_IP:{info_suiv['ip']};NEXT_PORT:{info_suiv['port']}|{paquet_chiffre}"
            paquet_chiffre = self.crypto.chiffrer(instruction, cle_actu)
            id_suivant = id_actuel

        return paquet_chiffre

    def envoyer_message_depuis_routeur(self):
        self.client_recuperer_annuaire()
        
        if not self.annuaire:
            print("[!] Annuaire vide ou Master inaccessible.")
            return

        print("\nEnvoie depuis le routeur")
        target_ip = input("IP du destinataire (Client ou Routeur) : ")
        try:
            target_port = int(input("Port du destinataire : "))
            msg = input("Message : ")
            nb_sauts = int(input("Nombre de routeurs relais : ") or 1)
        except ValueError:
            print("Erreur de saisie.")
            return
        
        ids_dispos = list(self.annuaire.keys())
        exit_node_id = random.choice(ids_dispos)
        relais = [i for i in ids_dispos if i != exit_node_id]
        
        chemin = random.sample(relais, min(nb_sauts-1, len(relais))) + [exit_node_id]

        paquet = self.construire_oignon(msg, chemin, self.annuaire, mode="CLIENT", ip_c=target_ip, port_c=target_port)

        try:
            id_in = chemin[0]
            journalisation_log(self.nom_log, "ENVOI", f"Expédition via circuit {chemin}")
            self._envoyer_socket(self.annuaire[id_in]['ip'], self.annuaire[id_in]['port'], paquet)
            print("[+] Message envoyé.")
        except Exception as e:
            print(f"Erreur d'envoi : {e}")
    
    # Gestion master
    def client_inscription(self):
        try:
            e, n = self.crypto.publique
            
            # --- MÉTHODE FIABLE POUR TROUVER L'IP BRIDGE ---
            # On crée un socket temporaire pour "voir" par où on sort
            s_test = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                # On ne se connecte pas vraiment, on demande juste l'IP de sortie
                s_test.connect(("8.8.8.8", 80))
                mon_ip_publique = s_test.getsockname()[0]
                s_test.close()
            except Exception:
                mon_ip_publique = "127.0.0.1"

            if mon_ip_publique.startswith("127.") or mon_ip_publique.startswith("10.0."):
                print(f"\n[!] Attention : IP détectée ({mon_ip_publique}) invalide pour le PC physique.")
                mon_ip_publique = input("Entrez manuellement l'IP BRIDGE de cette VM (ex: 192.168.1.XX) : ")

            # Envoi au Master
            requete = f"INSCRIPTION|{mon_ip_publique}|{self.port_local}|{e},{n}"
            self._envoyer_socket(self.ip_master, self.port_master, requete)
            
            journalisation_log(self.nom_log, "MASTER", f"Inscrit avec l'IP : {mon_ip_publique}")
            
            time.sleep(0.5)
            self.client_recuperer_annuaire()
        except Exception as e:
            journalisation_log(self.nom_log, "ERREUR", f"Inscription : {e}")


    def client_recuperer_annuaire(self):
        try:
            socketTCPannuaire = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            socketTCPannuaire.settimeout(2) 
            socketTCPannuaire.connect((self.ip_master, self.port_master))
            socketTCPannuaire.sendall(b"REQ_LIST_KEYS")
            reponse = self._recevoir_tout(socketTCPannuaire).decode('utf-8')
            socketTCPannuaire.close()
            
            self.annuaire = {}
            for ligne in reponse.split('\n'):
                if "ID:" in ligne:
                    d = self._parser_headers(ligne)
                    k = d['KEY'].split(',')
                    self.annuaire[d['ID']] = {'ip': d['IP'], 'port': int(d['PORT']), 'cle': (int(k[0]), int(k[1]))}
            journalisation_log(self.nom_log, "ANNUAIRE", f"{len(self.annuaire)} nœuds synchronisés.")
        except Exception as e:
            journalisation_log(self.nom_log, "ERREUR", f"Annuaire : {e}")
    
    def _menu_interactif(self):
        while True:
            print(f"\n Routeur hybride {self.port_local} ---")
            print("1. S'inscrire & Sync Annuaire")
            print("2. Voir l'annuaire local")
            print("3. Envoyer un message (Mode Client)")
            print("0. Quitter")
            c = input("Choix > ")
            if c == "1": self.client_inscription()
            elif c == "2": 
                for k,v in self.annuaire.items(): print(f"ID {k} -> {v['ip']}:{v['port']}")
            elif c == "3": self.envoyer_message_depuis_routeur()
            elif c == "0": break

    def _envoyer_socket(self, ip, port, message):
        try:
            socketTCPenvoie = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            socketTCPenvoie.connect((ip, port))
            socketTCPenvoie.sendall(message.encode('utf-8'))
            socketTCPenvoie.close()
        except Exception as e:
            print(f"Erreur envoi -> {ip}:{port} : {e}")

    def _parser_headers(self, chaine):
        res = {}
        parties = chaine.replace('|', ';').split(';')
        for p in parties:
            if ':' in p:
                k, v = p.split(':', 1)
                res[k.strip()] = v.strip()
        return res