import sys
import datetime
import threading
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTextEdit, QGroupBox,
    QSpinBox, QMessageBox, QStackedWidget, QFormLayout, QMainWindow,
    QTabWidget
)
from PyQt5.QtCore import pyqtSignal, QObject, Qt

try:
    # Import de la classe client
    from Client import Client, definir_callback_client
except ImportError:
    print("ERREUR CRITIQUE : Le fichier Client.py est introuvable dans le dossier !")
    sys.exit()

class LogBridge(QObject):
    nouveau_signal_log = pyqtSignal(str)


class PageConfig(QWidget):
    config_validee = pyqtSignal(str, int, int)

    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        mise_en_page = QVBoxLayout()
        mise_en_page.setAlignment(Qt.AlignCenter)
        
        lbl = QLabel("Connexion Réseau Oignon")
        lbl.setStyleSheet("font-size: 24px; font-weight: bold; color: #4CAF50; margin-bottom: 20px;")
        lbl.setAlignment(Qt.AlignCenter)
        mise_en_page.addWidget(lbl)

        group = QGroupBox("Configuration Passerelle")
        form = QFormLayout()
        
        self.input_ip = QLineEdit("192.168.1.X")
        self.input_ip.setPlaceholderText("IP du Routeur Linux")
        self.input_pr = QLineEdit("8081")
        self.input_pc = QLineEdit("9000")

        form.addRow("IP Routeur (Passerelle) :", self.input_ip)
        form.addRow("Port Routeur :", self.input_pr)
        form.addRow("Mon Port Local :", self.input_pc)

        group.setLayout(form)
        mise_en_page.addWidget(group)

        btn = QPushButton("Se Connecter")
        btn.setStyleSheet("background-color: #2196F3; color: white; padding: 12px; font-weight: bold;")
        btn.clicked.connect(self.valider)
        mise_en_page.addWidget(btn)

        self.setLayout(mise_en_page)
    
    def valider(self):
        ip = self.input_ip.text().strip()
        if not ip: return QMessageBox.warning(self, "Erreur", "IP requise.")
        try:
            pr = int(self.input_pr.text())
            pc = int(self.input_pc.text())
            self.config_validee.emit(ip, pr, pc)
        except ValueError:
            QMessageBox.warning(self, "Erreur", "Ports invalides.")
    
    # Page messagerie
