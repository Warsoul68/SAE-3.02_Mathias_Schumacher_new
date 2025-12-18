import socket
import threading
import mysql.connector
import datetime
import sys


# Méthode global
def journalisation_log(qui, type_message, message, gui_callback=None):
    maintenant = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ligne_log = f"[{maintenant}] [{qui}] [{type_message}] {message}"
    print(ligne_log)
    nom_fichier = f"journal_{qui.lower()}.log"
    try:
        with open(nom_fichier, "a", encoding="utf-8") as f:
            f.write(ligne_log + "\n")
    except Exception as e:
        print(f"Erreur d'écriture log : {e}")

# Classe Master
class Master:
    def __init__(self, db_host="localhost", db_user="root", db_password="toto", db_database="Routagedb", port_tcp=6000, port_udp=50000):
        
        # Attributs de configuration
        self.db_config = {
            "host": db_host,
            "user": db_user, 
            "password": db_password,
            "database": db_database
        }
        self.Port_TCP = port_tcp
        self.Port_UDP = port_udp
        
        journalisation_log("MASTER", "INIT", "Master Annuaire en cours de lancement.")
        self._vider_bdd()
        self._demarrer_services()
    
# Méthode pour la gestion de la base de données 
    def _get_db_connection(self):
        try:
            return mysql.connector.connect(**self.db_config)
        except mysql.connector.Error as err:
            journalisation_log("MASTER", "ERREUR BDD", f"Échec de connexion : {err}")
            return None
    
    def get_tous_les_routeurs(self):
        # On récupére la liste de tout les routeurs
        conn = self._get_db_connection()
        if conn:
            try:
                cursor = conn.cursor(dictionary=True)
                cursor.execute("SELECT * FROM TableRoutage")
                resultats = cursor.fetchall()
                return resultats
            except Exception as e:
                print(f"Erreur lors de la lecture BDD : {e}")
                return []
            finally:
                conn.close()
        return []
    
    def _vider_bdd(self):
        conn = self._get_db_connection()
        if conn:
            try:
                cursor = conn.cursor()
                cursor.execute("TRUNCATE TABLE TableRoutage")
                conn.commit()
                journalisation_log("MASTER", "NETTOYAGE", "Base de données nettoyée.")
                conn.close()
            except Exception as e:
                journalisation_log("MASTER", "ERREUR BDD", f"Échec du vidage : {e}")
    
    def enregistrer_ou_mettre_a_jour_routeur(self, ip, port, cle):
        conn = self._get_db_connection() 
        if not conn: return None
        
        cursor = conn.cursor()
        check_query = "SELECT id FROM TableRoutage WHERE ip = %s AND port = %s"
        cursor.execute(check_query, (ip, port))
        resultat = cursor.fetchone()
        nouvelle_id = None
        
        if resultat:
            routeur_id = resultat[0]
            update_query = "UPDATE TableRoutage SET cle = %s WHERE id = %s"
            try:
                cursor.execute(update_query, (cle, routeur_id))
                conn.commit()
                journalisation_log("MASTER", "MISE A JOUR", f"Routeur {ip}:{port} (ID {routeur_id}) mis à jour.")
                nouvelle_id = routeur_id
            except Exception as e:
                journalisation_log("MASTER", "ERREUR BDD", f"Échec UPDATE {ip}: {e}")
                
        else:
            insert_query = "INSERT INTO TableRoutage (ip, port, cle) VALUES (%s, %s, %s)"
            try:
                cursor.execute(insert_query, (ip, port, cle))
                conn.commit()
                nouvelle_id = cursor.lastrowid
                journalisation_log("MASTER", "INSCRIPTION", f"Nouveau routeur {ip}:{port} enregistré (ID {nouvelle_id}).")
            except Exception as e:
                journalisation_log("MASTER", "ERREUR BDD", f"Échec INSERT {ip}: {e}")

        conn.close()
        return nouvelle_id
    
    def get_ip_et_port_par_id(self, id_routeur):
        conn = self._get_db_connection()
        if conn:
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT ip, port FROM TableRoutage WHERE id = %s", (id_routeur,))
                res = cursor.fetchone()
                conn.close()
                if res:
                    return res[0], res[1]
            except: pass
        return None, None
    
    def compter_routeurs(self):
        conn = self._get_db_connection()
        if conn:
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM TableRoutage")
                res = cursor.fetchone()[0]
                conn.close()
                return str(res)
            except: pass
        return "0"

