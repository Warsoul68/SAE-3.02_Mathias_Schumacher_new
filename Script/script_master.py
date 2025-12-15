import socket
import threading
import mysql.connector
import datetime

def journalisation_log(qui, type_message, message):
    maintenant = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ligne_log = f"[{maintenant}] [{qui}] [{type_message}] {message}"

    print(ligne_log)

    nom_fichier = f"journal_{qui.lower()}.log"

    try:
        with open(nom_fichier, "a", encoding="utf-8") as f:
            f.write(ligne_log + "\n")
    except Exception as e:
        print(f"Erreur d'écriture log : {e}")

# Configuration de la BDD
db_config = {
    "host": "localhost",
    "user": "root",       
    "password": "toto",       
    "database": "Routagedb" 
}

Port_TCP = 6000
Port_UDP = 50000

def get_db_connection():
    try:
        return mysql.connector.connect(**db_config)
    except mysql.connector.Error as err:
        journalisation_log("MASTER", "ERREUR BDD", f"Échec de connexion : {err}")

def vider_bdd():
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute("TRUNCATE TABLE TableRoutage")
            conn.commit()
            journalisation_log("MASTER", "NETTOYAGE", "Base de données nettoyée (vider).")
            conn.close()
        except Exception as e:
            journalisation_log("MASTER", "ERREUR BDD", f"Échec du vidage : {e}")

def enregistrer_routeur(ip, port, cle):
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            query = "INSERT INTO TableRoutage (ip, port, cle) VALUES (%s, %s, %s)"
            cursor.execute(query, (ip, port, cle))
            conn.commit()
            nouvelle_id = cursor.lastrowid
            conn.close()
            return nouvelle_id
        except Exception as e:
            journalisation_log("MASTER", "ERREUR BDD", f"Échec de l'enregistrement : {e}")
            return None
    return None
    
def get_ip_par_id(id_routeur):
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT ip FROM TableRoutage WHERE id = %s", (id_routeur,))
            res = cursor.fetchone()
            conn.close()
            if res:
                return res[0]
        except: pass
    return "ERROR"
    
def compter_routeurs():
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM TableRoutage")
            res = cursor.fetchone()[0]
            conn.close()
            return str(res)
        except: pass
    return "0"

def handle_client(conn, addr):
    journalisation_log("MASTER", "CONNEXION", f"Nouvelle connexion TCP de {addr[0]}")
    try:
        while True:
            data = conn.recv(8192)
            if not data: break
            message = data.decode().strip()
            
            # Enregistrement d'un routeur
            if "|" in message and "REQ" not in message:
                try:
                    parties = message.split('|')
                    ip_r = parties[0]
                    port_r = parties[1]
                    cle_r = parties[2]
                    
                    nouvelle_id = enregistrer_routeur(ip_r, port_r, cle_r)
                    if nouvelle_id:
                        journalisation_log("MASTER", "INSCRIPTION", f"Routeur {ip_r}:{port_r} enregistré (ID {nouvelle_id}).")
                        conn.sendall(f"ACK|{nouvelle_id}".encode())
                    else:
                        conn.sendall(b"NACK")
                except:
                    conn.sendall(b"Erreur de format")

            elif message == "REQ_LIST_IDS":
                conn_bdd = get_db_connection()
                if conn_bdd:
                    cursor = conn_bdd.cursor()
                    cursor.execute("SELECT id FROM TableRoutage")
                    res = cursor.fetchall()
                    conn_bdd.close()
                    reponse = "|".join([f"ID:{r[0]}" for r in res])
                    conn.sendall(reponse.encode())

            elif message == "REQ_LIST_KEYS":
                journalisation_log("MASTER", "ANNUAIRE", f"Envoi de l'annuaire cryptographique à {addr[0]}")
                conn_bdd = get_db_connection()
                if conn_bdd:
                    cursor = conn_bdd.cursor()
                    cursor.execute("SELECT id, ip, port, cle FROM TableRoutage")
                    res = cursor.fetchall()
                    conn_bdd.close()
 
                    items = []
                    for r in res:
                        rid = r[0]
                        rip = r[1]
                        rport = r[2]
                        rcle = r[3]
                        items.append(f"ID:{rid};IP:{rip};PORT:{rport};KEY:{rcle}")
                    
                    reponse = "|".join(items)
                    conn.sendall(reponse.encode())

            elif message.startswith("REQ_RESOLVE_ID"):
                id_cible = message.split('|')[1]
                
                conn_bdd = get_db_connection()
                if conn_bdd:
                    cursor = conn_bdd.cursor()
                    cursor.execute("SELECT ip, port FROM TableRoutage WHERE id = %s", (id_cible,))
                    res = cursor.fetchone()
                    conn_bdd.close()
                    
                    if res:
                        conn.sendall(f"{res[0]}|{res[1]}".encode())
                    else:
                        conn.sendall(b"ERROR")
                else:
                    conn.sendall(b"ERROR")

            elif message == "REQ_NB_ROUTEURS":
                nb = compter_routeurs()
                conn.sendall(nb.encode())

    except Exception as e:
        print(f"Erreur Client {addr}: {e}")
    finally:
        conn.close()
        
# Service de decouverte UDP
def lancement_service_decouverte():
    socketUDP = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    socketUDP.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        socketUDP.bind(("0.0.0.0", Port_UDP))
        journalisation_log("MASTER", "UDP", f"Service de découverte lancé sur le port {Port_UDP}")
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
def demarrer_master():
    print("Master Lancé")
    
    vider_bdd()
    
    threading.Thread(target=lancement_service_decouverte, daemon=True).start()
    
    socketTCPmaster = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    socketTCPmaster.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        socketTCPmaster.bind(('0.0.0.0', Port_TCP))
        socketTCPmaster.listen(50)
        journalisation_log("MASTER", "TCP", f"Prêt à enregistrer les routeurs sur le port {Port_TCP}...")
        
        while True:
            conn, addr = socketTCPmaster.accept()
            threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()
    
    except Exception as e:
        journalisation_log("MASTER", "CRASH", f"Erreur critique du serveur : {e}")
    finally:
        socketTCPmaster.close()
        
if __name__ == "__main__":
    demarrer_master()
