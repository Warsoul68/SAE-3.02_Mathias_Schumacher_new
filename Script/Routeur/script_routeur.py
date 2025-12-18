import sys
import threading
import random
from Routeur import Routeur

def afficher_titre(port):
    print("\n" + "="*50)
    print(f" Noeud routeur Hybride {port}")
    print("="*50)

def main():
    if len(sys.argv) < 2:
        print("\n[!] Port manquant. Usage: python3 script_routeur.py <PORT>")
        sys.exit(1)

    port_local = int(sys.argv[1])
    ip_master = input("Entrez l'IP du Master (ex: 192.168.1.34) : ")
    port_master = int(input("Entrez le Port du Master (ex: 8080) : ") or 8080)

    try:
        mon_routeur = Routeur(port_local, ip_master, port_master)
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
                    print("[!] Annuaire vide. Synchronisez d'abord.")
                else:
                    print(f"\nNœuds connus ({len(mon_routeur.annuaire)}) :")
                    for rid, info in mon_routeur.annuaire.items():
                        print(f" - ID {rid} : {info['ip']}:{info['port']}")

            elif choix == "3":
                if not mon_routeur.annuaire:
                    print("[!] Erreur : Vous devez avoir l'annuaire pour envoyer.")
                    continue
                
                print("\nEnvoi d'un message :")
                print("(a) Vers un autre Routeur (via ID)")
                print("(b) Vers une Interface Client (via IP/Port)")
                type_dest = input("Type de cible > ").lower()
                
                msg = input("Votre message : ")
                nb_sauts = int(input("Nombre de routeurs relais : ") or 1)
                
                ids_dispos = list(mon_routeur.annuaire.keys())
                
                if type_dest == "a":
                    id_cible = input("ID du routeur cible : ")
                    if id_cible not in ids_dispos:
                        print("[!] ID inconnu.")
                        continue
                    relais = [i for i in ids_dispos if i != id_cible]
                    chemin = random.sample(relais, min(nb_sauts-1, len(relais))) + [id_cible]
                    paquet = mon_routeur.construire_oignon(msg, chemin, mon_routeur.annuaire, mode="ROUTEUR")
                
                elif type_dest == "b":
                    ip_c = input("IP du Client cible : ")
                    port_c = int(input("Port du Client cible : "))
                    id_exit = random.choice(ids_dispos)
                    relais = [i for i in ids_dispos if i != id_exit]
                    chemin = random.sample(relais, min(nb_sauts-1, len(relais))) + [id_exit]
                    paquet = mon_routeur.construire_oignon(msg, chemin, mon_routeur.annuaire, mode="CLIENT", ip_c=ip_c, port_c=port_c)
                
                else:
                    print("[!] Choix invalide.")
                    continue
                try:
                    premier_id = chemin[0]
                    target = mon_routeur.annuaire[premier_id]
                    mon_routeur._envoyer_socket(target['ip'], target['port'], paquet)
                    print(f"[OK] Message envoyé via le circuit : {chemin}")
                except Exception as e:
                    print(f"[!] Erreur d'envoi : {e}")

            elif choix == "q":
                break

    except KeyboardInterrupt:
        print("\nArrêt.")
    except Exception as e:
        print(f"\nErreur : {e}")

if __name__ == "__main__":
    main()