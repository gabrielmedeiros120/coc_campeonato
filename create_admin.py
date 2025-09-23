import firebase_init
from firebase_admin import firestore
import hashlib
from datetime import datetime

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode('utf-8')).hexdigest()

def create_admin_user(username: str, password: str):
    """
    Cria um usuário admin no Firestore
    """
    try:
        fb = firebase_init.init_firebase()
        db = fb['db']
        
        # Verificar se já existe admin
        usuarios_ref = db.collection('usuarios')
        query = usuarios_ref.where('is_admin', '==', True).limit(1)
        existing_admins = query.get()
        
        if len(existing_admins) > 0:
            print("⚠️  Já existe um administrador cadastrado no sistema.")
            return False
        
        # Criar novo admin
        user_data = {
            'username': username,
            'passhash': hash_password(password),
            'is_admin': True,
            'criado_em': datetime.utcnow().isoformat()
        }
        
        usuarios_ref.document(username).set(user_data)
        print(f"✅ Admin '{username}' criado com sucesso!")
        return True
        
    except Exception as e:
        print(f"❌ Erro ao criar admin: {e}")
        return False

if __name__ == "__main__":
    print("=== CRIADOR DE USUÁRIO ADMIN ===")
    username = input("Nome de usuário para admin: ").strip()
    password = input("Senha: ").strip()
    
    if not username or not password:
        print("❌ Usuário e senha não podem estar vazios")
    else:
        create_admin_user(username, password)