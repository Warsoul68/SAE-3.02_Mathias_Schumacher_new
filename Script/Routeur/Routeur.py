import socket
import threading
import sys
import time

# Import de la classe de chiffrement maison 
try:
    from chiffrement_RSA import CryptoManager
except ImportError:
    print("ERREUR : Le fichier chiffrement_RSA.py est introuvable !")
    sys.exit()

class Routeur:
    def __init__(self, port_local, master_ip, master_port):
        self.port_local = port_local
        self.master_ip = master_ip
        self.master_port = master_port
        self.annuaire = {}
        print(f"[*] Initialisation du module de chiffrement sur le port {self.port_local}...")
        self.crypto = CryptoManager()
        
    def demarrer(self):
        thread_reception = threading.Thread(target=self._ecouter_reseau, daemon=True)
        thread_reception.start()
        self._menu_interactif()
    
    # Partie Relais et reception
    def _ecouter_reseau(self):
        socketTCP = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        socketTCP.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            socketTCP.bind(("0.0.0.0", self.port_local))
            socketTCP.listen(5)
            print(f"[RELAIS] Écoute active sur le port {self.port_local}")
        except Exception as e:
            print(f"[ERREUR] Impossible de lier le port {self.port_local} : {e}")
            return

        while True:
            client, addr = socketTCP.accept()
            donnees = self._recevoir_tout(client)
            if donnees:
                threading.Thread(target=self._traiter_message, args=(donnees,)).start()
            client.close()

    def _recevoir_tout(self, socketTCP):
        contenu = b""
        socketTCP.settimeout(2)
        try:
            while True:
                partie = socketTCP.recv(4096)
                if not partie: break
                contenu += partie
        except: pass
        return contenu
    
    def _traiter_message(self, donnees_brutes):
        try:
            message_clair = self.crypto.dechiffrer(donnees_brutes)
            
            if not message_clair or "|" not in message_clair:
                return

            commande, reste = message_clair.split("|", 1)
            
            if "NEXT_IP" in commande:
                infos = self._parser_headers(commande)
                print(f"[RELAIS] Passage du paquet vers {infos['NEXT_IP']}:{infos['NEXT_PORT']}")
                self._envoyer_socket(infos['NEXT_IP'], int(infos['NEXT_PORT']), reste)
                
            elif "DEST:FINAL" in commande:
                print(f"\n🔔 [MESSAGE FINAL REÇU] : {reste}")
                print("\n(Appuyez sur Entrée pour revenir au menu)")

        except Exception as e:
            print(f"[ERREUR TRAITEMENT] Impossible de déchiffrer : {e}")
    
    # Partie client
    def _menu_interactif(self):
        while True:
            print(f"\n Routeur Hybride (Local: {self.port_local})")
            print(f"Cible Master : {self.master_ip}:{self.master_port}")
            print("1. S'inscrire au Master")
            print("2. Actualiser l'annuaire (REQ_LIST_KEYS)")
            print("3. Envoyer un message sécurisé (Oignon)")
            print("q. Quitter")
            
            choix = input("\nAction > ")
            
            if choix == "1":
                self.action_inscription()
            elif choix == "2":
                self.action_recuperer_annuaire()
            elif choix == "3":
                self.action_envoyer_oignon()
            elif choix == "q":
                print("Arrêt du routeur...")
                break

    def action_inscription(self):
        try:
            e, n = self.crypto.c_pub 
            requete = f"INSCRIPTION;{self.port_local};{e},{n}"
            
            self._envoyer_socket(self.master_ip, self.master_port, requete)
            print("[+] Demande d'inscription envoyée au Master.")
        except Exception as e:
            print(f"[-] Erreur Inscription : {e}")

    def action_recuperer_annuaire(self):
        try:
            socketTCPannuaire= socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            socketTCPannuaire.connect((self.master_ip, self.master_port))
            socketTCPannuaire.sendall(b"REQ_LIST_KEYS")
            reponse = self._recevoir_tout(socketTCPannuaire).decode('utf-8')
            socketTCPannuaire.close()

            self.annuaire = {}
            for ligne in reponse.split('\n'):
                if "ID:" in ligne:
                    d = self._parser_headers(ligne)
                    k = d['KEY'].split(',')
                    self.annuaire[d['ID']] = {
                        'ip': d['IP'], 
                        'port': int(d['PORT']),
                        'cle': (int(k[0]), int(k[1]))
                    }
            print(f"[+] Annuaire mis à jour : {len(self.annuaire)} routeurs détectés.")
        except Exception as e:
            print(f"[-] Erreur Annuaire : {e}")
    
    def action_envoyer_oignon(self):
        if not self.annuaire:
            print("❌ Annuaire vide. Faites l'option 2 d'abord.")
            return

        print("\nRouteur disponible")
        for rid, info in self.annuaire.items():
            print(f"ID {rid} | {info['ip']}:{info['port']}")
        
        id_dest = input("\nID du destinataire final : ")
        msg_final = input("Votre message : ")

        # Construction de l'oignon
        try:
            cle_dest = self.annuaire[id_dest]['cle']
            paquet = self.crypto.chiffrer(f"DEST:FINAL|{msg_final}", cle_dest)

            id_relais = input("ID du relais intermédiaire : ")
            cle_relais = self.annuaire[id_relais]['cle']
            info_dest = self.annuaire[id_dest]
            
            instruction = f"NEXT_IP:{info_dest['ip']};NEXT_PORT:{info_dest['port']}|{paquet}"
            paquet_complet = self.crypto.chiffrer(instruction, cle_relais)

            self._envoyer_socket(self.annuaire[id_relais]['ip'], self.annuaire[id_relais]['port'], paquet_complet)
            print("[*] Paquet oignon envoyé dans le réseau.")
        except Exception as e:
            print(f"[-] Erreur de construction : {e}")
    
    # Outils de réseaux et parsing
    def _envoyer_socket(self, ip, port, message):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((ip, port))
        if isinstance(message, str):
            s.sendall(message.encode('utf-8'))
        else:
            s.sendall(message)
        s.close()

    def _parser_headers(self, chaine):
        res = {}
        parties = chaine.replace('|', ';').split(';')
        for p in parties:
            if ':' in p:
                k, v = p.split(':', 1)
                res[k.strip()] = v.strip()
        return res