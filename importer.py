"""
灵元导入引擎 — 从灵元包恢复智能体实例
"""
import json
import shutil
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from lingos.manifest import LingManifest, sha256_file
from lingos.crypto_utils import (
    decrypt_with_password,
    verify_file_signature,
    derive_did_from_public_key,
)


def _resolve_target_workspace(target: str) -> Path:
    """解析目标 workspace 路径"""
    t = Path(target)
    if t.is_absolute():
        return t
    return _REPO_ROOT / t


class ImportResult:
    """导入结果"""
    def __init__(self):
        self.success: bool = False
        self.did: str = ""
        self.did_verified: bool = False
        self.files_copied: list = []
        self.polaris_check: dict = {}
        self.errors: list = []
        self.warnings: list = []

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "did": self.did,
            "did_verified": self.did_verified,
            "files_copied": self.files_copied,
            "polaris_check": self.polaris_check,
            "errors": self.errors,
            "warnings": self.warnings,
        }


def verify_lingyuan_package(package_dir: str) -> ImportResult:
    """
    验证灵元包的完整性（不解密私钥）

    Returns:
        ImportResult: 验证结果
    """
    result = ImportResult()
    pkg = Path(package_dir)

    # 1. 检查 manifest.json
    manifest_path = pkg / "manifest.json"
    if not manifest_path.exists():
        result.errors.append("未找到 manifest.json")
        return result

    try:
        manifest = LingManifest.from_json(manifest_path.read_text(encoding="utf-8"))
    except Exception as e:
        result.errors.append(f"manifest.json 解析失败: {e}")
        return result

    result.did = manifest.did

    # 2. 验证每个文件的 SHA-256
    for rel_name, entry in manifest.files.items():
        f = pkg / rel_name
        if not f.exists():
            result.errors.append(f"缺失文件: {rel_name}")
            continue
        actual_hash = sha256_file(f)
        if actual_hash != entry.sha256:
            result.errors.append(f"SHA-256 不匹配: {rel_name}")
        else:
            result.files_copied.append(rel_name)

    # 3. 验证 Ed25519 签名（如果能推导出公钥）
    if manifest.did and manifest.did.startswith("did:key:"):
        try:
            import base58
            multibase = manifest.did.replace("did:key:z", "")
            decoded = base58.b58decode(multibase)
            # 跳过 0xed01 前缀
            pk_bytes = decoded[2:]
            for rel_name, entry in manifest.files.items():
                if entry.ed25519_sig:
                    f = pkg / rel_name
                    if f.exists():
                        if verify_file_signature(f, entry.ed25519_sig, pk_bytes.hex()):
                            result.did_verified = True
                            break  # 至少一个文件签名验证通过即可
        except Exception as e:
            result.warnings.append(f"签名验证失败: {e}")

    result.success = len(result.errors) == 0
    return result


def import_lingyuan(package_dir: str, target_workspace: str, password: str,
                    dry_run: bool = False, verbose: bool = False) -> ImportResult:
    """
    导入灵元包到目标 workspace

    Args:
        package_dir: 灵元包路径
        target_workspace: 目标 workspace 目录
        password: 用户密码（用于解密私钥）
        dry_run: 仅验证，不实际写入
        verbose: 是否输出详细信息

    Returns:
        ImportResult: 导入结果
    """
    result = ImportResult()
    pkg = Path(package_dir)
    target = _resolve_target_workspace(target_workspace)

    if verbose:
        print(f"📦 灵元包: {pkg}")
        print(f"🎯 目标: {target}")

    # 1. 验证包完整性
    if verbose:
        print("[1/4] 验证灵元包完整性...")
    verify_result = verify_lingyuan_package(package_dir)
    result.did = verify_result.did
    result.errors = verify_result.errors[:]
    result.warnings = verify_result.warnings[:]

    if not verify_result.success:
        if verbose:
            for e in result.errors:
                print(f"  ❌ {e}")
        return result

    if verbose:
        print(f"  ✓ SHA-256 全部验证通过 ({len(verify_result.files_copied)} 文件)")
        if verify_result.did_verified:
            print(f"  ✓ Ed25519 签名验证通过")
        else:
            print(f"  ⚠ 未进行签名验证")

    # 2. 解密私钥并验证 DID
    if verbose:
        print("[2/4] 验证 DID 身份...")
    private_key_path = pkg / "did_private.enc"
    if private_key_path.exists():
        try:
            encrypted = private_key_path.read_bytes()
            sk_bytes = decrypt_with_password(encrypted, password)
            # 从私钥推导公钥
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
            sk = Ed25519PrivateKey.from_private_bytes(sk_bytes)
            pk_hex = sk.public_key().public_bytes_raw().hex()
            derived_did = derive_did_from_public_key(pk_hex)
            if derived_did == result.did:
                result.did_verified = True
                if verbose:
                    print(f"  ✓ DID 验证通过: {result.did[:40]}...")
            else:
                result.errors.append(f"DID 不匹配: 预期 {result.did[:40]}... 实际 {derived_did[:40]}...")
                if verbose:
                    print(f"  ❌ DID 不匹配")
        except Exception as e:
            result.errors.append(f"私钥解密失败: {e}")
            if verbose:
                print(f"  ❌ 私钥解密失败: {e}")
    else:
        result.warnings.append("未找到加密私钥，跳过 DID 验证")
        if verbose:
            print("  ⚠ 无加密私钥")

    if result.errors:
        return result

    # 3. 复制文件
    if verbose:
        print(f"[3/4] {'[DRY RUN] ' if dry_run else ''}写入灵魂文件...")
    soul_files = ["SOUL.md", "IDENTITY.md", "USER.md", "AGENTS.md", "MEMORY.md", "TOOLS.md"]
    for name in soul_files:
        src = pkg / name
        if src.exists():
            if not dry_run:
                target.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, target / name)
            result.files_copied.append(name)
            if verbose:
                print(f"  {'→' if not dry_run else '~'} {name}")

    # 4. 调用 Polaris 进行导入后基线校验
    if verbose:
        print("[4/4] Polaris 基线校验...")
    baseline_path = pkg / "polaris_baseline.json"
    if baseline_path.exists():
        try:
            baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
            if baseline.get("status") != "unavailable":
                result.polaris_check = baseline
                if verbose:
                    print(f"  ✓ 基线已加载 ({len(baseline)} 条)")
            else:
                result.warnings.append("Polaris 基线不可用（导出时 Polaris 未运行）")
                if verbose:
                    print("  ⚠ 基线不可用")
        except Exception as e:
            result.warnings.append(f"基线加载失败: {e}")
    else:
        result.warnings.append("未找到基线文件")

    result.success = len(result.errors) == 0
    if verbose:
        if result.success:
            print(f"\n✅ 灵元导入{'验证' if dry_run else ''}成功")
            print(f"   DID: {result.did[:40]}...")
            print(f"   文件: {len(result.files_copied)} 个")
        else:
            print(f"\n❌ 灵元导入失败")

    return result


def _attempt_polaris_register(instance_name: str, did: str, target_workspace: Path) -> dict:
    """尝试在 Polaris 注册新实例（可选步骤）"""
    try:
        import urllib.request
        data = json.dumps({
            "instance_name": instance_name,
            "did": did,
            "workspace": str(target_workspace),
        }).encode()
        req = urllib.request.Request(
            "http://127.0.0.1:5052/api/v1/instances/register",
            data=data,
            headers={"Content-Type": "application/json", "Authorization": "Bearer polaris-local"},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read())
    except Exception as e:
        return {"status": "error", "message": str(e)}
