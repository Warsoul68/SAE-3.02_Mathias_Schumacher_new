SAE 3.02 : Conception d'une architecture distribuée avec routage en oignon

1. présentation du projet :
   le projet s'inscrit dans le cadre de la SAE 3.02 et a pour objectif de développer un système de messagerie sécurisé et anonyme basé sur le protocole de routage en oignon. L'enjeu principal est de garantir la confidentialité et l'anonymat total des échanges entre deux utilisateurs (Client A et Client B).
   Le mécanisme de l'oignon :
   Contrairement à une communication directe, le message transite par plusieurs routeurs intermédiaires qui servent de relais.
   	- Encapsulation : L'expéditeur "enveloppe" son message dans plusieurs couches de chiffrement successives à l'aide de l'algorithme RSA.

&nbsp;  	- Épluchage : À chaque saut, le routeur retire une couche de protection (il "épluche" l'oignon) pour découvrir uniquement l'adresse du prochain destinataire.

&nbsp;  	- Confidentialité : Chaque nœud ne connaît que l'appareil qui lui a envoyé le paquet et celui à qui il doit le transmettre ; personne ne connaît le chemin complet.




2\. Composant du système :

&nbsp;	- le master (annuaire) : 

&nbsp;         Le Master est le pilier central de l'architecture. Il agit comme un "chef de gare" 
	  et un annuaire dynamique pour l'ensemble du réseau. Ses principales missions sont :
		- Gestion de la Base de Données : Il utilise MariaDB pour recenser et stocker 
		  les informations vitales des routeurs actifs (Adresses IP, ports et clés publiques RSA).

&nbsp;		- Nettoyage du Réseau : À chaque démarrage, le Master réinitialise la table de routage pour garantir que seuls 
		  les nœuds réellement connectés sont proposés aux clients.

&nbsp;		- Protocoles de Communication :
			- UDP : Utilisé pour le service de découverte rapide ("Plug \& Play") et pour l'envoi de statistiques légères, 
				comme le nombre de routeurs en ligne.

&nbsp;			- TCP : Réservé aux échanges de données fiables, notamment pour l'inscription des routeurs et 
				la diffusion de l'annuaire complet aux clients.

&nbsp;		- Diffusion de l'Annuaire : Lorsqu'un client souhaite envoyer un message, le Master lui transmet 
		  la liste des nœuds disponibles. Cela permet au client de construire son circuit de chiffrement et 
		  de définir son parcours de sauts de manière totalement aléatoire.

&nbsp;		- Multi-threading : Grâce à la gestion des threads, le Master peut traiter simultanément les requêtes 
	          de dizaines de clients et de routeurs sans interruption de service.


&nbsp;	 - Routeurs hybride : 

&nbsp;	   L'unité fondamentale de ce réseau est le nœud hybride. Contrairement à un réseau classique, chaque routeur possède 

&nbsp;	   une double identité logicielle, ce qui renforce considérablement la sécurité et la flexibilité du système.

&nbsp;		- Le rôle de Relais (Routeur) : Lorsqu'un nœud reçoit un paquet qui ne lui est pas destiné, 
		  il agit comme une passerelle. Il utilise sa propre clé privée pour "éplucher" la couche externe de l'oignon, 
 		  découvre l'adresse du prochain saut grâce au délimiteur, et transmet le reste du message au successeur.

&nbsp;		- Le rôle de Client (Émetteur/Destinataire) : Chaque routeur est également capable d'initier ses propres 
		  communications. Il peut consulter l'annuaire du Master, construire son propre oignon chiffré et l'injecter 
		  dans le réseau vers un autre client ou un autre routeur.

&nbsp;		- Anonymat Renforcé : Cette nature hybride permet de "noyer le poisson" : pour un observateur extérieur, 
		  il est impossible de distinguer si le message qui sort d'un nœud a été créé par l'utilisateur de cette machine 
		  ou s'il s'agit d'un simple relais pour un tiers.

&nbsp;		- Double Interface Réseau : Pour assurer ce rôle de pont, les routeurs sont configurés sur deux interfaces simultanées : 
		  le réseau Bridge (pour l'entrée depuis le monde physique) et le réseau Interne (pour la circulation isolée et privée).


&nbsp;	  - Le client :

&nbsp;	    Le client est l'initiateur de la communication. Il possède une "vue d'ensemble" du réseau grâce au Master et applique 
	    les couches de sécurité nécessaires pour garantir son propre anonymat.

&nbsp;		- Consultation de l'Annuaire : Avant tout envoi, le client interroge le Master via une requête UDP pour obtenir 
		  la liste des nœuds hybrides actifs (adresses IP, ports et clés publiques RSA).

&nbsp;		- Fabrication de l'Oignon (Encapsulation) : Le client choisit un chemin de manière aléatoire parmi les routeurs 
		  disponibles pour construire un circuit éphémère. Il utilise ensuite mon module maison CryptoManager pour chiffrer 
 		  le message de "l'intérieur vers l'extérieur" : chaque couche est verrouillée avec la clé publique d'un routeur spécifique du circuit.

&nbsp;		- Expédition et Protection : Une fois l'oignon construit, le client ouvre une connexion TCP vers le premier maillon du circuit 
		  (le point d'entrée) et lui transmet le paquet brut. Comme il ne communique qu'avec ce premier nœud, son identité reste protégée vis-à-vis 
		  du reste de la chaîne.

&nbsp;		- Écoute Passive : Le client intègre un fil d'exécution (Thread) dédié à l'écoute sur un port local. Cela lui permet de rester 
		  réactif et de recevoir des messages ou des confirmations en retour tout en préparant de nouveaux envois.





3\. Prérequis logiciels et infrastructure

&nbsp;  Pour déployer et tester l'architecture de routage en oignon, vous aurez besoin des éléments suivants :
3.1. Virtualisation et Systèmes d'exploitation :

&nbsp;		- Hyperviseur (Logiciel de virtualisation) : VirtualBox est recommandé pour gérer les segments réseaux Bridge et Intnet.

&nbsp;				- lien : https://www.virtualbox.org/wiki/Downloads
		- ISO Debian 12 : Utilisé pour les VM Master et les Routeurs.

&nbsp;				- lien : https://lecrabeinfo.net/telecharger/debian-12-64-bits/

&nbsp;		- ISO Windows 10 : Utilisé pour l'hôte physique ou les VM de test Client.

&nbsp;				- lien : https://telecharger.malekal.com/download/windows-10-22h2-x64/



3.2. Environnement de développement Python :
		- Python 3.x : Doit être installé sur toutes les machines.

&nbsp;				- lien : https://www.python.org/downloads/

&nbsp;		- Éditeur de code / IDE : Visual Studio Code est recommandé pour l'édition des scripts sous Windows.

&nbsp;				- lien : https://code.visualstudio.com/download



3.3. Services Systèmes et Serveurs :

Certains services spécifiques doivent être installés sur les machines Debian :

&nbsp;		- MariaDB : Indispensable sur la VM Master pour stocker l'annuaire des routeurs.

&nbsp;		- iptables : Requis sur les VM Routeurs pour configurer les règles de routage et l'accès Internet entre les interfaces réseau.



3.4. Bibliothèques Python (Dépendances) :
Certaines bibliothèques doivent être installées via pip pour permettre le fonctionnement des interfaces et de la base de données :

&nbsp;		- PyQt5 : Utilisée pour l'interface graphique du Master et du Client.

&nbsp;		- mysql-connector-python : Permet la liaison entre le script Python du Master et la base de données MariaDB.

Note importante : Les autres bibliothèques utilisées dans le projet (socket, threading, time, os, sys, random) sont incluses par défaut dans la bibliothèque standard de Python et ne nécessitent aucune installation manuelle.

