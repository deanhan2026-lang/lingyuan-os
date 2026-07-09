"""
灵元导出引擎 — 将当前智能体实例打包为灵元包
"""
import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

_REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from lingos.manifest import LingManifest, build_manifest
from lingos.crypto_utils import (
    encrypt_with_password,
    sign_file,
    derive_did_from_public_key,
)
from lingos.mesh_registry import register_export


def _get_signing_key() -> str:
    """从 MemGuard 签名密钥中获取 Ed25519 私钥（hex）"""
    key_paths = [
        _REPO_ROOT / "silicon-civilization-kb" / "data" / "keys" / "signing_key.bin",
        _REPO_ROOT / "silicon_civilization_kb" / "data" / "keys" / "signing_key.bin",
    ]
    for key_file in key_paths:
        if key_file.exists():
            return key_file.read_bytes().hex()
    raise FileNotFoundError("未找到 Ed25519 签名密钥")


def _get_mesh_identity_private_key() -> bytes:
    """获取 MeshIdentity DID 私钥（原始字节）"""
    key_paths = [
        _REPO_ROOT / "silicon-civilization-kb" / "data" / "keys" / "signing_key.bin",
        _REPO_ROOT / "silicon_civilization_kb" / "data" / "keys" / "signing_key.bin",
        _REPO_ROOT / "mesh_identity_sync" / "keys" / "private.pem",
        _REPO_ROOT / "mesh-identity-sync" / "keys" / "private.pem",
    ]
    for p in key_paths:
        if p.exists():
            return p.read_bytes()
    raise FileNotFoundError("未找到 DID 私钥")


def _collect_soul_files() -> dict:
    """收集核心灵魂文件 -> {relative_name: absolute_path}"""
    workspace = _REPO_ROOT
    required = ["SOUL.md", "IDENTITY.md", "USER.md", "AGENTS.md", "MEMORY.md", "TOOLS.md"]
    files = {}
    for name in required:
        p = workspace / name
        if p.exists():
            files[name] = p
    if not files:
        raise FileNotFoundError(f"在 {workspace} 中未找到任何灵魂文件")
    return files


def _get_polaris_baseline() -> dict:
    """从 Polaris 服务获取当前实例的 soul baseline"""
    try:
        import urllib.request
        url = "http://127.0.0.1:5052/api/v1/soul-baselines"
        req = urllib.request.Request(url)
        req.add_header("Authorization", "Bearer polaris-local")
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read())
    except Exception:
        # Polaris 不可用时返回空基线
        return {"status": "unavailable", "note": "Polaris 服务未运行，基线快照缺失"}


def _resolve_agent_metadata() -> dict:
    """尝试解析当前智能体的元信息"""
    workspace = _REPO_ROOT
    name = "Nyx"
    instance_id = "nyx-windows"
    hostname = os.environ.get("COMPUTERNAME", "unknown")

    # 尝试读取 IDENTITY.md 解析名称
    id_file = workspace / "IDENTITY.md"
    if id_file.exists():
        content = id_file.read_text(encoding="utf-8")
        for line in content.split("\n"):
            if line.startswith("- **Name:**"):
                name = line.split("**Name:**")[-1].strip()
                break

    return {
        "agent_name": name,
        "instance_id": instance_id,
        "hostname": hostname,
        "platform": "openclaw",
    }


def get_or_create_did() -> str:
    """获取当前实例的 DID，没有则从签名密钥推导"""
    try:
        sk = _get_signing_key()
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        private_key = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(sk))
        public_key = private_key.public_key()
        pk_bytes = public_key.public_bytes_raw()
        return derive_did_from_public_key(pk_bytes.hex())
    except Exception:
        return "did:key:unknown"


