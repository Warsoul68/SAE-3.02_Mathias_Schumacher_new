import random
import os

# les différente fonction mathématique pour le chiffrement
def pgcd(a, b):
    while b != 0: a, b = b, a % b
    return a

def mod_inverse(e, phi):
    t, nouveau_t = 0, 1
    r, nouveau_r = phi, e

    while nouveau_r != 0:
        quotient = r // nouveau_r

        t, nouveau_t = nouveau_t, t - quotient * nouveau_t
        r, nouveau_r = nouveau_r, r - quotient * nouveau_r
    if r > 1: return None
    if t < 0: t = t + phi
    return t

def est_premier(num):
    if num < 2: return False
    if num == 2: return True
    if num % 2 == 0: return False
    for i in range(3, int(num ** 0.5) + 1, 2):
        if num %  i == 0: return False
    return True

def generer_paire_cle():
    premier = [i for i in range(100, 500) if est_premier(i)]
    p = random.choice(premier)
    q = random.choice(premier)
    while p == q: q = random.choice(premier)

    n = p * q
    phi = (p - 1) * (q - 1)

    e = random.randrange(1, phi)
    g = pgcd(e, phi)
    while g != 1:
        e = random.randrange(1, phi)
        g = pgcd(e, phi)

    d = mod_inverse(e, phi)
    return ((e, n), (d, n))

# La classe
class CryptoManager:
    def __init__(self, cle_pub="cle_publique.txt", cle_priv="cle_privee.txt"):
        self.c_pub = cle_pub
        self.c_priv = cle_priv
        self.publique = None
        self.privee = None

        self.charger_ou_generer()
    
    def charger_ou_generer(self):
        if os.path.exists(self.c_pub) and os.path.exists(self.c_priv):
            try:
                print("[Crypto] Chargement des clés...")
                with open(self.c_pub, "r") as f:
                    ligne = f.read().strip()
                    p = ligne.split(',')
                    self.publique = (int(p[0]), int(p[1]))

                with open(self.c_priv, "r") as f: 
                    ligne = f.read().strip()
                    p = ligne.split(',')
                    self.privee = (int(p[0]), int(p[1]))
                return
            except:
                print("[Crypto] Erreur lecture. On régénère.")
                return
            
        print("[Crypto] Génération nouvelle paire RSA...")
        self.publique, self.privee = generer_paire_cle()

        # CODE AMÉLIORÉ (dans charger_ou_generer, section écriture)
        with open(self.c_pub, "w") as f:
            f.write(f"{self.publique[0]},{self.publique[1]}")

        with open(self.c_priv, "w") as f:
            f.write(f"{self.privee[0]},{self.privee[1]}")

    def chiffrer(self, message, cle_pub_destinataire=None):
        cle_cible = cle_pub_destinataire if cle_pub_destinataire else self.publique
        e, n = cle_cible

        nombres = []
        for char in message:
            c = pow(ord(char), e, n)
            nombres.append(str(c))
        return ",".join(nombres)
    
    def dechiffrer(self, message_chiffrer_str):
        if not message_chiffrer_str: return ""
        d, n = self.privee

        message_clair = ""
        try:
            nombres = message_chiffrer_str.split(',')
            for c_str in nombres:
                if c_str.strip():
                    c = int(c_str)
                    m = pow(c, d, n)
                    message_clair += chr(m)
        except:
            return "[Erreur Déchiffrement]"
        return message_clair
    
    def get_pub_avec_str(self):
        return f"{self.publique[0]}, {self.publique[1]}"