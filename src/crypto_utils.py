from cryptography.fernet import Fernet
from pathlib import Path

KEY_PATH = Path(__file__).parent / "key.key"

def get_key():
    """Cria ou lê a chave de criptografia local."""
    if not KEY_PATH.exists():
        key = Fernet.generate_key()
        KEY_PATH.write_bytes(key)
    return KEY_PATH.read_bytes()

def encrypt_text(text):
    """Criptografa um texto usando Fernet."""
    return Fernet(get_key()).encrypt(text.encode()).decode()

def decrypt_text(token):
    """Descriptografa o texto criptografado (ou retorna texto original se falhar)."""
    try:
        return Fernet(get_key()).decrypt(token.encode()).decode()
    except Exception:
        return token
