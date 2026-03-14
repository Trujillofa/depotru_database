import importlib
import logging
import xml.etree.ElementTree as ET
from collections.abc import Callable
from typing import Any, Optional

from ..config import Config

logger = logging.getLogger(__name__)

_navicat_crypto_ctor: Optional[Callable[[], Any]]
try:
    _navicat_module = importlib.import_module("NavicatCipher")
    _navicat_crypto_ctor = getattr(_navicat_module, "Navicat12Crypto")
except Exception:
    _navicat_crypto_ctor = None

_aes_module: Optional[Any]
_unpad: Optional[Callable[..., Any]]
try:
    _aes_module = importlib.import_module("Crypto.Cipher").AES
    _unpad = importlib.import_module("Crypto.Util.Padding").unpad
except Exception:
    _aes_module = None
    _unpad = None


def decrypt_navicat_password(encrypted_password: str) -> str:
    if _navicat_crypto_ctor is not None:
        try:
            crypto = _navicat_crypto_ctor()
            decrypted = crypto.DecryptStringForNCX(encrypted_password)
            return decrypted
        except Exception as exc:
            logger.warning(f"NavicatCipher decryption failed: {exc}")

    if _aes_module is not None and _unpad is not None:
        try:
            key = b"libcckeylibcckey"
            iv = b"libcciv libcciv "
            encrypted_bytes = bytes.fromhex(encrypted_password)
            cipher = _aes_module.new(key, _aes_module.MODE_CBC, iv)
            decrypted = _unpad(cipher.decrypt(encrypted_bytes), _aes_module.block_size)
            return decrypted.decode("utf-8")
        except Exception as exc:
            logger.warning(f"AES decryption failed: {exc}")

    raise ImportError("No decryption method available")


def load_connections(file_path: str) -> list[dict[str, Any]]:
    try:
        tree = ET.parse(file_path)
        root = tree.getroot()
        connections: list[dict[str, Any]] = []

        for conn in root.findall("Connection"):
            host = conn.get("Host")
            user = conn.get("UserName")
            encrypted_password = conn.get("Password")

            if not all([host, user, encrypted_password]):
                continue
            assert encrypted_password is not None

            try:
                password = decrypt_navicat_password(encrypted_password)
            except Exception as exc:
                logger.error(f"Failed to decrypt password: {exc}")
                continue

            port = conn.get("Port", "1433")
            database = conn.get("Database", "master")

            connections.append(
                {
                    "Host": host,
                    "Port": int(port),
                    "UserName": user,
                    "Password": password,
                    "Database": database,
                }
            )

        return connections
    except Exception as exc:
        logger.error(f"Error loading connections: {exc}")
        return []


def resolve_connection_details(ncx_file: Optional[str]) -> dict[str, Any]:
    if Config.has_direct_db_config():
        logger.info("Using direct database configuration from environment")
        return {
            "Host": Config.DB_HOST,
            "Port": Config.DB_PORT,
            "UserName": Config.DB_USER,
            "Password": Config.DB_PASSWORD,
            "Database": Config.DB_NAME,
        }

    ncx_path = ncx_file if ncx_file else Config.NCX_FILE_PATH
    logger.info(f"Loading database configuration from NCX file: {ncx_path}")
    connections = load_connections(ncx_path)
    if not connections:
        raise ValueError(f"No valid connections found in {ncx_path}")
    return connections[0]
