import sys
from Routeur import Routeur

def main():
    print("\n" + "="*50)
    print("   Lancement du nœud réseau (Mode Hybride)")
    print("="*50)

    # 1. On vérifie que le port du routeur est passé en argument
    if len(sys.argv) < 2:
        print("\n[!] ERREUR : Port local manquant.")
        print("Usage : python3 script_routeur.py <PORT_DU_ROUTEUR>")
        print("Exemple : python3 script_routeur.py 8080\n")
        sys.exit(1)

    try:
        port_local = int(sys.argv[1])
    except ValueError:
        print("\n[!] ERREUR : Le port doit être un nombre entier.")
        sys.exit(1)
    
    print(f"\n[*] Configuration de l'accès au Master pour le port {port_local}")
    
    ip_master = input("Entrez l'IP du Master (ex: 10.128.200.15) : ")
    
    while True:
        try:
            port_master = int(input("Entrez le Port du Master (ex: 8080) : "))
            break
        except ValueError:
            print("[!] Erreur : Le port doit être un nombre.")

    try:
        mon_routeur = Routeur(port_local, ip_master, port_master)
        
        print("\n" + "-"*50)
        mon_routeur.demarrer()
        
    except KeyboardInterrupt:
        print("\n[!] Arrêt manuel du script.")
        sys.exit(0)
    except Exception as e:
        print(f"\n[!] Erreur fatale : {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()