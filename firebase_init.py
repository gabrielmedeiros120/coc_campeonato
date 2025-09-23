import firebase_admin
from firebase_admin import credentials, firestore, auth, messaging

def init_firebase(service_account_path: str = "serviceAccountKey.json"):
    """
    Inicializa o Firebase Admin com a chave do service account e retorna objetos úteis.
    """
    if not firebase_admin._apps:
        cred = credentials.Certificate(service_account_path)
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