import os
from pathlib import Path
from tempfile import NamedTemporaryFile

from cryptography.fernet import Fernet

from app.core.config import settings


class MasterKeyError(ValueError):
    pass


class MasterKeyStore:
    """Loads and persists the Fernet key outside the application database."""

    def __init__(self, path: str | Path | None = None):
        self.path = Path(path or settings.master_key_path)
        self._fernet: Fernet | None = None
        self._key: bytes | None = None

    @property
    def is_initialized(self) -> bool:
        return self._fernet is not None

    def load_existing(self) -> bool:
        if self._fernet is not None:
            return True

        if self.path.exists():
            persisted_key = self.path.read_bytes().strip()
            if settings.encryption_key and settings.encryption_key.encode() != persisted_key:
                raise MasterKeyError(
                    "Configured ENCRYPTION_KEY does not match the persisted master key"
                )
            self._set_key(persisted_key)
            return True

        if settings.encryption_key:
            raw_key = settings.encryption_key.encode()
            self._set_key(raw_key)
            try:
                self._persist(raw_key)
            except Exception:
                self._fernet = None
                self._key = None
                raise
            return True

        return False

    def initialize(self, custom_key: str | None = None) -> None:
        if self.load_existing():
            if custom_key and custom_key.encode() != self._key:
                raise MasterKeyError(
                    "Encryption is already initialized; changing the key requires a rotation workflow"
                )
            return

        raw_key = custom_key.encode() if custom_key else Fernet.generate_key()
        self._set_key(raw_key)
        try:
            self._persist(raw_key)
        except Exception:
            self._fernet = None
            self._key = None
            raise

    @staticmethod
    def validate_key(custom_key: str) -> None:
        try:
            Fernet(custom_key.encode())
        except (TypeError, ValueError) as exc:
            raise MasterKeyError("Encryption key must be a valid Fernet key") from exc

    def encrypt(self, plaintext: str) -> str:
        if not self.load_existing():
            raise MasterKeyError("Encryption is not initialized")
        return self._fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        if not self.load_existing():
            raise MasterKeyError("Encryption is not initialized")
        return self._fernet.decrypt(ciphertext.encode()).decode()

    def _set_key(self, raw_key: bytes) -> None:
        try:
            self._fernet = Fernet(raw_key)
        except (TypeError, ValueError) as exc:
            raise MasterKeyError("Encryption key must be a valid Fernet key") from exc
        self._key = raw_key

    def _persist(self, raw_key: bytes) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary_name: str | None = None
        try:
            with NamedTemporaryFile(
                mode="wb", dir=self.path.parent, prefix=".master-key-", delete=False
            ) as temporary_file:
                temporary_name = temporary_file.name
                temporary_file.write(raw_key)
                temporary_file.flush()
                os.fsync(temporary_file.fileno())
            os.chmod(temporary_name, 0o600)
            os.replace(temporary_name, self.path)
        finally:
            if temporary_name and os.path.exists(temporary_name):
                os.unlink(temporary_name)


master_key_store = MasterKeyStore()
