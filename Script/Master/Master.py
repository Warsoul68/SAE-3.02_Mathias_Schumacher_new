import socket
import threading
import mysql.connector
import datetime
import time

# Gestion du lien avec l'interface graphique
CALLBACK_LOG_GUI = None

def definir_callback_gui(fonction):
    global CALLBACK_LOG_GUI
    CALLBACK_LOG_GUI = fonction

def journalisation_log(qui, type_message, message):
    maintenant = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ligne_log = f"[{maintenant}] [{qui}] [{type_message}] {message}"
    
    print(ligne_log)

    if CALLBACK_LOG_GUI:
        try:
            CALLBACK_LOG_GUI(ligne_log)
        except: pass

    nom_fichier = f"journal_{qui.lower()}.log"
    try:
        with open(nom_fichier, "a", encoding="utf-8") as f:
            f.write(ligne_log + "\n")
    except Exception as e:
        print(f"Erreur d'écriture log : {e}")

# Classe Master
class Master:
    def __init__(self, port_tcp, db_host="localhost", db_user="root", db_password="toto", db_database="Routagedb", port_udp=50000):
        
        # Configuration BDD
        self.db_config = {
            "host": db_host,
            "user": db_user, 
            "password": db_password,
            "database": db_database
        }
        self.Port_TCP = port_tcp
        self.Port_UDP = port_udp
        
        journalisation_log("MASTER", "INIT", f"Configuration chargée. Port TCP: {self.Port_TCP}")
        self._vider_bdd()

    def demarrer_ecoute(self):
        self._demarrer_services()

    # Gestion BDD
    def _get_db_connection(self):
        try:
            return mysql.connector.connect(**self.db_config)
        except mysql.connector.Error as err:
            journalisation_log("MASTER", "ERREUR BDD", f"Échec de connexion : {err}")
            return None
    
    def get_tous_les_routeurs(self):
        conn = self._get_db_connection()
        if conn:
            try:
                cursor = conn.cursor(dictionary=True)
                cursor.execute("SELECT * FROM TableRoutage")
                resultats = cursor.fetchall()
                return resultats
            except Exception as e:
                journalisation_log("MASTER", "ERREUR BDD", f"Lecture échouée : {e}")
                return []
            finally:
                if conn.is_connected(): conn.close()
        return []
    
    def _vider_bdd(self):
        conn = self._get_db_connection()
        if conn:
            try:
                cursor = conn.cursor()
                cursor.execute("TRUNCATE TABLE TableRoutage")
                conn.commit()
                journalisation_log("MASTER", "NETTOYAGE", "Base de données vidée au démarrage.")
            except Exception as e:
                journalisation_log("MASTER", "ERREUR BDD", f"Échec du vidage : {e}")
            finally:
                if conn.is_connected(): conn.close()
    
    def enregistrer_ou_mettre_a_jour_routeur(self, ip, port, cle):
        conn = self._get_db_connection() 
        if not conn: return None
        try:
            cursor = conn.cursor()
            check_query = "SELECT id FROM TableRoutage WHERE ip = %s AND port = %s"
            cursor.execute(check_query, (ip, port))
            resultat = cursor.fetchone()
            nouvelle_id = None
            
            if resultat:
                routeur_id = resultat[0]
                update_query = "UPDATE TableRoutage SET cle = %s WHERE id = %s"
                cursor.execute(update_query, (cle, routeur_id))
                conn.commit()
                journalisation_log("MASTER", "MISE A JOUR", f"Routeur {ip}:{port} (ID {routeur_id}) mis à jour.")
                nouvelle_id = routeur_id
            else:
                insert_query = "INSERT INTO TableRoutage (ip, port, cle) VALUES (%s, %s, %s)"
                cursor.execute(insert_query, (ip, port, cle))
                conn.commit()
                nouvelle_id = cursor.lastrowid
                journalisation_log("MASTER", "INSCRIPTION", f"Nouveau routeur {ip}:{port} enregistré (ID {nouvelle_id}).")
            return nouvelle_id
        except Exception as e:
            journalisation_log("MASTER", "ERREUR BDD", f"Échec Enregistrement {ip}: {e}")
            return None
        finally:
            if conn.is_connected(): conn.close()
    
    def compter_routeurs(self):
        conn = self._get_db_connection()
        if conn:
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM TableRoutage")
                res = cursor.fetchone()[0]
                return str(res)
            except: pass
            finally:
                conn.close()
        return "0"

    def _recevoir_tout(self, sock):
        contenu = b""
        sock.settimeout(2.0)
        try:
            while True:
                partie = sock.recv(8192)
                if not partie: break
                contenu += partie
                if len(partie) < 8192:
                    break
        except: pass
        return contenu

    def _handle_client(self, conn, addr):
        journalisation_log("MASTER", "CONNEXION", f"Nouvelle connexion de {addr[0]}")
        try:
            while True:
                data = self._recevoir_tout(conn)
                
                if not data: break
                message = data.decode('utf-8', errors='ignore').strip()
                
                if "|" in message and "REQ" not in message and "INSCRIPTION" in message:
                    try:
                        parties = message.split('|')
                        if parties[0] == "INSCRIPTION":
                            ip_r = parties[1]
                            port_r = int(parties[2])
                            cle_r = parties[3]
                            
                            nouvelle_id = self.enregistrer_ou_mettre_a_jour_routeur(ip_r, port_r, cle_r)
                            if nouvelle_id:
                                conn.sendall(f"ACK|{nouvelle_id}".encode())
                                time.sleep(0.1)
                            else:
                                conn.sendall(b"NACK")
                    except Exception as e:
                        journalisation_log("MASTER", "ERREUR", f"Format invalide pour {addr[0]}: {e}")
                        conn.sendall(b"Erreur de format")

                # Demande Annuaire
                elif message == "REQ_LIST_KEYS" or message == "ANNUAIRE|GET":
                    journalisation_log("MASTER", "ANNUAIRE", f"Envoi de l'annuaire complet à {addr[0]}")
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
                        reponse = "\n".join(items)
                        conn.sendall(reponse.encode())
                        time.sleep(0.2)

                # Demande Nombre
                elif message == "REQ_NB_ROUTEURS":
                    nb = self.compter_routeurs()
                    conn.sendall(nb.encode())
                    time.sleep(0.1)

        except Exception as e:
            journalisation_log("MASTER", "ERREUR", f"Erreur Client {addr}: {e}")
        finally:
            conn.close()

    def _lancement_service_decouverte(self):
        socketUDP = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        socketUDP.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            socketUDP.bind(("0.0.0.0", self.Port_UDP))
            journalisation_log("MASTER", "UDP", f"Service découverte sur UDP/{self.Port_UDP}")
            while True:
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
        journalisation_log("MASTER", "INIT", "Démarrage des threads services...")
        
        threading.Thread(target=self._lancement_service_decouverte, daemon=True).start()
        
        socketTCPmaster = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        socketTCPmaster.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            socketTCPmaster.bind(('0.0.0.0', self.Port_TCP))
            socketTCPmaster.listen(50)
            journalisation_log("MASTER", "TCP", f"Serveur en écoute sur 0.0.0.0:{self.Port_TCP}")
            
            while True:
                conn, addr = socketTCPmaster.accept()
                threading.Thread(target=self._handle_client, args=(conn, addr), daemon=True).start()
        
        except Exception as e:
            journalisation_log("MASTER", "CRASH", f"Erreur critique du serveur : {e}")
        finally:
            socketTCPmaster.close()