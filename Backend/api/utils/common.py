from cryptography.fernet import Fernet
from pymongo import MongoClient
from fastapi import HTTPException
from api.core.config import config

# Generate a secret key for encryption (keep it secure and consistent across your app)
# Use `Fernet.generate_key()` once to generate the key, and store it securely.
SECRET_KEY = config.SECRET_KEY  # Replace with your actual secret key
cipher = Fernet(SECRET_KEY)


def encrypt_data(data: str) -> str:
    """
    Encrypts a given string using Fernet symmetric encryption.
    :param data: The string to encrypt
    :return: Encrypted string
    """
    if not data:
        return ""
    return cipher.encrypt(data.encode()).decode()


def decrypt_data(data: str) -> str:
    """
    Decrypts a given string encrypted with Fernet symmetric encryption.
    :param data: The encrypted string to decrypt
    :return: Decrypted string
    """
    if not data:
        return ""
    return cipher.decrypt(data.encode()).decode()
