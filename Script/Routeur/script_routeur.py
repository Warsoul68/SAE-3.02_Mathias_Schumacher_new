import sys
from Routeur import Routeur

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 script_routeur.py <PORT_LOCAL>")
        sys.exit(1)

    port_local = sys.argv[1]
    
    print(f"--- Démarrage du Routeur Hybride ({port_local}) ---")
    master_ip = input("IP du Master : ")
    master_port = int(input("Port du Master : "))

    mon_routeur = Routeur(int(port_local), master_ip, master_port)
    mon_routeur.demarrer()

if __name__ == "__main__":
    main()