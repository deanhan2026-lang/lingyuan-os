"""
灵元包加密工具 — 复用 MemGuard 的 AES-256-GCM + Ed25519 签名

原则：不重复造轮子，直接调用 memguard 模块
"""

import os
import sys
import base64
import hashlib
from pathlib import Path

# 添加 silicon-civilization-kb 到 sys.path（双重路径兼容）
_REPO_ROOT = Path(__file__).parent.parent
_KB_PATHS = [
    _REPO_ROOT / "silicon-civilization-kb",
    _REPO_ROOT / "silicon_civilization_kb",
]
for _p in _KB_PATHS:
    if _p.exists() and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))


def encrypt_with_password(plaintext: bytes, password: str) -> bytes:
    """
    用用户密码加密数据（AES-256-GCM + PBKDF2）
    输出格式: salt(16) + nonce(12) + ciphertext + tag(16)
    """
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives import hashes
    import secrets

    salt = secrets.token_bytes(16)
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=600000,
    )
    key = kdf.derive(password.encode("utf-8"))

    aesgcm = AESGCM(key)
    nonce = secrets.token_bytes(12)
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)
    return salt + nonce + ciphertext


def decrypt_with_password(encrypted: bytes, password: str) -> bytes:
    """
    用用户密码解密数据
    输入格式: salt(16) + nonce(12) + ciphertext + tag(16)
    """
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives import hashes

    salt = encrypted[:16]
    nonce = encrypted[16:28]
    ciphertext = encrypted[28:]

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=600000,
    )
    key = kdf.derive(password.encode("utf-8"))
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(nonce, ciphertext, None)


def sign_file(file_path: Path, signing_key_hex: str) -> str:
    """用 Ed25519 私钥对文件签名，返回 base64 签名"""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    sk = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(signing_key_hex))
    with open(file_path, "rb") as f:
        content = f.read()
    sig = sk.sign(content)
    return base64.b64encode(sig).decode("ascii")


def verify_file_signature(file_path: Path, signature_b64: str, public_key_hex: str) -> bool:
    """用 Ed25519 公钥验证文件签名"""
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        from cryptography.exceptions import InvalidSignature
        pk = Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_key_hex))
        sig = base64.b64decode(signature_b64)
        with open(file_path, "rb") as f:
            content = f.read()
        pk.verify(sig, content)
        return True
    except InvalidSignature:
        return False
    except Exception:
        return False


def derive_did_from_public_key(public_key_hex: str) -> str:
    """
    从 Ed25519 公钥推导 DID:key
    格式: did:key:z + multibase(base58btc, 0xed01 + raw_public_key)
    """
    import base58
    prefix = bytes([0xed, 0x01])
    raw = bytes.fromhex(public_key_hex)
    multicodec = prefix + raw
    encoded = base58.b58encode(multicodec).decode("ascii")
    return f"did:key:z{encoded}"
