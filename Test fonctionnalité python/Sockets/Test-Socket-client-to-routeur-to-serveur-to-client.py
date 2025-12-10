import socket

ROUTER_HOST = "192.168.1.38"  # IP du routeur côté bridge
ROUTER_PORT = 6000

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect((ROUTER_HOST, ROUTER_PORT))
print("[CLIENT A] Connecté au routeur.")

message = "Bonjour Master via Routeur !"
s.sendall(message.encode())
print("[CLIENT A] Message envoyé :", message)

reponse = s.recv(1024).decode()
print("[CLIENT A] Réponse reçue :", reponse)

s.close()
