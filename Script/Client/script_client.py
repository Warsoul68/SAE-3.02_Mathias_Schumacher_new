from Client import journalisation_log, Client


if __name__ == "__main__":
    
    routeur_ip = ""
    while not routeur_ip:
        routeur_ip = input("Saisir l'IP de la Passerelle (Routeur 1) : ").strip()

    routeur_port = None
    while not routeur_port:
        try:
            port_saisie = input("Saisir le Port de la Passerelle (ex: 8080) : ").strip()
            routeur_port = int(port_saisie)
        except ValueError:
            print("Erreur : Le port doit être un nombre valide.")
            routeur_port = None
            
    client_port_ecoute = None
    while not client_port_ecoute:
        try:
            port_saisie = input("Saisir le Port d'écoute du Client (ex: 8888) : ").strip()
            client_port_ecoute = int(port_saisie)
        except ValueError:
            print("Erreur : Le port doit être un nombre valide.")
            client_port_ecoute = None
    
    print("--- Démarrage de Client ---")
    client_app = Client(routeur_ip, routeur_port, client_port_ecoute)
    
    while True:
        print("-" * 40)
        print("MENU CLIENT - TEST CONSOLE")
        print(f"Passerelle : {client_app.Routeur_IP_Passerelle}:{client_app.Port_Routeur_Passerelle} (Port écoute : {client_app.Port_en_ecoute})")
        print("1. Afficher Annuaire & Clés")
        print("2. Envoyer un message sécurisé (Oignon)")
        print("0. Quitter")
        
        choix = input("Votre choix : ")

        if choix == "1":
            annuaire = client_app.recuperer_annuaire_complet()
            if annuaire:
                print(f"\n[Annuaire Réseau] {len(annuaire)} Routeur(s) actif(s) : {list(annuaire.keys())}")
                print("Détails des clés et IPs :")
                for id_r, infos in annuaire.items():
                    print(f" - ID {id_r} | IP: {infos['ip']} | Port: {infos['port']} | Clé (N): {infos['cle'][1]}")
                print("\n")
            else:
                print("\n[Annuaire] Vide ou Master injoignable.\n")
                
        elif choix == "2":
            dest_ip = input("IP Destinataire (Ex: 10.0.0.5) : ")
            message = input("Message : ")
            
            # Logique pour demander le nombre de sauts
            annuaire = client_app.recuperer_annuaire_complet()
            nb_max = len(annuaire)
            
            if nb_max == 0:
                print("Annuaire vide. Impossible d'envoyer.")
                continue

            nb_sauts = 0
            while not (1 <= nb_sauts <= nb_max):
                try:
                    saisie = input(f"Nombre de sauts souhaités (Max {nb_max}) : ")
                    nb_sauts = int(saisie)
                except ValueError:
                    nb_sauts = 0
            
            client_app.envoyer_message(dest_ip, message, nb_sauts)

        elif choix == "0":
            journalisation_log("CLIENT", "FIN", "Fermeture du programme.")
            break