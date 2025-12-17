import sys
import datetime
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTextEdit, QGroupBox,
    QSpinBox, QMessageBox, QStackedWidget, QFormLayout, QMainWindow
)
from PyQt5.QtCore import pyqtSignal, QObject, Qt

try:
    from Client import Client, journalisation_log
except ImportError:
    print("ERREUR CRITIQUE : Le fichier Client.py est introuvable dans le dossier !")
    sys.exit()

# le pont de logs
class LogBridge(QObject):
    nouveau_signal_log = pyqtSignal(str)

# la page de configuration
class PageConfig(QWidget):
    config_validee = pyqtSignal(str, int, int)

    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        mise_en_page = QVBoxLayout()
        mise_en_page.setAlignment(Qt.AlignCenter)

        lbl_titre = QLabel("Connexion réseau TOR")
        lbl_titre.setStyleSheet("font-size: 24px; font-weight: bold; color: #4CAF50; margin-bottom: 20px;")
        lbl_titre.setAlignment(Qt.AlignCenter)
        mise_en_page.addWidget(lbl_titre)

        formulaire_groupe = QGroupBox("Paramètres")
        formulaire_mise_en_page = QFormLayout()

        self.input_ip_routeur = QLineEdit("10.0.0.1")
        self.input_port_routeur = QLineEdit("8080")
        self.input_port_client = QLineEdit("8888")

        formulaire_mise_en_page.addRow("IP passerelle :", self.input_ip_routeur)
        formulaire_mise_en_page.addRow("Port Passerelle :", self.input_port_routeur)
        formulaire_mise_en_page.addRow("Mon port d'écoute :", self.input_port_client)

        formulaire_groupe.setLayout(formulaire_mise_en_page)
        mise_en_page.addWidget(formulaire_groupe)

        self.btn_valider = QPushButton("Démarrer le client")
        self.btn_valider.setStyleSheet("background-color: #2196F3; color: white; padding: 12px; font-weight: bold;")
        self.btn_valider.clicked.connect(self.verifier_et_envoyer)
        mise_en_page.addWidget(self.btn_valider)

        self.setLayout(mise_en_page)

    def verifier_et_envoyer(self):
        ip = self.input_ip_routeur.text().strip()
        try:
            port_routeur = int(self.input_port_routeur.text().strip())
            port_client = int(self.input_port_client.text().strip())
            self.config_validee.emit(ip, port_routeur, port_client)
        except ValueError:
            QMessageBox.warning(self, "Erreur", "Les ports doivent être des nombres.")

# Page de la messagerie
class PageMessagerie(QWidget):
    def __init__(self):
        super().__init__()
        self.pont = LogBridge()
        self.pont.nouveau_signal_log.connect(self.mise_a_jour_zone_log)
        self.client_backend = None
        self.init_ui()
    
    def init_ui(self):
        mise_en_page = QVBoxLayout()
        self.lbl_info = QLabel("Statut : Deconnecté")
        self.lbl_info.setStyleSheet("background-color: #333; color: white; padding: 5px;")
        mise_en_page.addWidget(self.lbl_info)

        groupe_messagerie = QGroupBox("Messagerie Oignon")
        mise_en_page_messagerie = QVBoxLayout()
        self.btn_annuaire = QPushButton("Récuperer l'annuaire")
        self.btn_annuaire.clicked.connect(self.get_annuaire)
        mise_en_page_messagerie.addWidget(self.btn_annuaire)
        mise_en_page.addWidget(groupe_messagerie)

        mise_en_page_envoyer = QHBoxLayout()
        self.in_dest = QLineEdit()
        self.in_dest.setPlaceholderText("IP Destinataire")
        self.spin_sauts = QSpinBox()
        self.spin_sauts.setRange(1, 10)
        self.spin_sauts.setPrefix("Sauts: ")
        mise_en_page_envoyer.addWidget(self.in_dest)
        mise_en_page_envoyer.addWidget(self.spin_sauts)
        mise_en_page_messagerie.addLayout(mise_en_page_envoyer)

        mise_en_page_message = QHBoxLayout()
        self.in_message = QLineEdit()
        self.in_message.setPlaceholderText("Message...")
        self.btn_envoyer = QPushButton("Envoyer")
        self.btn_envoyer.clicked.connect(self.envoyer_oignon)
        self.btn_envoyer.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        mise_en_page_message.addWidget(self.in_message)
        mise_en_page_message.addWidget(self.btn_envoyer)
        mise_en_page_messagerie.addLayout(mise_en_page_message)

        groupe_messagerie.setLayout(mise_en_page_messagerie)
        
        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setStyleSheet("background-color: black; color: #00FF00; font-family: Consolas;")
        groupe_messagerie.setLayout(mise_en_page_messagerie)
        mise_en_page.addWidget(self.console)
        self.setLayout(mise_en_page)
    
    def demarrer_backend(self, ip, port_routeur, port_client):
        self.lbl_info.setText(f"Connecté | Passerelle: {ip}:{port_routeur}")
        self.client_backend = Client(ip, port_routeur, port_client)
        self.rediriger_logs()
    
    def rediriger_logs(self):
        import Client as ClientModule
        logs_original = ClientModule.journalisation_log

        def custom_log(qui, type_message, message, callback=None):
            logs_original(qui, type_message, message)
            maitenant = datetime.datetime.now().strftime("%H:%M:%S")
            self.pont.nouveau_signal_log.emit(f"[{maitenant}] [{qui}] [{type_message}] {message}")
        
        ClientModule.journalisation_log = custom_log
    
    def mise_a_jour_zone_log(self, texte):
        self.console.append(texte)
        self.console.verticalScrollBar().setValue(self.console.verticalScrollBar().maximum())
    
    def get_annuaire(self):
        if not self.client_backend: return
        res = self.client_backend.recuperer_annuaire_complet()
        if res:
            self.spin_sauts.setMaximum(len(res))
            self.mise_a_jour_zone_log(f"Annuaire reçu : {len(res)} routeurs")
    
    def envoyer_oignon(self):
        if not self.client_backend: return
        dest = self.in_dest.text()
        message = self.in_message.text()
        sauts = self.spin_sauts.value()
        if dest and message:
            self.client_backend.envoyer_message(dest, message, sauts)

# Fenétre principal
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Interface Client")
        self.resize(800, 600)
        self.stack = QStackedWidget()
        self.page_config = PageConfig()
        self.page_messagerie = PageMessagerie()
        self.stack.addWidget(self.page_config)
        self.stack.addWidget(self.page_messagerie)
        self.page_config.config_validee.connect(self.passer_a_messagerie)
        self.setCentralWidget(self.stack)
    
    def passer_a_messagerie(self, ip, port_routeur, port_client):
        self.page_messagerie.demarrer_backend(ip, port_routeur, port_client)
        self.stack.setCurrentIndex(1)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    fenetre = MainWindow()
    fenetre.show()
    sys.exit(app.exec_())