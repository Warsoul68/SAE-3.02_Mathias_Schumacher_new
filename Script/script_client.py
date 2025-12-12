import socket
import threading
import time
import random
from chiffrement_RSA import CryptoManager

crypto_outils = CryptoManager()

# Config
Port_Routeur = 8080
Recherche_port = 50001
Port_en_ecoute = 8888

def ecouter_message_entrants():
    try:
        socket_serveur = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        socket_serveur.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        socket_serveur.bind(("0.0.0.0", Port_en_ecoute))
        socket_serveur.listen(5)

        while True:
            conn, addr = socket_serveur.accept()
            data = conn.recv(4096)
            message = data.decode("utf-8")
            print(f"\n\n [Message reçu] De {addr[0]} : \n {message}\n")
            print("Appuyer sur Entrée pour rafraîchir le menu...")
            conn.close()
    except: pass


# recherche du routeur UDP
def trouver_ip_routeur():
    print("[Auto-Config] Recherche du routeur sur le réseau...")
    liste_ips = []

    try:
        hostname = socket.gethostname()
        res = socket.gethostbyname_ex(hostname)[2]
        for ip in res:
            if not ip.startswith("127."): liste_ips.append(ip)
    except: pass

    # Methode sonde vers une IP interne
    try:
        socket_client_UDP = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        socket_client_UDP.connect(("10.0.0.1", 80))
        ip = socket_client_UDP.getsockname()[0]
        if ip not in liste_ips: liste_ips.append(ip)
        socket_client_UDP.close()
    except: pass

    if not liste_ips:liste_ips = ["10.0.0.1", "192.168.1.41"]
    
    for ip_test in liste_ips:
        if ip_test.startswith("127."): continue
        socketUDP = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        socketUDP.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        socketUDP.settimeout(1)

        try:
            socketUDP.bind((ip_test, 0))
            if ip_test.startswith("10."):
                parts = ip_test.split('.')
                broadcast_cible = f"{parts[0]}.{parts[1]}.{parts[2]}.255"
            else:
                broadcast_cible = "<broadcast>"
            
            socketUDP.sendto(b"Ou_est_le_routeur?", (broadcast_cible, Recherche_port))

            data, addr = socketUDP.recvfrom(1024)
            message = data.decode()

            if message.startswith("Je_suis_le_routeur"):
                routeur_ip = addr[0]
                mon_routeur_id = "?"
                if "|" in message: mon_routeur_id = message.split('|')[1]

                print(f"[Succès] Passerelle trouvée : {routeur_ip} (Agent ID {mon_routeur_id})")
                socketUDP.close()
                return routeur_ip
        except: pass
        finally:
            socketUDP.close()
    return None

def envoyer_commande(routeur_ip, commande):
    try:
        socketTCP = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        socketTCP.settimeout(5)
        socketTCP.connect((routeur_ip, Port_Routeur))
        socketTCP.sendall(commande.encode("utf-8"))
        reponse = socketTCP.recv(4096).decode("utf-8")
        socketTCP.close()
        return reponse
    except Exception as e:
        print(f"[Erreur] : {e}")
        return "ERROR"
    
def recuperer_annuaire_avec_cles(routeur_ip):
    reponse = envoyer_commande(routeur_ip, "REQ_LIST_KEYS")

    annuaire = {}
    if not reponse or "ERROR" in reponse:
        return annuaire
    
    items = reponse.split('|')
    for item in items:
        try:
            if "KEY:" in item:
                parties = item.split(",KEY:")
                id_r = parties[0].replace("ID:", "").strip()
                cle_str = parties[1].strip()
                e_val, n_val = cle_str.split(',')
                annuaire[id_r] = (int(e_val), int(n_val))
        except: pass

    return annuaire

def construire_oignon(message, chemin_ids, annuaire_cles, id_dest_final):
    blob = f"CMD_FINAL|{id_dest_final}|{message}"

    dernier_id = chemin_ids[-1]
    cle_derniere = annuaire_cles[dernier_id]
    blob_chiffre = crypto_outils.chiffrer(blob, cle_derniere)

    routeur_restants = list(reversed(chemin_ids[:-1]))

    prochain_saut = dernier_id

    for id_routeur in routeur_restants:
        cle = annuaire_cles[id_routeur]
        nouvelle_instruction = f"CMD_RELAY|{prochain_saut}|{blob_chiffre}"

        blob_chiffre = crypto_outils.chiffrer(nouvelle_instruction, cle)
        prochain_saut = id_routeur
    return f"CMD_OIGNON|{blob_chiffre}"

# Menu
def menu():
    print("--- MESSAGERIE CLIENT ---")
    threading.Thread(target=ecouter_message_entrants, daemon=True).start()

    routeur_ip = None
    while not routeur_ip:
        routeur_ip = trouver_ip_routeur()
        if not routeur_ip:
            choix = input("Routeur introuvable. [R]éessayer ou entrer [I]P manuelle ? ")
            if choix.lower() == "i":
                routeur_ip = input("IP du routeur : ")
            else:
                time.sleep(2)
    
    while True:
        print("-" * 40)
        print(f"Passerelle : {routeur_ip}")
        print("1. Afficher l'Annuaire")
        print("2. Envoyer un message")
        print("0. Quitter")
        
        choix = input("Votre choix : ")
        
        if choix == "1":
            print("Récuperation de l'annuaire...")
            ids = recuperer_annuaire_avec_cles(routeur_ip)
            if ids:
                print(f"\n[Annuaire Réseau] {len(ids)} Routeur(s) actif(s) : {ids}\n")
            else:
                print("\n[Annuaire] Vide ou Master injoignable.\n")
            
        elif choix == "2":
            dest = input("IP Destinataire : ")
            message = input("Message : ")

            annuaire = recuperer_annuaire_avec_cles(routeur_ip)
            ids_dispo = list(annuaire.keys())
            nb_routeurs_total = len(ids_dispo)

            if nb_routeurs_total == 0:
                print("[Erreur] Aucun routeur disponible (ou pas de clés).")
                continue

            print(f"{nb_routeurs_total} routeurs disponibles : {ids_dispo}")

            while True:
                try:
                    saisie = input(f"Nombre de sauts souhaités (Max {nb_routeurs_total}) : ")
                    nb_sauts = int(saisie)
                    if 1 <= nb_sauts <= nb_routeurs_total:
                        break
                    else:
                        print(f"[Erreur] Vous devez choisir entre 1 et {nb_routeurs_total}.")
                except ValueError:
                    print("Veuillez entrer un chiffre.")
            
            chemin = random.sample(ids_dispo, nb_sauts)

            print(f"Chemin généré (Unique) : {chemin}")

            try:
                print("Chiffrement en couches (Oignon)...")
                paquet_final = construire_oignon(message, chemin, annuaire, dest)

                print(f"Envoie vers la passerelle...")
                reponse = envoyer_commande(routeur_ip, paquet_final)
                print(f"[Retour passerelle] : {reponse}")
            except Exception as e:
                print(f"[Erreur] lors de la création de l'oignon : {e}")

        elif choix == "0":
            print("Fermeture.")
            break

if __name__ == "__main__":
    menu()
