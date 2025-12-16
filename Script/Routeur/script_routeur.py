import sys
from Routeur import Routeur


if __name__ == "__main__":
    master_ip = ""
    while not master_ip:
        master_ip = input("Saisir l'IP du Master (Annuaire) : ").strip()
    
    # Ports par défaut :
    port_routeur = 8080
    recherche_port_client = 50001
    port_ecoute_client = 8888 
    
    if len(sys.argv) > 1:
        try:
            port_routeur = int(sys.argv[1])
        except ValueError:
            print("Erreur: Le 1er argument (Port Routeur TCP) doit être un nombre. Utilisation de 8080.")

    # Port UDP de Découverte Client (sys.argv[2])
    if len(sys.argv) > 2:
        try:
            recherche_port_client = int(sys.argv[2])
        except ValueError:
            print("Erreur: Le 2ème argument (Port Découverte UDP) doit être un nombre. Utilisation de 50001.")
            
    # Port d'Écoute Client Final (sys.argv[3])
    if len(sys.argv) > 3:
        try:
            port_ecoute_client = int(sys.argv[3])
        except ValueError:
            print("Erreur: Le 3ème argument (Port Écoute Client Final) doit être un nombre. Utilisation de 8888.")
    
    # 3. Instanciation de la classe Routeur (lance le programme)
    print("--- Démarrage de Routeur ---")
    routeur = Routeur(master_ip, port_routeur, recherche_port_client, port_ecoute_client)