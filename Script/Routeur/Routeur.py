import socket
import threading
import sys
import datetime
import time

# Import de la classe de chiffrement maison
try:
    from chiffrement_RSA import CryptoManager
except ImportError:
    print("ERREUR CRITIQUE : Le fichier chiffrement_RSA.py est introuvable !")
    sys.exit(1)

# Gestion des logs
def journalisation_log(qui, type_message, message):
    maintenant = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ligne_log = f"[{maintenant}] [{qui}] [{type_message}] {message}"
    
    # Affichage de la console
    print(ligne_log)

    # écriture du fichier pour les logs
    nom_fichier = f"journal_{qui.lower()}.log"
    try:
        with open(nom_fichier, "a", encoding="utf-8") as f:
            f.write(ligne_log + "\n")
    except Exception as e:
        print(f"Erreur d'écriture log : {e}")

# Classe du routeur
class Routeur:
    def __init__(self, port_local, ip_master, port_master):
        self.port_local = port_local
        self.ip_master = ip_master
        self.port_master = port_master
        
        self.nom_log = f"ROUTEUR_{port_local}"
        self.annuaire = {} 
        
        journalisation_log(self.nom_log, "INIT", "Démarrage du Nœud...")
        
        # Initialisation de ma classe de chiffrement
        self.crypto = CryptoManager()
        
        # Vérification clé
        if self.crypto.publique is None:
            journalisation_log(self.nom_log, "ERREUR", "Clé publique non chargée (vérifiez chiffrement_RSA.py).")

    def demarrer(self):
        # Thread pour l'interface routeur
        thread_ecoute = threading.Thread(target=self._module_ecoute_reseau, daemon=True)
        thread_ecoute.start()
        
        # Thread pour l'interface client
        self._menu_client()
    
    # Module d'écoute 
    def _module_ecoute_reseau(self):
        socketTCP_routeur = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        socketTCP_routeur.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            socketTCP_routeur.bind(("0.0.0.0", self.port_local))
            socketTCP_routeur.listen(5)
            journalisation_log(self.nom_log, "ECOUTE", f"Prêt à relayer sur le port {self.port_local}")
        except Exception as e:
            journalisation_log(self.nom_log, "FATAL", f"Impossible d'ouvrir le port d'écoute : {e}")
            return

        while True:
            connexion_entrante, addr = socketTCP_routeur.accept()
            donnees = self._recevoir_tout(connexion_entrante)
            
            if donnees:
                try:
                    message_str = donnees.decode('utf-8')
                    if message_str == "REQ_LIST_KEYS":
                        journalisation_log(self.nom_log, "CLIENT", f"Envoi de l'annuaire local à {addr[0]}")
                        
                        lignes = []
                        for rid, info in self.annuaire.items():
                            cle_tuple = info['cle']
                            cle_str = f"{cle_tuple[0]},{cle_tuple[1]}"
                            lignes.append(f"ID:{rid};IP:{info['ip']};PORT:{info['port']};KEY:{cle_str}")
                        
                        reponse = "\n".join(lignes)
                        connexion_entrante.sendall(reponse.encode('utf-8'))
                        connexion_entrante.close()
                        continue
                except:
                    pass
                try:
                    apercu = donnees.decode('utf-8')
                    if len(apercu) > 50: apercu = apercu[:50] + "..."
                    type_msg = "🔒 CRYPTÉ" if (len(apercu) > 0 and apercu[0].isdigit()) else "⚠️ CLAIR"
                    print(f"\n[flux entrant] {type_msg} De {addr[0]} : {apercu}")
                except: pass

                threading.Thread(target=self._analyser_paquet, args=(donnees,)).start()
            try:
                connexion_entrante.close()
            except: pass
    
    def _recevoir_tout(self, socketTCPrecevoir):
        contenu = b""
        socketTCPrecevoir.settimeout(2)
        try:
            while True:
                partie = socketTCPrecevoir.recv(4096)
                if not partie: break
                contenu += partie
        except: pass
        return contenu
    
    def _analyser_paquet(self, donnees_chiffrees):
        try:
            message_str = donnees_chiffrees.decode('utf-8')
            message_clair = self.crypto.dechiffrer(message_str)
            
            if not message_clair or "|" not in message_clair:
                return

            commande, reste_du_paquet = message_clair.split("|", 1)
            
            if "NEXT_IP" in commande:
                infos = self._parser_headers(commande)
                ip_suiv = infos['NEXT_IP']
                port_suiv = int(infos['NEXT_PORT'])
                
                journalisation_log(self.nom_log, "ROUTAGE", f"Relayage vers -> {ip_suiv}:{port_suiv}")
                self._envoyer_socket(ip_suiv, port_suiv, reste_du_paquet)
                
            elif "DEST:FINAL" in commande:
                journalisation_log(self.nom_log, "ARRIVEE", f"Message reçu : {reste_du_paquet}")
                print("\n(Appuyez sur Entrée pour rafraîchir le menu)")

        except Exception as e:
            journalisation_log(self.nom_log, "ERREUR", f"Problème lors de l'analyse : {e}")
    
    # Module client
    def _menu_client(self):
        time.sleep(1)
        while True:
            print(f"\n Noeud du réseau ({self.port_local})")
            print("1. S'inscrire au Master")
            print("2. Mettre à jour l'annuaire")
            print("3. Envoyer un message (Mode Client)")
            print("0. Quitter")
            
            choix = input("Choix > ")
            
            if choix == "1": self.client_inscription()
            elif choix == "2": self.client_recuperer_annuaire()
            elif choix == "3": self.client_envoyer_oignon()
            elif choix == "0": break
    
    def client_inscription(self):
        try:
            if self.crypto.publique is None:
                print("Erreur : Pas de clé publique !")
                return

            e, n = self.crypto.publique
            
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect((self.ip_master, self.port_master))
                mon_ip = s.getsockname()[0]
                s.close()
            except Exception:
                mon_ip = "127.0.0.1"

            print(f"[*] Détection IP : Je m'inscris avec l'IP {mon_ip}")
            
            requete = f"INSCRIPTION|{mon_ip}|{self.port_local}|{e},{n}"
            
            self._envoyer_socket(self.ip_master, self.port_master, requete)
            journalisation_log(self.nom_log, "CLIENT", f"Inscription envoyée ({mon_ip}).")
            
        except Exception as e:
            journalisation_log(self.nom_log, "ERREUR", f"Inscription impossible : {e}")
    
    def client_recuperer_annuaire(self):
        try:
            socketTCP_client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            socketTCP_client.connect((self.ip_master, self.port_master))
            socketTCP_client.sendall(b"REQ_LIST_KEYS")
            reponse = self._recevoir_tout(socketTCP_client).decode('utf-8')
            socketTCP_client.close()
            self.annuaire = {}
            lignes = reponse.split('\n')
            
            for ligne in lignes:
                if "ID:" in ligne:
                    d = self._parser_headers(ligne)
                    k_parts = d['KEY'].split(',')
                    cle_tuple = (int(k_parts[0]), int(k_parts[1]))
                    
                    self.annuaire[d['ID']] = {
                        'ip': d['IP'],
                        'port': int(d['PORT']),
                        'cle': cle_tuple
                    }
            journalisation_log(self.nom_log, "CLIENT", f"Annuaire mis à jour ({len(self.annuaire)} nœuds).")
            
        except Exception as e:
            journalisation_log(self.nom_log, "ERREUR", f"Récupération annuaire : {e}")
    
    def client_envoyer_oignon(self):
        if len(self.annuaire) < 2:
            print("Annuaire vide pour faire du routage oignon.")
            return

        print("\n Nœuds disponibles")
        for rid, info in self.annuaire.items():
            print(f"ID {rid} -> {info['ip']}:{info['port']}")
        
        id_dest = input("ID Destinataire : ")
        if id_dest not in self.annuaire: return print("ID Inconnu.")
            
        msg_clair = input("Message : ")

        try:
            cle_dest = self.annuaire[id_dest]['cle']
            payload = f"DEST:FINAL|{msg_clair}"
            paquet_final = self.crypto.chiffrer(payload, cle_dest)

            id_relais = input("ID du Relais : ")
            if id_relais not in self.annuaire: return print("ID Relais inconnu.")

            cle_relais = self.annuaire[id_relais]['cle']
            info_dest = self.annuaire[id_dest]
            
            instruction = f"NEXT_IP:{info_dest['ip']};NEXT_PORT:{info_dest['port']}|{paquet_final}"
            paquet_complet = self.crypto.chiffrer(instruction, cle_relais)

            journalisation_log(self.nom_log, "CLIENT", f"Envoi du paquet via le relais {id_relais}")
            self._envoyer_socket(self.annuaire[id_relais]['ip'], self.annuaire[id_relais]['port'], paquet_complet)
            
        except Exception as e:
            journalisation_log(self.nom_log, "ERREUR", f"Création oignon : {e}")
    
    # Outils
    def _envoyer_socket(self, ip, port, message):
        socketTCPenvoyer = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        socketTCPenvoyer.connect((ip, port))
        socketTCPenvoyer.sendall(message.encode('utf-8'))
        socketTCPenvoyer.close()

    def _parser_headers(self, chaine):
        res = {}
        parties = chaine.replace('|', ';').split(';')
        for p in parties:
            if ':' in p:
                k, v = p.split(':', 1)
                res[k.strip()] = v.strip()
        return res