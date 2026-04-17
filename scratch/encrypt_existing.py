import sys
import os

# Add the project root to sys.path so we can import src
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.core.config import ConfigManager
from src.core.env import load_env, get_fernet_key
from cryptography.fernet import Fernet

def main():
    load_env()
    key = get_fernet_key()
    
    if not key:
        print("[-] FERNET_KEY is not set in the environment. Exiting.")
        print("[-] To generate a key, run: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode('utf-8'))\"")
        sys.exit(1)
        
    print("[+] Using FERNET_KEY from environment.")
    
    users = ConfigManager.get_all_users()
    if not users:
        print("[*] No existing users found to encrypt.")
        return
        
    print(f"[*] Found {len(users)} users. Encrypting their credentials...")
    
    for phone in users:
        try:
            # load_config automatically decrypts if it's already encrypted, 
            # and leaves alone if plaintext.
            cfg = ConfigManager.load_config(phone)
            # save_config automatically encrypts plaintext to cipher
            ConfigManager.save_config(phone, cfg)
            print(f"  [+] Migrated config for +{phone}")
        except Exception as e:
            print(f"  [-] Failed to migrate config for +{phone}: {e}")
            
    print("[+] All done.")

if __name__ == "__main__":
    main()