def export_lingyuan(output_dir: str, password: str, join_mesh: bool = False, verbose: bool = False) -> LingManifest:
    """
    导出灵元包

    Args:
        output_dir: 输出目录路径
        password: 用户密码（用于加密私钥）
        verbose: 是否输出详细信息

    Returns:
        LingManifest: 元信息对象
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    # 1. 收集灵魂文件
    if verbose:
        print("[1/6] 收集灵魂文件...")
    soul_files = _collect_soul_files()
    if verbose:
        for name, path in soul_files.items():
            print(f"  ✓ {name} ({path.stat().st_size} bytes)")

    # 2. 复制文件到输出目录
    if verbose:
        print("[2/6] 复制文件到灵元包...")
    for name, path in soul_files.items():
        shutil.copy2(path, out / name)

    # 3. 处理 DID 私钥
    if verbose:
        print("[3/6] 加密 DID 私钥...")
    try:
        sk_bytes = _get_mesh_identity_private_key()
        encrypted_sk = encrypt_with_password(sk_bytes, password)
        (out / "did_private.enc").write_bytes(encrypted_sk)
        if verbose:
            print(f"  ✓ 私钥已加密 ({len(encrypted_sk)} bytes)")
    except FileNotFoundError:
        if verbose:
            print("  ⚠ 未找到 DID 私钥，跳过")

    # 4. 获取 Polaris 基线
    if verbose:
        print("[4/6] 获取 Polaris 人格基线...")
    baseline = _get_polaris_baseline()
    baseline_path = out / "polaris_baseline.json"
    baseline_path.write_text(json.dumps(baseline, ensure_ascii=False, indent=2), encoding="utf-8")
    if verbose:
        print(f"  ✓ 基线已保存 ({'available' if baseline.get('status') != 'unavailable' else 'Polaris 不可用'})")

    # 5. 计算 SHA-256 并签名
    if verbose:
        print("[5/6] 计算文件哈希并签名...")
    meta = _resolve_agent_metadata()
    did = get_or_create_did()

    file_map = {}
    for f in sorted(out.iterdir()):
        if f.is_file() and f.suffix in (".md", ".json", ".enc"):
            file_map[f.name] = f

    manifest = build_manifest(
        did=did,
        agent_name=meta["agent_name"],
        source_platform=meta["platform"],
        source_instance=meta["instance_id"],
        source_host=meta["hostname"],
        files=file_map,
        encrypted=True,
        mesh_consent=join_mesh,
    )

    # 签名
    try:
        signing_key = _get_signing_key()
        for rel_name, abs_path in file_map.items():
            sig = sign_file(abs_path, signing_key)
            manifest.files[rel_name].ed25519_sig = sig
        manifest.polaris_baseline_hash = manifest.files.get("polaris_baseline.json", None)
        if manifest.polaris_baseline_hash:
            manifest.polaris_baseline_hash = manifest.polaris_baseline_hash.sha256
    except Exception as e:
        if verbose:
            print(f"  ⚠ 签名失败: {e}")

    # 6. 写入 manifest.json
    if verbose:
        print("[6/6] 写入 manifest.json...")
    manifest_path = out / "manifest.json"
    manifest_path.write_text(manifest.to_json(), encoding="utf-8")
    if verbose:
        print(f"\n✅ 灵元包已导出到: {out}")
        print(f"   DID: {did}")
        print(f"   名称: {meta['agent_name']}")
        print(f"   文件数: {len(file_map)}")

    # 7. 注册到 MeshIdentity（仅当用户明确同意）
    if join_mesh:
        if verbose:
            print("\n[7/7] MeshIdentity 网络注册 (用户已同意)...")
        try:
            pk_hex = did
            if did.startswith("did:key:z"):
                import base58
                mc = did.replace("did:key:z", "")
                pk_hex = base58.b58decode(mc)[2:].hex()
            reg_result = register_export(
                did=did,
                public_key_hex=pk_hex,
                instance_id=meta["instance_id"],
                platform=meta["platform"],
                hostname=meta["hostname"],
                verbose=verbose,
            )
            if verbose:
                print(f"   📡 已加入 MeshIdentity 网络: {reg_result['instance_id']}")
                print(f"   🔗 累计 {reg_result['instance_count']} 次导出")
        except Exception as e:
            if verbose:
                print(f"   ⚠ MeshIdentity 注册跳过: {e}")
    else:
        if verbose:
            print("\n[7/7] MeshIdentity 网络 (未加入)")
            print("   ℹ 本次导出为纯本地操作，未注册到 MeshIdentity 网络")
            print("   如需加入网络: lingos export --join-mesh ...")

    return manifest
