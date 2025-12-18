import sys
import threading
import random
# On importe le Routeur ET la fonction de log
from Routeur import Routeur, journalisation_log

def afficher_titre(port):
    print("\n" + "="*50)
    print(f"Noeud routeur hybride - port {port}")
    print("="*50)

def main():
    if len(sys.argv) < 2:
        print("\n[!] Port manquant. Usage: python3 script_routeur.py <PORT>")
        sys.exit(1)

    try:
        port_local = int(sys.argv[1])
    except ValueError:
        print("\n[!] Le port doit être un nombre entier.")
        sys.exit(1)

    nom_log = f"ROUTEUR_{port_local}"

    ip_master = input("Entrez l'IP du Master (ex: 192.168.1.34) : ")
    port_master_in = input("Entrez le Port du Master (8080 par défaut) : ")
    port_master = int(port_master_in) if port_master_in else 8080

    try:
        mon_routeur = Routeur(port_local, ip_master, port_master)
        
        journalisation_log(nom_log, "SCRIPT", "Initialisation du thread d'écoute réseau...")
        
        thread_serveur = threading.Thread(target=mon_routeur._module_ecoute_reseau, daemon=True)
        thread_serveur.start()
        
        afficher_titre(port_local)

        while True:
            print("\nMenu principal :")
            print("1. S'inscrire & Sync Annuaire (Auto)")
            print("2. Afficher l'Annuaire local")
            print("3. ENVOYER UN MESSAGE")
            print("0. Quitter")
            
            choix = input("\nAction > ").lower()

            if choix == "1":
                mon_routeur.client_inscription()
            
            elif choix == "2":
                if not mon_routeur.annuaire:
                    print("[!] Annuaire vide. Synchronisez d'abord (Option 1).")
                else:
                    print(f"\nNœuds connus dans le réseau ({len(mon_routeur.annuaire)}) :")
                    for rid, info in mon_routeur.annuaire.items():
                        print(f" - ID {rid} : {info['ip']}:{info['port']}")

            elif choix == "3":
                if not mon_routeur.annuaire:
                    print("[!] Erreur : L'annuaire est nécessaire pour choisir des relais.")
                    journalisation_log(nom_log, "ERREUR", "Tentative d'envoi sans annuaire.")
                    continue
                
                print("\nEnvoie :")
                target_ip = input("IP de la cible (Client ou Routeur) : ")
                try:
                    target_port = int(input("Port de la cible : "))
                except:
                    print("[!] Port invalide.")
                    continue
                
                msg = input("Message à envoyer : ")
                nb_sauts = int(input("Nombre de relais (sauts) : ") or 1)
                
                ids_dispos = list(mon_routeur.annuaire.keys())
                id_exit = random.choice(ids_dispos)
                relais_possibles = [i for i in ids_dispos if i != id_exit]
                chemin = random.sample(relais_possibles, min(nb_sauts-1, len(relais_possibles))) + [id_exit]
                
                try:
                    journalisation_log(nom_log, "ENVOI", f"Préparation oignon vers {target_ip}:{target_port} via {chemin}")
                    
                    paquet = mon_routeur.construire_oignon(
                        message=msg, 
                        chemin_ids=chemin, 
                        annuaire=mon_routeur.annuaire, 
                        mode="CLIENT", 
                        ip_c=target_ip, 
                        port_c=target_port
                    )
                    
                    premier_id = chemin[0]
                    target_relais = mon_routeur.annuaire[premier_id]
                    mon_routeur._envoyer_socket(target_relais['ip'], target_relais['port'], paquet)
                    
                    print(f"[OK] Message envoyé anonymement via le circuit : {chemin}")
                except Exception as e:
                    print(f"[!] Erreur lors de la préparation : {e}")
                    journalisation_log(nom_log, "ERREUR", f"Échec préparation envoi : {e}")

            elif choix == "0":
                journalisation_log(nom_log, "STOP", "Fermeture manuelle du nœud.")
                print("Fermeture du nœud...")
                break

    except KeyboardInterrupt:
        journalisation_log(nom_log, "STOP", "Interruption par l'utilisateur (Ctrl+C).")
        print("\n[!] Interruption par l'utilisateur.")
    except Exception as e:
        journalisation_log(nom_log, "FATAL", f"Erreur critique : {e}")
        print(f"\n[!] Erreur fatale : {e}")