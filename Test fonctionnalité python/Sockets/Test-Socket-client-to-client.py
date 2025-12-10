import socket

server_socket = socket.socket()
server_socket.bind(("0.0.0.0", 5000))
server_socket.listen(1)
conn, address = server_socket.accept()
message = conn.recv(1024).decode()
conn.send(reply.encode())
conn.close
server_socket.close