import socket
import threading
import time
import random

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

                print(f"[Succès] Paserelle trouvée : {routeur_ip} (Agent ID {mon_routeur_id})")
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
    
def recuperer_annuaire(routeur_ip):
    reponse = envoyer_commande(routeur_ip, "REQ_LIST_IDS")
    if reponse and "ERROR" not in reponse:
        return [x.strip() for x in reponse.split(',') if x.strip()]
    return []

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
            ids = recuperer_annuaire(routeur_ip)
            if ids:
                print(f"\n[Annuaire Réseau] {len(ids)} Routeur(s) actif(s) : {ids}\n")
            else:
                print("\n[Annuaire] Vide ou Master injoignable.\n")
            
        elif choix == "2":
            dest = input("IP du destinataire : ")
            if not dest: continue

            print("Mise à jour de la liste des roteurs...")
            ids_dispo = recuperer_annuaire(routeur_ip)
            nb_routeurs_actifs = len(ids_dispo)

            if nb_routeurs_actifs == 0:
                print("Erreur : Aucun routeur disponible pour relayer le message.")
                continue
            print(f"Routeur disponible : {ids_dispo}")

            while True:
                try:
                    saisie = input(f"Combien de sauts voulez-vous ? : ")
                    nb_bonds = int(saisie)
                    if nb_bonds > 0:
                        break
                    print("Il faut au moins 1 saut.")
                except ValueError:
                    print("Veuillez entrer un chiffre")
            
            chemin = []

            if nb_bonds <= nb_routeurs_actifs:
                chemin = random.sample(ids_dispo, nb_bonds)
            
            else:
                print(f"Note Vous demandez {nb_bonds} saut sur {nb_routeurs_actifs} routeurs.")
                print(" -> Le message repassera plusieurs fois par les même noeuds.")
                for _ in range(nb_bonds):
                    chemin.append(random.choice(ids_dispo))
                
            chemin_str = ",".join(chemin)
            print(f"Chemin généré : [{chemin_str}]")

            message = input("Votre message : ")

            commande = f"CMD_MSG|{dest}|{chemin_str}|{message}"

            rep = envoyer_commande(routeur_ip, commande)
            print(f"[Retour Passerelle] {rep}")
            
        elif choix == "0":
            print("Fermeture.")
            break

if __name__ == "__main__":
    menu()
