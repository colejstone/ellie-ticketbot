"""
Session file encryption and decryption functionality.
"""

import os
import stat
import base64
import logging
import time
import subprocess
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

logger = logging.getLogger(__name__)


class SessionEncryption:
    """Handle session file encryption and decryption"""
    
    def __init__(self, api_id: str, api_hash: str):
        # Always auto-generate encryption key from API credentials (more secure)
        self.encryption_key = f"{api_id}-{api_hash}-session-encryption"
        self.fernet = None
        self._init_encryption()
    
    def _init_encryption(self):
        """Initialize encryption with key derivation"""
        # Derive encryption key using PBKDF2 with API credentials
        salt = b'ellie_ticketbot_salt_2024'  # Static salt is OK for this use case
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(self.encryption_key.encode()))
        self.fernet = Fernet(key)
    
    def _remove_extended_attributes(self, file_path: str):
        """Remove extended attributes that might cause permission issues (especially in Dropbox)"""
        try:
            # Remove Dropbox-specific extended attributes that can cause read-only issues
            dropbox_attrs = ['com.dropbox.attrs', 'com.dropbox.internal', 'com.apple.provenance']
            for attr in dropbox_attrs:
                try:
                    subprocess.run(['xattr', '-d', attr, file_path], 
                                 capture_output=True, check=False)
                except Exception:
                    pass  # Ignore errors if attribute doesn't exist
            
            # Also try to remove all extended attributes
            try:
                subprocess.run(['xattr', '-c', file_path], 
                             capture_output=True, check=False)
            except Exception:
                pass  # Ignore errors
                
        except Exception as e:
            logger.debug(f"Could not remove extended attributes from {file_path}: {e}")
    
    def _ensure_writable_with_retry(self, file_path: str, max_retries: int = 3) -> bool:
        """Ensure file is writable with retry logic for Dropbox-related issues"""
        for attempt in range(max_retries):
            try:
                # Remove extended attributes that might cause issues
                self._remove_extended_attributes(file_path)
                
                # Set proper permissions
                os.chmod(file_path, 0o600)
                
                # Test write access
                with open(file_path, 'r+b') as test_file:
                    test_file.seek(0, 2)  # Seek to end
                    pos = test_file.tell()
                    test_file.seek(pos)  # Stay at end, don't modify
                
                logger.info(f"✅ File write access verified: {file_path}")
                return True
                
            except Exception as e:
                logger.warning(f"⚠️ Attempt {attempt + 1}/{max_retries} - File write test failed: {e}")
                
                if attempt < max_retries - 1:
                    # Wait briefly for any sync operations to complete
                    time.sleep(0.5)
                    
                    # Try more aggressive permission fixing
                    try:
                        os.chmod(file_path, 0o666)  # More permissive temporarily
                        time.sleep(0.1)
                        os.chmod(file_path, 0o600)  # Back to secure
                    except Exception:
                        pass
                        
                    # Try to remove file locks or other issues
                    try:
                        # Force remove any file locks (macOS/Dropbox specific)
                        subprocess.run(['lsof', file_path], capture_output=True, check=False)
                    except Exception:
                        pass
                else:
                    logger.error(f"❌ Failed to ensure write access after {max_retries} attempts: {file_path}")
                    return False
        
        return False
    
    def encrypt_file(self, file_path: str) -> bool:
        """Encrypt a session file"""
        try:
            if not os.path.exists(file_path):
                return False
            
            # Ensure file is writable before encryption
            if not self._ensure_writable_with_retry(file_path):
                logger.error(f"Cannot encrypt file - not writable: {file_path}")
                return False
            
            # Read the original file
            with open(file_path, 'rb') as f:
                original_data = f.read()
            
            # Encrypt the data
            encrypted_data = self.fernet.encrypt(original_data)
            
            # Write encrypted data to .enc file
            encrypted_path = f"{file_path}.enc"
            with open(encrypted_path, 'wb') as f:
                f.write(encrypted_data)
            
            # Set secure permissions on encrypted file
            os.chmod(encrypted_path, stat.S_IRUSR | stat.S_IWUSR)  # 600 permissions
            
            # Remove original file
            os.remove(file_path)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to encrypt session file {file_path}: {e}")
            return False
    
    def decrypt_file(self, encrypted_path: str) -> str:
        """Decrypt a session file and return the decrypted file path"""
        try:
            if not os.path.exists(encrypted_path):
                return None
            
            # Read encrypted data
            with open(encrypted_path, 'rb') as f:
                encrypted_data = f.read()
            
            # Decrypt the data
            decrypted_data = self.fernet.decrypt(encrypted_data)
            
            # Get original file path
            original_path = encrypted_path.replace('.enc', '')
            
            # Write decrypted data to original location
            with open(original_path, 'wb') as f:
                f.write(decrypted_data)
            
            # Ensure the decrypted file is writable with retry logic
            if not self._ensure_writable_with_retry(original_path):
                logger.error(f"Failed to ensure write access for decrypted file: {original_path}")
                return None
            
            return original_path
            
        except Exception as e:
            logger.error(f"Failed to decrypt session file {encrypted_path}: {e}")
            return None
    
    def cleanup_decrypted_file(self, file_path: str):
        """Remove decrypted session file for security"""
        try:
            if os.path.exists(file_path):
                # Remove extended attributes before deletion
                self._remove_extended_attributes(file_path)
                # Ensure we can delete the file
                os.chmod(file_path, 0o600)
                os.remove(file_path)
        except Exception as e:
            logger.error(f"Failed to cleanup decrypted file {file_path}: {e}") 