class PageMessagerie(QWidget):
    signal_maj_annuaire = pyqtSignal(int)

    def __init__(self):
        super().__init__()
        self.client_backend = None
        self.pont = LogBridge()
        self.pont.nouveau_signal_log.connect(self.log_ui)
        self.signal_maj_annuaire.connect(self.update_spinbox)
        self.init_ui()

    def init_ui(self):
        mise_en_page_principal = QVBoxLayout()
        self.lbl_statut = QLabel("Statut : Déconnecté")
        self.lbl_statut.setStyleSheet("background-color: #333; color: white; padding: 5px; font-weight: bold;")
        mise_en_page_principal.addWidget(self.lbl_statut)

        groupe = QGroupBox("Envoi de Message")
        mise_en_page_groupe = QVBoxLayout()
        
        self.btn_annuaire = QPushButton("🔄 Télécharger l'Annuaire")
        self.btn_annuaire.clicked.connect(self.get_annuaire)
        mise_en_page_groupe.addWidget(self.btn_annuaire)

        self.tables = QTabWidget()
        
        # Page 1 vers le client
        self.table_client = QWidget()
        l_client = QFormLayout()
        self.in_c_ip = QLineEdit()
        self.in_c_ip.setPlaceholderText("ex: 192.168.1.50")
        self.in_c_port = QLineEdit("9000")
        l_client.addRow("IP Destinataire :", self.in_c_ip)
        l_client.addRow("Port Destinataire :", self.in_c_port)
        self.table_client.setLayout(l_client)
    
    # Page 2 vers le routeur
        self.table_routeur = QWidget()
        l_routeur = QFormLayout()
        self.in_r_id = QLineEdit()
        self.in_r_id.setPlaceholderText("ID du Nœud (ex: 2)")
        l_routeur.addRow("ID du Routeur :", self.in_r_id)
        self.table_routeur.setLayout(l_routeur)

        self.tables.addTab(self.table_client, "📤 Vers un Client (IP)")
        self.tables.addTab(self.table_routeur, "🔒 Vers un Nœud (ID)")

        mise_en_page_groupe.addWidget(self.tables)

        # Options communes (Sauts + Message)
        l_common = QHBoxLayout()
        self.spin_sauts = QSpinBox()
        self.spin_sauts.setRange(1, 1)
        self.spin_sauts.setPrefix("Relais: ")
        l_common.addWidget(QLabel("Complexité :"))
        l_common.addWidget(self.spin_sauts)
        mise_en_page_groupe.addLayout(l_common)

        l_msg = QHBoxLayout()
        self.in_msg = QLineEdit()
        self.in_msg.setPlaceholderText("Votre message secret...")
        self.btn_send = QPushButton("Envoyer")
        self.btn_send.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        self.btn_send.clicked.connect(self.envoyer)
        l_msg.addWidget(self.in_msg)
        l_msg.addWidget(self.btn_send)
        mise_en_page_groupe.addLayout(l_msg)

        groupe.setLayout(mise_en_page_groupe)
        mise_en_page_principal.addWidget(groupe)

        # Logs
        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setStyleSheet("background-color: #111; color: #0f0; font-family: Consolas; font-size: 11px;")
        mise_en_page_principal.addWidget(self.console)

        self.setLayout(mise_en_page_principal)
    
    def demarrer(self, ip, pr, pc):
        self.lbl_statut.setText(f"Connecté à {ip}:{pr}")
        try:
            self.client_backend = Client(ip, pr, pc)
            definir_callback_client(self.pont.nouveau_signal_log.emit)
            self.get_annuaire()
        except Exception as e:
            self.log_ui(f"[ERREUR] {e}")

    def log_ui(self, txt):
        self.console.append(txt)
        self.console.verticalScrollBar().setValue(self.console.verticalScrollBar().maximum())

    def get_annuaire(self):
        if self.client_backend: threading.Thread(target=self._th_annuaire).start()

    def _th_annuaire(self):
        res = self.client_backend.recuperer_annuaire_complet()
        if res: self.signal_maj_annuaire.emit(len(res))

    def update_spinbox(self, n):
        self.spin_sauts.setMaximum(max(1, n))
        self.spin_sauts.setValue(min(3, n))
        self.log_ui(f"Annuaire chargé : {n} nœuds.")
    
    def envoyer(self):
        if not self.client_backend: return
        message = self.in_msg.text()
        sauts = self.spin_sauts.value()
        
        if not message: return QMessageBox.warning(self, "Erreur", "Message vide.")

        # On regarde quel onglet est actif
        index = self.tables.currentIndex()
        
        if index == 0: # Onglet CLIENT (IP)
            ip = self.in_c_ip.text().strip()
            try: port = int(self.in_c_port.text())
            except: return QMessageBox.warning(self, "Erreur", "Port invalide.")
            
            if not ip: return QMessageBox.warning(self, "Erreur", "IP requise.")
            
            threading.Thread(target=self.client_backend.envoyer_message,
                             args=((ip, port), message, sauts, "CLIENT")).start()
            
        elif index == 1: 
            rid = self.in_r_id.text().strip()
            if not rid: return QMessageBox.warning(self, "Erreur", "ID requis.")
            
            threading.Thread(target=self.client_backend.envoyer_message,
                             args=(rid, message, sauts, "ROUTEUR")).start()

        self.in_msg.clear()
    
# Fenétre principale
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Client Oignon (Hybride)")
        self.resize(600, 700)
        self.stack = QStackedWidget()
        self.p1 = PageConfig()
        self.p2 = PageMessagerie()
        self.stack.addWidget(self.p1)
        self.stack.addWidget(self.p2)
        self.p1.config_validee.connect(self.lancer_chat)
        self.setCentralWidget(self.stack)

    def lancer_chat(self, ip, pr, pc):
        self.p2.demarrer(ip, pr, pc)
        self.stack.setCurrentIndex(1)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    w = MainWindow()
    w.show()
    sys.exit(app.exec_())
    
