import sys
from Routeur import Routeur

def main():
    print("\n" + "="*50)
    print("Lancement du nœud réseau (Mode Hybride)")
    print("="*50)

    # 1. Vérification du port
    if len(sys.argv) < 2:
        print("\n[!] ERREUR : Port local manquant.")
        print("Usage : python3 script_routeur.py <PORT_DU_ROUTEUR>")
        print("Exemple : python3 script_routeur.py 8081\n")
        sys.exit(1)

    try:
        port_local = int(sys.argv[1])
    except ValueError:
        print("\n[!] ERREUR : Le port doit être un nombre entier.")
        sys.exit(1)
    
    print(f"\n[*] Configuration de l'accès au Master pour le port {port_local}")
    
    ip_master = input("Entrez l'IP du Master (ex: 192.168.1.34) : ")
    
    while True:
        try:
            port_master_input = input("Entrez le Port du Master (ex: 8080) : ")
            if not port_master_input:
                port_master = 8080
            else:
                port_master = int(port_master_input)
            break
        except ValueError:
            print("[!] Erreur : Le port doit être un nombre.")

    try:
        mon_routeur = Routeur(port_local, ip_master, port_master)
        
        print("\n" + "-"*50)
        print(f"Nœud démarré. En attente d'instructions...")
        mon_routeur.demarrer()
        
    except KeyboardInterrupt:
        print("\n[!] Arrêt manuel du script.")
        sys.exit(0)
    except Exception as e:
        print(f"\n[!] Erreur fatale : {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()