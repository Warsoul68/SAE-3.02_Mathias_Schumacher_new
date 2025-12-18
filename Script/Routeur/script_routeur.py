import sys
from Routeur import Routeur

if __name__ == "__main__":
    # Saisie de l'IP du Master
    master_ip = ""
    while not master_ip:
        master_ip = input("Saisir l'IP du Master (Annuaire) : ").strip()
    
    # Saisie du Port du Master
    master_port = None
    while master_port is None:
        saisie_p = input("Saisir le Port du Master (ex: 8080) : ").strip()
        if saisie_p.isdigit():
            master_port = int(saisie_p)
        else:
            print("Erreur : Le port doit être un nombre (ex: 8080).")
    
    port_routeur = 8080
    recherche_port_client = 50001
    port_ecoute_client = 8888 
    
    if len(sys.argv) > 1:
        try:
            port_routeur = int(sys.argv[1])
        except ValueError:
            print("Erreur: Le 1er argument (Port Routeur TCP) doit être un nombre. Utilisation de 8080.")

    if len(sys.argv) > 2:
        try:
            recherche_port_client = int(sys.argv[2])
        except ValueError:
            print("Erreur: Le 2ème argument (Port Découverte UDP) doit être un nombre. Utilisation de 50001.")
            
    if len(sys.argv) > 3:
        try:
            port_ecoute_client = int(sys.argv[3])
        except ValueError:
            print("Erreur: Le 3ème argument (Port Écoute Client Final) doit être un nombre. Utilisation de 8888.")
    
    print("\n" + "="*40)
    print("DÉMARRAGE DU NŒUD ROUTEUR")
    print(f"Connexion Master : {master_ip}:{master_port}")
    print(f"Port écoute TCP : {port_routeur}")
    print(f"Port découverte UDP : {recherche_port_client}")
    print("="*40 + "\n")
    
    routeur = Routeur(master_ip, master_port, port_routeur, recherche_port_client, port_ecoute_client)