# Méthode Services (TCP et UDP)

    def _handle_client(self, conn, addr):
        journalisation_log("MASTER", "CONNEXION", f"Nouvelle connexion TCP de {addr[0]}")
        try:
            while True:
                data = conn.recv(8192)
                if not data: break
                message = data.decode().strip()
                
                if "|" in message and "REQ" not in message:
                    try:
                        parties = message.split('|')
                        ip_r = parties[0]
                        port_r = int(parties[1])
                        cle_r = parties[2]
                        nouvelle_id = self.enregistrer_ou_mettre_a_jour_routeur(ip_r, port_r, cle_r)
                        
                        if nouvelle_id:
                            journalisation_log("MASTER", "INSCRIPTION", f"Routeur {ip_r}:{port_r} enregistré (ID {nouvelle_id}).")
                            conn.sendall(f"ACK|{nouvelle_id}".encode())
                        else:
                            conn.sendall(b"NACK")
                    except Exception as e:
                        journalisation_log("MASTER", "ERREUR", f"Erreur de format/enregistrement pour {addr[0]}: {e}")
                        conn.sendall(b"Erreur de format")

                elif message == "REQ_LIST_IDS":
                    conn_bdd = self._get_db_connection()
                    if conn_bdd:
                        cursor = conn_bdd.cursor()
                        cursor.execute("SELECT id FROM TableRoutage")
                        res = cursor.fetchall()
                        conn_bdd.close()
                        reponse = "|".join([f"ID:{r[0]}" for r in res])
                        conn.sendall(reponse.encode())

                elif message == "REQ_LIST_KEYS":
                    journalisation_log("MASTER", "ANNUAIRE", f"Envoi de l'annuaire cryptographique à {addr[0]}")
                    conn_bdd = self._get_db_connection()
                    if conn_bdd:
                        cursor = conn_bdd.cursor()
                        cursor.execute("SELECT id, ip, port, cle FROM TableRoutage")
                        res = cursor.fetchall()
                        conn_bdd.close()
    
                        items = []
                        for r in res:
                            rid, rip, rport, rcle = r[0], r[1], r[2], r[3]
                            items.append(f"ID:{rid};IP:{rip};PORT:{rport};KEY:{rcle}")
                        
                        reponse = "|".join(items)
                        conn.sendall(reponse.encode())

                elif message.startswith("REQ_RESOLVE_ID"):
                    id_cible = message.split('|')[1]
                    
                    conn_bdd = self._get_db_connection()
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
                    # Remplacement de l'appel global
                    nb = self.compter_routeurs()
                    conn.sendall(nb.encode())
                
                else:
                    conn.sendall(b"Commande inconnue")

        except Exception as e:
            journalisation_log("MASTER", "ERREUR", f"Erreur Client {addr}: {e}")
        finally:
            conn.close()

    def _lancement_service_decouverte(self):
        socketUDP = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        socketUDP.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            socketUDP.bind(("0.0.0.0", self.Port_UDP))
            journalisation_log("MASTER", "UDP", f"Service de découverte lancé sur le port {self.Port_UDP}")
            while True:
                # ... (logique de réponse UDP) ...
                try:
                    data, addr = socketUDP.recvfrom(1024)
                    if data.decode().strip() == "Ou_est_le_master?":
                        socketUDP.sendto(b"Je_suis_le_master", addr)
                except: pass
        except Exception as e:
            journalisation_log("MASTER", "ERREUR", f"[UDP] Erreur : {e}")
        finally:
            socketUDP.close()
    
    def _demarrer_services(self):
        journalisation_log("MASTER", "INIT", "Démarrage des services TCP et UDP.")
        
        threading.Thread(target=self._lancement_service_decouverte, daemon=True).start()
        
        socketTCPmaster = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        socketTCPmaster.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            socketTCPmaster.bind(('0.0.0.0', self.Port_TCP))
            socketTCPmaster.listen(50)
            journalisation_log("MASTER", "TCP", f"Prêt à enregistrer les routeurs sur le port {self.Port_TCP}...")
            
            while True:
                conn, addr = socketTCPmaster.accept()
                threading.Thread(target=self._handle_client, args=(conn, addr), daemon=True).start()
        
        except Exception as e:
            journalisation_log("MASTER", "CRASH", f"Erreur critique du serveur : {e}")
        finally:
            socketTCPmaster.close()