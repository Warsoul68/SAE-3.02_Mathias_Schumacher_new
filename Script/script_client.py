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
                port_detectee = 8080

                if "|" in message:
                    parties = message.split('|')
                    mon_routeur_id = parties[1]
                    if len(parties) > 2:
                        port_detectee = int(parties[2])
                
                global Port_Routeur
                Port_Routeur = port_detectee

                print(f"[Succès] Passerelle trouvée : {routeur_ip}:{Port_Routeur} (Agent ID {mon_routeur_id})")
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
    
def recuperer_annuaire_complet(routeur_ip, routeur_port):
    try:
        socketTCP = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        socketTCP.settimeout(5)
        socketTCP.connect((routeur_ip, routeur_port))
        socketTCP.sendall(b"REQ_LIST_KEYS")
        reponse = socketTCP.recv(8192).decode("utf-8")
        socketTCP.close()
    except:
        return {}

    annuaire = {}
    if not reponse or "ERROR" in reponse: return annuaire

    lignes_routeurs = reponse.split('|')

    for ligne in lignes_routeurs:
        if not ligne: continue
        try:
            champs = ligne.split(';')
            infos = {}
            for champ in champs:
                if ':' in champs:
                    k, v = champ.split(':', 1)
                    infos[k] = v
            if 'ID' in infos and 'KEY' in infos:
                id_r = infos['ID']
                cle_str = infos['KEY']

                e_val, n_val = cle_str.split(',')

                annuaire[id_r] = {
                    'ip': infos.get('IP', ''),
                    'port': int(infos.get('PORT', Port_Routeur)),
                    'cle': (int(e_val), int(n_val))
                }
        except Exception as e:
            print(f"[Annuaire] Ligne ignorée car mal formée : {e}")
            pass

    return annuaire

def construire_oignon(message, chemin_ids, annuaire_complet, id_dest_final):
    blob = f"CMD_FINAL|{id_dest_final}|{message}"

    dernier_id = chemin_ids[-1]
    cle_derniere = annuaire_complet[dernier_id]
    blob_chiffre = crypto_outils.chiffrer(blob, cle_derniere)

    routeur_restants = list(reversed(chemin_ids[:-1]))

    prochain_saut = dernier_id

    for id_routeur in routeur_restants:
        cle = annuaire_complet[id_routeur]['cle']
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
            ids = recuperer_annuaire_complet(routeur_ip, Port_Routeur)
            if ids:
                print(f"\n[Annuaire Réseau] {len(ids)} Routeur(s) actif(s) : {ids}\n")
            else:
                print("\n[Annuaire] Vide ou Master injoignable.\n")
            
        elif choix == "2":
            dest = input("IP Destinataire : ")
            message = input("Message : ")

            annuaire = recuperer_annuaire_complet(routeur_ip, Port_Routeur)
            
            ids_dispo = list(annuaire.keys())
            nb_routeurs_total = len(ids_dispo)

            if nb_routeurs_total == 0:
                print("[Erreur] Aucun routeur disponible (ou pas de clés).")
                continue

            print(f"Routeurs : {ids_dispo}")
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

            print(f"Chemin : {chemin}")

            try:
                print("Construction de l'oignon...")
                paquet_final = construire_oignon(message, chemin, annuaire, dest) 

                premier_id = chemin[0]

                ip_cible = annuaire[premier_id]['ip']
                port_cible = annuaire[premier_id]['port']

                print(f"Connexion directe au 1er saut : ID {premier_id} ({ip_cible}:{port_cible()})")

                socketTCP = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                socketTCP.settimeout(5)
                socketTCP.connect((ip_cible, port_cible))
                socketTCP.sendall(paquet_final.encode())
                rep = socketTCP.recv(4096).decode()
                socketTCP.close()

                print(f"[Retour] : {rep}")

            except Exception as e:
                print(f"[Erreur] {e}")

        elif choix == "0":
            print("Fermeture.")
            break

if __name__ == "__main__":
    menu()
