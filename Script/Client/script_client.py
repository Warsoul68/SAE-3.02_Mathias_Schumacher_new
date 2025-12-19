import sys
import threading
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTextEdit, QGroupBox,
    QSpinBox, QMessageBox, QStackedWidget, QFormLayout, QMainWindow
)
from PyQt5.QtCore import pyqtSignal, QObject, Qt

try:
    # Import de la classe client
    from Client import Client, definir_callback_client
except ImportError:
    print("ERREUR CRITIQUE : Le fichier Client.py est introuvable !")
    sys.exit()

class LogBridge(QObject):
    """Pont pour transmettre les logs du thread vers l'interface graphique"""
    nouveau_signal_log = pyqtSignal(str)

# Page de configuration
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

        groupe = QGroupBox("Paramètres de la Passerelle")
        
        formulaire = QFormLayout()
        
        self.input_ip = QLineEdit("192.168.1.X")
        self.input_ip.setPlaceholderText("Ex: 10.0.x.x (VM) ou 192.168.x.x (PC)")
        self.input_pr = QLineEdit("8080") 
        self.input_pc = QLineEdit("8888") 

        formulaire.addRow("IP Passerelle :", self.input_ip)
        formulaire.addRow("Port Passerelle :", self.input_pr)
        formulaire.addRow("Mon Port Local :", self.input_pc)

        lbl_aide = QLabel("<b>Aide :</b> Si votre Windows est en réseau 'intnet', utilisez l'IP interne du routeur (10.0.x.x).")
        lbl_aide.setWordWrap(True)
        lbl_aide.setStyleSheet("color: #555; font-size: 11px; margin-top: 10px; font-style: italic;")

        aide_groupe = QVBoxLayout()
        aide_groupe.addLayout(formulaire)
        aide_groupe.addWidget(lbl_aide)
        groupe.setLayout(aide_groupe)
        mise_en_page.addWidget(groupe)

        btn = QPushButton("Démarrer le Client")
        btn.setStyleSheet("background-color: #2196F3; color: white; padding: 12px; font-weight: bold; border-radius: 5px;")
        btn.clicked.connect(self.valider)
        mise_en_page.addWidget(btn)

        self.setLayout(mise_en_page)
    
    def valider(self):
        ip = self.input_ip.text().strip()
        if not ip: return QMessageBox.warning(self, "Erreur", "L'IP est requise.")
        try:
            pr = int(self.input_pr.text())
            pc = int(self.input_pc.text())
            self.config_validee.emit(ip, pr, pc)
        except ValueError:
            QMessageBox.warning(self, "Erreur", "Ports invalides.")
    
# Page de Messagerie
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
        self.lbl_statut.setStyleSheet("background-color: #333; color: white; padding: 10px; font-weight: bold; border-radius: 5px;")
        mise_en_page_principal.addWidget(self.lbl_statut)

        groupe = QGroupBox("Envoi de Message")
        mise_en_page_groupe = QVBoxLayout()
        
        self.btn_annuaire = QPushButton("Actualiser l'Annuaire Réseau")
        self.btn_annuaire.clicked.connect(self.get_annuaire)
        mise_en_page_groupe.addWidget(self.btn_annuaire)

        formulaire_dest = QFormLayout()
        self.in_dest_ip = QLineEdit()
        self.in_dest_ip.setPlaceholderText("IP cible (Ex: 10.0.0.x ou 192.168.1.x)")
        self.in_dest_port = QLineEdit("9000")
        formulaire_dest.addRow("IP Destinataire :", self.in_dest_ip)
        formulaire_dest.addRow("Port Destinataire :", self.in_dest_port)
        mise_en_page_groupe.addLayout(formulaire_dest)

        l_common = QHBoxLayout()
        self.spin_sauts = QSpinBox()
        self.spin_sauts.setRange(1, 1) # Mettre (1, 3) si tu as assez de routeurs
        self.spin_sauts.setPrefix("Circuit : ")
        self.spin_sauts.setSuffix(" rebonds")
        l_common.addWidget(QLabel("Complexité du trajet :"))
        l_common.addWidget(self.spin_sauts)
        mise_en_page_groupe.addLayout(l_common)

        l_msg = QHBoxLayout()
        self.in_msg = QLineEdit()
        self.in_msg.setPlaceholderText("Écrivez votre message")
        self.btn_send = QPushButton("Envoyer")
        self.btn_send.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; padding: 8px;")
        self.btn_send.clicked.connect(self.envoyer)
        l_msg.addWidget(self.in_msg)
        l_msg.addWidget(self.btn_send)
        mise_en_page_groupe.addLayout(l_msg)

        groupe.setLayout(mise_en_page_groupe)
        mise_en_page_principal.addWidget(groupe)

        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setStyleSheet("background-color: #000; color: #FFF; font-family: Consolas; font-size: 11px;")
        mise_en_page_principal.addWidget(self.console)

        self.setLayout(mise_en_page_principal)

    def demarrer(self, ip, pr, pc):
        self.lbl_statut.setText(f"Connecté - Passerelle: {ip}:{pr}")
        try:
            self.client_backend = Client(ip, pr, pc)
            definir_callback_client(self.pont.nouveau_signal_log.emit)
            self.get_annuaire()
        except Exception as e:
            self.log_ui(f"[ERREUR] Impossible de lancer le backend : {e}")

    def log_ui(self, txt):
        self.console.append(txt)
        self.console.verticalScrollBar().setValue(self.console.verticalScrollBar().maximum())

    def get_annuaire(self):
        if self.client_backend: 
            threading.Thread(target=self._th_annuaire).start()
    
    def _th_annuaire(self):
        res = self.client_backend.recuperer_annuaire_complet()
        if res: 
            self.signal_maj_annuaire.emit(len(res))

    def update_spinbox(self, n):
        self.spin_sauts.setMaximum(max(1, n))
        self.spin_sauts.setValue(min(2, n))
        self.log_ui(f"Annuaire chargé : {n} nœuds disponibles.")
    
    def envoyer(self):
        if not self.client_backend: return
        message = self.in_msg.text()
        sauts = self.spin_sauts.value()
        
        if not message: return QMessageBox.warning(self, "Erreur", "Message vide.")
        
        ip = self.in_dest_ip.text().strip()
        try: 
            port = int(self.in_dest_port.text().strip())
        except ValueError: 
            return QMessageBox.warning(self, "Erreur", "Port invalide.")
        
        if not ip: return QMessageBox.warning(self, "Erreur", "L'IP est requise.")

        threading.Thread(target=self.client_backend.envoyer_message,
                         args=((ip, port), message, sauts)).start()
        
        self.in_msg.clear()
    
# Page principal
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Messagerie Oignon")
        self.resize(700, 600)
        
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