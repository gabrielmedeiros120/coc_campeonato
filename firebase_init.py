import os
import firebase_admin
from firebase_admin import credentials, firestore, auth, messaging

def init_firebase():
    """
    Inicializa o Firebase Admin usando variáveis de ambiente e retorna objetos úteis.
    """
    if not firebase_admin._apps:
        # Carrega as credenciais das env vars
        private_key = os.getenv("FIREBASE_PRIVATE_KEY")
        if not private_key:
            raise ValueError("FIREBASE_PRIVATE_KEY não configurada nas env vars.")

        cred_dict = {
            "type": os.getenv("FIREBASE_TYPE"),
            "project_id": os.getenv("FIREBASE_PROJECT_ID"),
            "private_key_id": os.getenv("FIREBASE_PRIVATE_KEY_ID"),
            "private_key": private_key.replace("\\n", "\n"),  # Corrige quebras de linha
            "client_email": os.getenv("FIREBASE_CLIENT_EMAIL"),
            "client_id": os.getenv("FIREBASE_CLIENT_ID"),
            "auth_uri": os.getenv("FIREBASE_AUTH_URI"),
            "token_uri": os.getenv("FIREBASE_TOKEN_URI"),
            "auth_provider_x509_cert_url": os.getenv("FIREBASE_AUTH_PROVIDER_X509_CERT_URL"),
            "client_x509_cert_url": os.getenv("FIREBASE_CLIENT_X509_CERT_URL"),
            "universe_domain": os.getenv("FIREBASE_UNIVERSE_DOMAIN")
        }
        cred = credentials.Certificate(cred_dict)
        firebase_admin.initialize_app(cred)
    db = firestore.client()
    return {
        "app": firebase_admin.get_app(),
        "auth": auth,
        "db": db,
        "messaging": messaging
    }

if __name__ == "__main__":
    f = init_firebase()
    print("Conexão com Firestore realizada com sucesso:", f["db"])