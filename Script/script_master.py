import socket
import threading
import mysql.connector

# Configuration de la BDD
db_config = {
    "host": "localhost",
    "user": "root",       
    "password": "toto",       
    "database": "Routagedb" 
}

TCP_PORT = 6000
UDP_PORT = 50000
        
def sauvegarde_BDD(ip, port, cle):
    conn = None
    nouvel_id = "ERROR"
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        
        query = """
        INSERT INTO TableRoutage (ip, port, cle) 
        VALUES (%s, %s, %s) 
        ON DUPLICATE KEY UPDATE port=%s, cle=%s
        """
        
        cursor.execute(query, (ip, port, cle, port, cle))
        conn.commit()
        
        # recuperation de l'id attribué
        cursor.execute("SELECT id FROM TableRoutage WHERE ip=%s", (ip,))
        res = cursor.fetchone()
        if res:
            nouvel_id = str(res[0])
        
        print(f"[BDD] Routeur {ip} traité -> ID attribué : {nouvel_id}")
        
    except mysql.connector.Error as err:
        print(f"[BDD] Erreur SQL : {err}")
    finally:
        if conn and conn.is_connected():
            conn.close()
    
    return nouvel_id
    
def compter_routeur_bdd():
    compteur = 0
    conn = None
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM TableRoutage")
        res = cursor.fetchone()
        if res: compteur = res[0]
    except: pass
    finally:
        if conn and conn.is_connected(): conn.close()
    return compteur

def get_routeur_aleatoire_bdd():
    resultat = "NONE"
    conn = None
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM TableRoutage ORDER BY RAND() LIMIT 1")
        res = cursor.fetchone()
        if res:
            resultat = str(res[0])
    except: pass
    finally:
        if conn and conn.is_connected(): conn.close()
    return resultat

def get_ip_from_id(id_routeur):
    ip_trouvee = "ERROR"
    conn = None
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        cursor.execute("SELECT ip FROM TableRoutage WHERE id=%s", (id_routeur,))
        res = cursor.fetchone()
        if res:
            ip_trouvee = res[0]
    except: pass
    finally:
        if conn and conn.is_connected(): conn.close()
    return ip_trouvee

def get_tout_les_routeur_ids_liste():
    liste = []
    conn = None
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM TableRoutage")
        for row in cursor.fetchall():
            liste.append(str(row[0]))
    except: pass
    finally:
        if conn and conn.is_connected(): conn.close()
    return ",".join(liste)
    
# Service de decouverte UDP
def lancement_service_decouverte():
    socketUDP = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    socketUDP.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        socketUDP.bind(("0.0.0.0", UDP_PORT))
        print(f"[UDP] Service de découverte sur le port {UDP_PORT}")
        while True:
            try:
                data, addr = socketUDP.recvfrom(1024)
                if data.decode().strip() == "Ou_est_le_master?":
                    socketUDP.sendto(b"Je_suis_le_master", addr)
            except: pass
    except Exception as e:
        print(f"[UDP] Erreur : {e}")
    finally:
        socketUDP.close()

# service TCP
def handle_routeur(conn, addr):
    print(f"[+] Connexion TCP de {addr}")
    try:
        while True:
            data = conn.recv(1024)
            if not data: break
            
            raw_msg = data.decode('utf-8').strip()
            if "|" in raw_msg and "REQ" not in raw_msg and "CMD" not in raw_msg:
                try:
                    elements = raw_msg.split('|')
                    if len(elements) == 3:
                        r_ip = elements[0]
                        r_port = int(elements[1])
                        r_cle = elements[2] 
                        mon_id = sauvegarde_BDD(r_ip, r_port, r_cle)
                        conn.sendall(f"ACK|{mon_id}".encode())
                    else: conn.sendall(b"ERREUR: Format")
                except: conn.sendall(b"ERREUR: Invalide")
                
            elif raw_msg.startswith("REQ_RESOLVE_ID|"):
                target_id = raw_msg.split('|')[1]
                target_ip = get_ip_from_id(target_id)
                conn.sendall(target_ip.encode())
            
            elif raw_msg == "REQ_LIST_IDS":
                ids_str = get_tout_les_routeur_ids_liste()
                conn.sendall(ids_str.encode())
                
            elif raw_msg == "REQ_NB_ROUTEURS":
                nb = compter_routeurs_bdd()
                conn.sendall(str(nb).encode())

            elif raw_msg == "REQ_RANDOM_ROUTER":
                rand_id = get_routeur_aleatoire_bdd()
                conn.sendall(rand_id.encode())
            
            else:
                conn.sendall(b"ERREUR: Commande inconnue")

    except Exception as e:
        print(f"[{addr}] Erreur Socket : {e}")
    finally:
        conn.close()
        
if __name__ == "__main__":
    print("Lancement Master")
    threading.Thread(target=lancement_service_decouverte, daemon=True).start()
    
    socket_master = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    socket_master.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        socket_master.bind(("0.0.0.0", TCP_PORT))
        socket_master.listen(50)
        print(f"[TCP] Master en écoute sur le port {TCP_PORT}...")
        
        while True:
            conn, addr = socket_master.accept()
            threading.Thread(target=handle_routeur, args=(conn, addr), daemon=True).start()
    except KeyboardInterrupt:
        print("\n[!] Arrêt du serveur demandée...")
    finally:
        socket_master.close()
