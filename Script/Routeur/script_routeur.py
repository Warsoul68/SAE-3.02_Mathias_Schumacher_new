import sys
from Routeur import Routeur

def main():
    print("Réseaux oignons : routeur hybride")

    # 1. Récupération du port local via l'argument
    if len(sys.argv) < 2:
        print("\n[!] Erreur : Vous devez spécifier un port pour ce routeur.")
        print("Exemple : python3 script_routeur.py 8081")
        sys.exit(1)

    try:
        port_local = int(sys.argv[1])
    except ValueError:
        print("[!] Erreur : Le port doit être un nombre entier.")
        sys.exit(1)

    # Saisie des informations du Master
    print("\n--- Configuration de la connexion Master ---")
    master_ip = input("Entrez l'IP du serveur Master (ex: 10.128.200.15) : ")
    
    while True:
        try:
            master_port = int(input("Entrez le Port du serveur Master (ex: 8080) : "))
            break
        except ValueError:
            print("Veuillez entrer un numéro de port valide.")

    # 3. Initialisation et démarrage
    print(f"\n[*] Tentative de démarrage du routeur sur le port {port_local}...")
    mon_routeur = Routeur(port_local, master_ip, master_port)
    
    try:
        mon_routeur.demarrer()
    except KeyboardInterrupt:
        print("\n[!] Arrêt manuel du routeur.")
        sys.exit(0)

if __name__ == "__main__":
    main()