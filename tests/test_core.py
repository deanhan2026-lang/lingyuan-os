"""
灵元 OS 单元测试
"""
import json
import os
import tempfile
import sys
from pathlib import Path

_SCRIPT_DIR = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_SCRIPT_DIR))


def test_manifest_create():
    """测试 manifest 创建与序列化"""
    from lingos.manifest import LingManifest, FileEntry, build_manifest

    m = LingManifest(
        did="did:key:z6MkhaXgBZDvotDkL5257esdDsFjsB5ivBix3U5xFoVnQ4te",
        agent_name="TestAgent",
        source_platform="openclaw",
        source_instance="test-instance",
        source_host="TEST-PC",
    )
    m.files["SOUL.md"] = FileEntry(path="SOUL.md", sha256="abc123", size=1024)
    m.files["MEMORY.md"] = FileEntry(path="MEMORY.md", sha256="def456", size=2048)

    js = m.to_json()
    m2 = LingManifest.from_json(js)

    assert m2.did == m.did
    assert m2.agent_name == "TestAgent"
    assert m2.source_platform == "openclaw"
    assert len(m2.files) == 2
    assert m2.files["SOUL.md"].sha256 == "abc123"
    assert m2.files["MEMORY.md"].size == 2048
    print("✅ test_manifest_create")


def test_manifest_version():
    """测试 manifest 版本字段"""
    from lingos.manifest import LingManifest, MANIFEST_VERSION
    m = LingManifest()
    assert m.version == MANIFEST_VERSION == "1.0"
    print("✅ test_manifest_version")


def test_sha256_file():
    """测试文件 SHA-256 计算"""
    from lingos.manifest import sha256_file
    import hashlib

    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write("Hello, LingOS!")
        f.flush()
        path = Path(f.name)

    try:
        h = sha256_file(path)
        expected = hashlib.sha256(b"Hello, LingOS!").hexdigest()
        assert h == expected
    finally:
        path.unlink()
    print("✅ test_sha256_file")


def test_crypto_roundtrip():
    """测试加密/解密往返"""
    from lingos.crypto_utils import encrypt_with_password, decrypt_with_password

    original = b"This is my secret DID private key material. 32 bytes!"
    password = "test-password-123"

    encrypted = encrypt_with_password(original, password)
    assert encrypted != original
    assert len(encrypted) > len(original)  # salt + nonce + tag

    decrypted = decrypt_with_password(encrypted, password)
    assert decrypted == original
    print("✅ test_crypto_roundtrip")


def test_crypto_wrong_password():
    """测试错误密码解密失败"""
    from lingos.crypto_utils import encrypt_with_password, decrypt_with_password

    original = b"secret data"
    encrypted = encrypt_with_password(original, "correct-password")

    try:
        decrypt_with_password(encrypted, "wrong-password")
        assert False, "应该抛出异常"
    except Exception:
        pass  # 预期抛异常
    print("✅ test_crypto_wrong_password")


def test_did_derivation():
    """测试 DID 从公钥推导"""
    from lingos.crypto_utils import derive_did_from_public_key
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    sk = Ed25519PrivateKey.generate()
    pk_hex = sk.public_key().public_bytes_raw().hex()

    did = derive_did_from_public_key(pk_hex)
    assert did.startswith("did:key:z")
    assert len(did) > 20
    print(f"✅ test_did_derivation → {did[:50]}...")


def test_sign_and_verify():
    """测试 Ed25519 签名/验证"""
    from lingos.crypto_utils import sign_file, verify_file_signature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    sk = Ed25519PrivateKey.generate()
    sk_hex = sk.private_bytes_raw().hex()
    pk_hex = sk.public_key().public_bytes_raw().hex()

    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write("# Test Soul\nI am an AI agent.")
        f.flush()
        path = Path(f.name)

    try:
        sig = sign_file(path, sk_hex)
        assert len(sig) > 0

        # 正确验证
        assert verify_file_signature(path, sig, pk_hex) is True

        # 错误公钥
        sk2 = Ed25519PrivateKey.generate()
        pk2_hex = sk2.public_key().public_bytes_raw().hex()
        assert verify_file_signature(path, sig, pk2_hex) is False

        # 修改文件后验证失败
        path.write_text("# Modified Soul\nI am someone else.")
        assert verify_file_signature(path, sig, pk_hex) is False
    finally:
        path.unlink()
    print("✅ test_sign_and_verify")


def test_manifest_build():
    """测试从文件列表构建 manifest"""
    from lingos.manifest import build_manifest

    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp)
        (p / "SOUL.md").write_text("# Soul File", encoding="utf-8")
        (p / "MEMORY.md").write_text("# Memory File", encoding="utf-8")

        files = {
            "SOUL.md": p / "SOUL.md",
            "MEMORY.md": p / "MEMORY.md",
        }
        m = build_manifest(
            did="did:key:ztest",
            agent_name="Test",
            source_platform="openclaw",
            source_instance="test",
            source_host="test-pc",
            files=files,
        )
        assert len(m.files) == 2
        assert m.files["SOUL.md"].size == len("# Soul File".encode("utf-8"))
        assert m.files["MEMORY.md"].size == len("# Memory File".encode("utf-8"))
    print("✅ test_manifest_build")


if __name__ == "__main__":
    test_manifest_create()
    test_manifest_version()
    test_sha256_file()
    test_crypto_roundtrip()
    test_crypto_wrong_password()
    test_did_derivation()
    test_sign_and_verify()
    test_manifest_build()
    print("\n🎉 全部测试通过！")
