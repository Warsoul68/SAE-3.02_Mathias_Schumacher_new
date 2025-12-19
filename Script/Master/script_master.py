import sys
import threading
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTextEdit, QGroupBox,
    QStackedWidget, QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox, QMainWindow
)
from PyQt5.QtCore import pyqtSignal, QObject, Qt

# Importation sécurisée
try:
    from Master import Master, definir_callback_gui
except ImportError:
    print("ERREUR : Master.py est introuvable dans le répertoire courant !")
    sys.exit()

class LogBridge(QObject):
    nouveau_signal_log = pyqtSignal(str)

# Configuration du port TCP
class PagePort(QWidget):
    port_valide = pyqtSignal(int)

    def __init__(self):
        super().__init__()
        mise_en_page = QVBoxLayout()
        mise_en_page.setAlignment(Qt.AlignCenter)

        titre = QLabel("Serveur Master - Configuration")
        titre.setStyleSheet("font-size: 24px; font-weight: bold; color: #1E88E5; margin-bottom: 20px;")
        mise_en_page.addWidget(titre)

        self.input_port = QLineEdit("6000")
        self.input_port.setPlaceholderText("Port TCP")
        self.input_port.setFixedWidth(250)
        self.input_port.setStyleSheet("padding: 10px; font-size: 16px; border-radius: 5px; border: 1px solid #CCC;")
        
        mise_en_page.addWidget(QLabel("Port d'écoute TCP :"))
        mise_en_page.addWidget(self.input_port)

        self.btn_start = QPushButton("Démarrer le Serveur")
        self.btn_start.setFixedWidth(250)
        self.btn_start.setStyleSheet("background-color: #1E88E5; color: white; padding: 12px; font-weight: bold; border-radius: 5px;")
        self.btn_start.setCursor(Qt.PointingHandCursor)
        self.btn_start.clicked.connect(self.valider_configuration)
        mise_en_page.addWidget(self.btn_start)

        self.setLayout(mise_en_page)

    def valider_configuration(self):
        try:
            port = int(self.input_port.text().strip())
            self.port_valide.emit(port)
        except ValueError:
            QMessageBox.warning(self, "Erreur", "Veuillez entrer un numéro de port valide.")
    
# Tableau de bord 
class PageDashboard(QWidget):
    def __init__(self):
        super().__init__()
        self.master_backend = None
        
        self.pont = LogBridge()
        self.pont.nouveau_signal_log.connect(self.ajouter_log_ecran)
        
        self.init_ui()

    def init_ui(self):
        mise_en_page_global = QVBoxLayout()

        # Tableau
        groupe_table = QGroupBox("Nœuds du Réseau (Annuaire BDD)")
        groupe_table.setStyleSheet("QGroupBox { font-weight: bold; }")
        mise_en_page_table = QVBoxLayout()
        
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["ID", "Adresse IP", "Port", "Clé Publique (Extrait)"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet("background-color: white; gridline-color: #ccc;")
        mise_en_page_table.addWidget(self.table)
        
        layout_boutons = QHBoxLayout()
        self.btn_refresh = QPushButton("Actualiser la liste")
        self.btn_refresh.clicked.connect(self.charger_donnees_bdd)
        
        self.btn_clear = QPushButton("Vider les logs")
        self.btn_clear.clicked.connect(lambda: self.console.clear())
        
        layout_boutons.addWidget(self.btn_refresh)
        layout_boutons.addWidget(self.btn_clear)
        mise_en_page_table.addLayout(layout_boutons)
        
        groupe_table.setLayout(mise_en_page_table)
        mise_en_page_global.addWidget(groupe_table)

        # Section log
        mise_en_page_global.addWidget(QLabel("Journal d'activité en temps réel :"))
        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setStyleSheet("background-color: #121212; color: #00E676; font-family: 'Consolas', monospace; font-size: 11px; border: 1px solid #333;")
        mise_en_page_global.addWidget(self.console)

        self.setLayout(mise_en_page_global)
    
    def demarrer_serveur(self, port):
        try:
            # instanciation du Master
            self.master_backend = Master(port_tcp=port)
            definir_callback_gui(self.pont.nouveau_signal_log.emit)
            
            threading.Thread(target=self.master_backend.demarrer_ecoute, daemon=True).start()
            
            self.ajouter_log_ecran(f"[GUI] Interface connectée au Master sur le port {port}.")
            
            threading.Timer(1.0, self.charger_donnees_bdd).start()
            
        except Exception as e:
            QMessageBox.critical(self, "Erreur Critique", f"Impossible de lancer le Master : {e}")
    
    def ajouter_log_ecran(self, texte):
        self.console.append(texte)
        sb = self.console.verticalScrollBar()
        sb.setValue(sb.maximum())
    
    def charger_donnees_bdd(self):
        if not self.master_backend: return

        try:
            routeurs = self.master_backend.get_tous_les_routeurs()
            
            self.table.setRowCount(0)
            for row_idx, r in enumerate(routeurs):
                self.table.insertRow(row_idx)
                
                r_id = str(r['id'])
                r_ip = r['ip']
                r_port = str(r['port'])
                r_cle = str(r['cle'])[:30] + "..."
                
                self.table.setItem(row_idx, 0, QTableWidgetItem(r_id))
                self.table.setItem(row_idx, 1, QTableWidgetItem(r_ip))
                self.table.setItem(row_idx, 2, QTableWidgetItem(r_port))
                self.table.setItem(row_idx, 3, QTableWidgetItem(r_cle))
                
        except Exception as e:
            self.ajouter_log_ecran(f"[GUI] Erreur lecture BDD : {e}")
    
# Fenêtre principale
class MasterApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Master - Gestion réseau en oignon")
        self.resize(1000, 700)

        self.stack = QStackedWidget()
        self.page_config = PagePort()
        self.page_dashboard = PageDashboard()
        
        self.stack.addWidget(self.page_config)
        self.stack.addWidget(self.page_dashboard)
        
        self.page_config.port_valide.connect(self.lancer_dashboard)
        
        self.setCentralWidget(self.stack)

    def lancer_dashboard(self, port):
        self.stack.setCurrentIndex(1)
        self.page_dashboard.demarrer_serveur(port)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion") 
    fenetre = MasterApp()
    fenetre.show()
    sys.exit(app.exec_())
    