import socket

HOST = "0.0.0.0"
PORT = 5000

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.bind((HOST, PORT))
s.listen(1)
print(f"[SERVEUR] En attente de connexion sur {HOST}:{PORT}...")

conn, addr = s.accept()
print(f"[SERVEUR] Connecté à : {addr}")

data = conn.recv(1024).decode()
print("[SERVEUR] Reçu :", data)

reponse = "Réponse du serveur PC"
conn.sendall(reponse.encode())

conn.close()
s.close()


