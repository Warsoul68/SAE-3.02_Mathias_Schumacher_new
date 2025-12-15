import socket 
import threading
import time
import random
from chiffrement_RSA import CryptoManager
import datetime

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
            journalisation_log("CLIENT", "RECEPTION", f"Message reçu de {addr[0]}. Contenu : {message[:20]}...")
            print("Appuyer sur Entrée pour rafraîchir le menu...")
            conn.close()
    except: pass


# recherche UDP
def trouver_ip_routeur():
    journalisation_log("CLIENT", "INIT", "Lancement de la recherche de passerelle.")
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

    if not liste_ips: liste_ips = ["10.0.0.1", "192.168.1.41"]
    
    for ip_test in liste_ips:
        if ip_test.startswith("127."): continue
        socketUDP = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        socketUDP.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        socketUDP.settimeout(20)

        try:
            socketUDP.bind((ip_test, 0))
            if ip_test.startswith("10."):
                parties = ip_test.split('.')
                broadcast_cible = f"{parties[0]}.{parties[1]}.{parties[2]}.255"
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

                journalisation_log("CLIENT", "INIT", f"Passerelle trouvée : {routeur_ip} (ID {mon_routeur_id})")
                socketUDP.close()
                return routeur_ip
        except: pass
        finally:
            socketUDP.close()
    return None

def envoyer_commande(routeur_ip, commande):
    try:
        socketTCP = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        socketTCP.settimeout(20)
        socketTCP.connect((routeur_ip, Port_Routeur))
        socketTCP.sendall(commande.encode("utf-8"))
        reponse = socketTCP.recv(4096).decode("utf-8")
        socketTCP.close()
        return reponse
    except Exception as e:
        journalisation_log("CLIENT", "ERREUR", f"Échec envoi commande Master : {e}")
        return "ERROR"
    
def recuperer_annuaire_complet(routeur_ip, routeur_port):
    journalisation_log("CLIENT", "ANNUAIRE", f"Demande d'annuaire au routeur {routeur_ip}")
    try:
        socketTCP = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        socketTCP.settimeout(20)
        socketTCP.connect((routeur_ip, routeur_port))
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
                        'port': int(infos.get('PORT', Port_Routeur)),
                        'cle': (int(e_val), int(n_val))
                    }
                else:
                    print(f"Clé ignorée (format incorrect) : {cle_str}")

        except Exception as e:
            print(f"Erreur parsing ligne : {e}")
            pass

    return annuaire

def construire_oignon(message, chemin_ids, annuaire_complet, id_dest_final):
    blob = f"CMD_FINAL|{id_dest_final}|{message}"

    dernier_id = chemin_ids[-1]
    cle_derniere = annuaire_complet[dernier_id]['cle']
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
    print("Messagerie")
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
                print(f"\n[Annuaire Réseau] {len(ids)} Routeur(s) actif(s) : {list(ids.keys())}\n")
            else:
                print("\n[Annuaire] Vide ou Master injoignable.\n")
            
        elif choix == "2":
            dest = input("IP Destinataire : ")
            message = input("Message : ")

            annuaire = recuperer_annuaire_complet(routeur_ip, Port_Routeur)
            
            ids_dispo = list(annuaire.keys())
            nb_routeurs_total = len(ids_dispo)

            if nb_routeurs_total == 0:
                journalisation_log("CLIENT", "ERREUR", "Impossible d'envoyer. Annuaire vide.")
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
                journalisation_log("CLIENT", "ENVOI", f"Construction Oignon ({nb_sauts} sauts) vers {dest}")
                paquet_final = construire_oignon(message, chemin, annuaire, dest) 

                premier_id = chemin[0]

                ip_cible = annuaire[premier_id]['ip']
                port_cible = annuaire[premier_id]['port']

                journalisation_log("CLIENT", "ENVOI", f"Connexion 1er saut ID {premier_id} ({ip_cible})")

                socketTCP = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                socketTCP.settimeout(20)
                socketTCP.connect((ip_cible, port_cible)) 
                socketTCP.sendall(paquet_final.encode())
                rep = socketTCP.recv(4096).decode()
                socketTCP.close()

                journalisation_log("CLIENT", "SUCCES", f"Message envoyé. Réponse du 1er saut : {rep[:15]}...")

            except Exception as e:
                journalisation_log("CLIENT", "ERREUR", f"Crash envoi/reception du message : {e}")

        elif choix == "0":
            journalisation_log("CLIENT", "FIN", "Fermeture du programme.")
            break

if __name__ == "__main__":
    menu()