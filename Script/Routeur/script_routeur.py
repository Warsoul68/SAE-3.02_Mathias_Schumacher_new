import sys
import threading
import time

# import de la classe Routeur 
from Routeur import Routeur, journalisation_log

def afficher_titre(port):
    print(f"Noeud Routeur hybride - port {port}")

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
        thread_serveur = threading.Thread(target=mon_routeur.demarrer, daemon=True) # Utilise demarrer() qui lance l'écoute
        thread_serveur.start()
        
        afficher_titre(port_local)
        time.sleep(0.5)

        while True:
            print("\nMenu principal")
            print("1. S'inscrire & Sync Annuaire (Auto)")
            print("2. Afficher l'Annuaire local")
            print("3. Envoyer un message (Client)")
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
                print("\nPréparation de l'envoie")
                mon_routeur.client_recuperer_annuaire()
                
                if not mon_routeur.annuaire:
                    print("[!] Erreur : Annuaire vide. Impossible de router.")
                    continue
                
                try:
                    target_port = int(input("Port de la cible : "))
                    
                    if target_port == port_local:
                        print(f"\nERREUR : Le port {target_port} est le vôtre !")
                        print("Impossible de s'envoyer un message à soi-même.")
                        continue
                    
                    target_ip = input("IP de la cible : ")
                    msg = input("Message à envoyer : ")
                    nb_sauts = int(input("Nombre de relais (sauts) : ") or 1)
                    
                    mon_routeur.envoyer_message_personnalise(target_ip, target_port, msg, nb_sauts)
                    
                except ValueError:
                    print("[!] Saisie invalide (Ports et sauts doivent être des chiffres).")
                except Exception as e:
                    print(f"[!] Erreur inattendue : {e}")

            elif choix == "0":
                journalisation_log(nom_log, "STOP", "Fermeture manuelle du nœud.")
                print("Fermeture du nœud...")
                break

    except KeyboardInterrupt:
        journalisation_log(nom_log, "STOP", "Interruption par l'utilisateur (Ctrl+C).")
        print("\n[!] Arrêt demandé.")
    except Exception as e:
        journalisation_log(nom_log, "FATAL", f"Erreur critique : {e}")
        print(f"\n[!] Erreur fatale : {e}")

if __name__ == "__main__":
    main()