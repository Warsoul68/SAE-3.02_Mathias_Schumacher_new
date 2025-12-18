import sys
import datetime
import threading
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTextEdit, QGroupBox,
    QStackedWidget, QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox, QMainWindow
)
from PyQt5.QtCore import pyqtSignal, QObject, Qt

# Import de la classe Master
try:
    from Script.Master.Master import Master, journalisation_log
except ImportError:
    print("ERREUR : Master.py est introuvable dans le répertoire courant !")
    sys.exit()

class LogBridge(QObject):
    nouveau_signal_log = pyqtSignal(str)

# Configuration initiale
class PagePort(QWidget):
    port_valide = pyqtSignal(int)

    def __init__(self):
        super().__init__()
        mise_en_page_principal = QVBoxLayout()
        mise_en_page_principal.setAlignment(Qt.AlignCenter)

        titre = QLabel("Administration du Master")
        titre.setStyleSheet("font-size: 24px; font-weight: bold; color: #1E88E5; margin-bottom: 20px;")
        mise_en_page_principal.addWidget(titre)

        self.input_port = QLineEdit("8080")
        self.input_port.setFixedWidth(250)
        self.input_port.setStyleSheet("padding: 10px; font-size: 16px; border-radius: 5px; border: 1px solid #CCC;")
        
        mise_en_page_principal.addWidget(QLabel("Port d'écoute TCP :"))
        mise_en_page_principal.addWidget(self.input_port)

        self.btn_start = QPushButton("Lancer le Serveur")
        self.btn_start.setFixedWidth(250)
        self.btn_start.setStyleSheet("background-color: #1E88E5; color: white; padding: 12px; font-weight: bold; border-radius: 5px;")
        self.btn_start.clicked.connect(self.valider_configuration)
        mise_en_page_principal.addWidget(self.btn_start)

        self.setLayout(mise_en_page_principal)

    def valider_configuration(self):
        try:
            port = int(self.input_port.text().strip())
            self.port_valide.emit(port)
        except ValueError:
            QMessageBox.warning(self, "Erreur", "Veuillez entrer un numéro de port valide.")

# Tableau de bord principal
class PageDashboard(QWidget):
    def __init__(self):
        super().__init__()
        self.master_backend = None
        self.pont = LogBridge()
        self.pont.nouveau_signal_log.connect(self.ajouter_log_ecran)
        self.init_ui()

    def init_ui(self):
        mise_en_page_global = QVBoxLayout()

        groupe_table = QGroupBox("Nœuds du Réseau Oignon (Base de Données)")
        mise_en_page_interne_table = QVBoxLayout()
        
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["ID", "Adresse IP", "Port", "Clé Publique"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setStyleSheet("background-color: white;")
        mise_en_page_interne_table.addWidget(self.table)
        
        layout_boutons = QHBoxLayout()
        
        self.btn_refresh = QPushButton("🔄 Actualiser la liste")
        self.btn_refresh.setStyleSheet("padding: 8px; font-weight: bold;")
        self.btn_refresh.clicked.connect(self.charger_donnees_bdd)

        self.btn_clear = QPushButton("🗑️ Effacer la console")
        self.btn_clear.setStyleSheet("padding: 8px;")
        self.btn_clear.clicked.connect(lambda: self.console.clear())
        
        layout_boutons.addWidget(self.btn_refresh)
        layout_boutons.addWidget(self.btn_clear)
        
        mise_en_page_interne_table.addLayout(layout_boutons)
        
        groupe_table.setLayout(mise_en_page_interne_table)

        mise_en_page_global.addWidget(groupe_table)

        mise_en_page_global.addWidget(QLabel("Activité du serveur :"))
        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setStyleSheet("background-color: #121212; color: #00E676; font-family: 'Consolas'; font-size: 11px;")
        mise_en_page_global.addWidget(self.console)

        self.setLayout(mise_en_page_global)
    
    def demarrer_serveur(self, port):
        try:
            self.master_backend = Master(port)
            self.installer_hook_logs()
            
            threading.Thread(target=self.master_backend.demarrer_ecoute, daemon=True).start()
            
            self.ajouter_log_ecran(f"Master opérationnel sur le port {port}")
            self.charger_donnees_bdd()
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Erreur lors du démarrage : {e}")
    
    def installer_hook_logs(self):
        import Script.Master.Master as MasterModule   
        fonction_originale = MasterModule.journalisation_log

        def nouveau_log_intercepteur(qui, type_msg, message, callback=None):
            # On garde l'écriture dans le fichier original
            fonction_originale(qui, type_msg, message)

            heure = datetime.datetime.now().strftime("%H:%M:%S")
            texte_formate = f"[{heure}] [{qui}] {message}"
            
            self.pont.nouveau_signal_log.emit(texte_formate)

        MasterModule.journalisation_log = nouveau_log_intercepteur

    def ajouter_log_ecran(self, texte):
        self.console.append(texte)
        self.console.verticalScrollBar().setValue(self.console.verticalScrollBar().maximum())
    
    def charger_donnees_bdd(self):
        if hasattr(self.master_backend, 'get_tous_les_routeurs'):
            routeurs = self.master_backend.get_tous_les_routeurs()
            self.table.setRowCount(0)
            for row_idx, r in enumerate(routeurs):
                self.table.insertRow(row_idx)
                r_id = str(r.get('id', row_idx) if isinstance(r, dict) else r[0])
                r_ip = str(r.get('ip', 'N/A') if isinstance(r, dict) else r[1])
                r_port = str(r.get('port', 'N/A') if isinstance(r, dict) else r[2])
                r_cle = str(r.get('cle', '')[:25] if isinstance(r, dict) else r[3][:25]) + "..."
                
                self.table.setItem(row_idx, 0, QTableWidgetItem(r_id))
                self.table.setItem(row_idx, 1, QTableWidgetItem(r_ip))
                self.table.setItem(row_idx, 2, QTableWidgetItem(r_port))
                self.table.setItem(row_idx, 3, QTableWidgetItem(r_cle))
        else:
            self.ajouter_log_ecran("[ERREUR] Méthode 'get_tous_les_routeurs' manquante dans Master.py !")

# Fenêtre principale
class MasterApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Master Panel de Contrôle")
        self.resize(950, 650)

        self.stack = QStackedWidget()
        self.p1 = PagePort()
        self.p2 = PageDashboard()
        
        self.stack.addWidget(self.p1)
        self.stack.addWidget(self.p2)
        
        self.p1.port_valide.connect(self.basculer_affichage)
        self.setCentralWidget(self.stack)

    def basculer_affichage(self, port):
        self.stack.setCurrentIndex(1)
        self.p2.demarrer_serveur(port)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    fenetre = MasterApp()
    fenetre.show()
    sys.exit(app.exec_())
