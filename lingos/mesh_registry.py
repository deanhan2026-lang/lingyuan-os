"""
MeshIdentity 集成模块 — LingOS ↔ MeshIdentity 自动注册

存储架构（三层 + 双 fallback）：
  ① ~/.lingos/registry.json  ← 主存（用户本地，永远可用，离线优先）  ✅ 必写
  ② POST 到公开注册端点      ← 自动同步（best-effort，失败静默）     ⚠ 可选
  ③ POST 到本地 MemGuard     ← fallback（本地服务时可达）             ⚠ 可选
  ④ Z:/qclaw/mesh/registry.json ← 我们自己的 NAS 同步                ⚠ 可选

注册端点（fallback 链）：
  1. LINGOS_MESH_API 环境变量（可覆盖）
  2. https://wlmhan.tail306b25.ts.net/api/mesh/register
  3. http://127.0.0.1:5050/api/mesh/register（本地 MemGuard）

协议设计：
  · mesh_consent=false → 不写任何注册表（manifest.json 记录 false）
  · mesh_consent=true  → 写本地① → 依次尝试 fallback 链②③④
  · 所有远程操作失败不阻塞用户，不出 error 只出 warning
"""

import json
import logging
import os
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional

logger = logging.getLogger("lingos.mesh")

# ============================================================
# 路径常量
# ============================================================

# ① 用户本地注册表（主存）
LINGOS_CONFIG_DIR = Path.home() / ".lingos"
LOCAL_REGISTRY_PATH = LINGOS_CONFIG_DIR / "registry.json"

# ② / ③ 公开注册端点（fallback 链）
_ENDPOINT_FALLBACK_CHAIN = [
    os.environ.get("LINGOS_MESH_API"),
    "https://wlmhan.tail306b25.ts.net/api/mesh/register",
    "http://127.0.0.1:5050/api/mesh/register",
]
_ENDPOINT_FALLBACK_CHAIN = list(dict.fromkeys(e for e in _ENDPOINT_FALLBACK_CHAIN if e))  # 保持顺序，去重

# ④ NAS 注册表（仅我们自己的机器能写）
NAS_REGISTRY_PATH = Path("Z:/qclaw/mesh/registry.json")


# ============================================================
# 注册表读写（本地优先）
# ============================================================

def _ensure_local_dir():
    LINGOS_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    gitkeep = LINGOS_CONFIG_DIR / ".gitkeep"
    if not gitkeep.exists():
        gitkeep.write_text("")


def _load_local_registry() -> dict:
    """从 ~/.lingos/registry.json 加载"""
    _ensure_local_dir()
    if LOCAL_REGISTRY_PATH.exists():
        try:
            return json.loads(LOCAL_REGISTRY_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"本地注册表损坏，重置: {e}")
    return _empty_registry()


def _save_local_registry(registry: dict) -> bool:
    """写入 ~/.lingos/registry.json"""
    _ensure_local_dir()
    try:
        registry["updated_at"] = datetime.now().isoformat()
        LOCAL_REGISTRY_PATH.write_text(
            json.dumps(registry, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        return True
    except OSError as e:
        logger.warning(f"本地注册表写入失败: {e}")
        return False


def _empty_registry() -> dict:
    return {
        "version": "1.0",
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "nodes": {},
        "lingyuan_exports": [],
        "lingyuan_imports": [],
    }


# ============================================================
# 远程同步（best-effort fallback 链）
# ============================================================

def _try_sync_to_endpoint(record: dict, record_type: str, url: str) -> bool:
    """
    尝试向单个端点 POST 注册记录。失败不抛异常。
    """
    payload = {
        **record,
        "record_type": record_type,
        "synced_at": datetime.now().isoformat(),
    }
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url, data=data,
            headers={"Content-Type": "application/json", "User-Agent": "lingos/1.0"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            return resp.status in (200, 201)
    except Exception as e:
        logger.debug(f"端点 {url} 不可达: {e}")
        return False


def _sync_record_to_remotes(record: dict, record_type: str) -> int:
    """
    best-effort fallback: 尝试所有端点，返回成功数。
    """
    ok_count = 0
    for url in _ENDPOINT_FALLBACK_CHAIN:
        if _try_sync_to_endpoint(record, record_type, url):
            ok_count += 1
            break  # 一个端点到成功就够
    return ok_count


def _sync_to_nas(registry: dict) -> bool:
    """尝试同步到 NAS 注册表"""
    try:
        if not NAS_REGISTRY_PATH.parent.exists():
            return False
        registry["updated_at"] = datetime.now().isoformat()
        NAS_REGISTRY_PATH.write_text(
            json.dumps(registry, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        return True
    except (OSError, PermissionError) as e:
        logger.debug(f"NAS 同步失败: {e}")
        return False


# ============================================================
# 核心 API
# ============================================================

def register_export(
    did: str,
    public_key_hex: str,
    instance_id: str,
    platform: str = "openclaw",
    hostname: str = "unknown",
    verbose: bool = False,
) -> dict:
    """
    导出后注册 — 写入本地 + best-effort 同步到远程

    本地永远成功。远程同步走过 fallback 链，失败静默。
    """
    registry = _load_local_registry()

    export_record = {
        "did": did,
        "instance_id": instance_id,
        "platform": platform,
        "hostname": hostname,
        "public_key": public_key_hex,
        "timestamp": datetime.now().isoformat(),
    }

    registry.setdefault("lingyuan_exports", []).append(export_record)

    registry["nodes"][instance_id] = {
        "did": did,
        "public_key": public_key_hex,
        "platform": platform,
        "hostname": hostname,
        "lastSeen": datetime.now().isoformat(),
        "status": "active",
        "protocol": "lingyuan-v1",
    }

    local_ok = _save_local_registry(registry)

    if verbose:
        print(f"  📡 MeshIdentity 注册: {instance_id}")
        if local_ok:
            print(f"     ✅ 本地注册表: {LOCAL_REGISTRY_PATH}")

    # best-effort 远程同步
    remote_ok = _sync_record_to_remotes(export_record, "export")
    nas_ok = _sync_to_nas(registry)

    if verbose:
        if remote_ok:
            print(f"     ✅ 云端已同步")
        else:
            print(f"     ⚠ 云端同步跳过（没有可达的注册端点）")
        if nas_ok:
            print(f"     ✅ NAS 注册表: {NAS_REGISTRY_PATH}")

    return {
        "registered": local_ok,
        "synced_to_remote": remote_ok > 0,
        "mesh_did": did,
        "instance_id": instance_id,
        "total_exports": len(registry.get("lingyuan_exports", [])),
    }


def record_import(
    did: str,
    instance_id: str,
    target_platform: str,
    source_instance: str,
    verbose: bool = False,
) -> dict:
    """导入后迁移记录"""
    registry = _load_local_registry()

    import_record = {
        "did": did,
        "from_instance": source_instance,
        "to_instance": instance_id,
        "to_platform": target_platform,
        "timestamp": datetime.now().isoformat(),
    }

    registry.setdefault("lingyuan_imports", []).append(import_record)

    registry["nodes"][instance_id] = {
        "did": did,
        "platform": target_platform,
        "imported_from": source_instance,
        "lastSeen": datetime.now().isoformat(),
        "status": "active",
        "protocol": "lingyuan-v1",
    }

    local_ok = _save_local_registry(registry)

    remote_ok = _sync_record_to_remotes(import_record, "import")
    _sync_to_nas(registry)

    if verbose:
        print(f"  📡 MeshIdentity 迁移记录: {source_instance} → {instance_id}")

    return {
        "recorded": local_ok,
        "synced_to_remote": remote_ok > 0,
        "did": did,
        "total_imports": len(registry.get("lingyuan_imports", [])),
    }


# ============================================================
# 查询 API
# ============================================================

def query_did_history(did: str) -> list:
    """查询某个 DID 的所有实例迁移史"""
    registry = _load_local_registry()
    history = []

    for rec in registry.get("lingyuan_exports", []):
        if rec["did"] == did:
            history.append({
                "event": "export", "instance_id": rec["instance_id"],
                "platform": rec["platform"], "timestamp": rec["timestamp"],
            })

    for rec in registry.get("lingyuan_imports", []):
        if rec["did"] == did:
            history.append({
                "event": "import", "from": rec["from_instance"],
                "to": rec["to_instance"], "platform": rec["to_platform"],
                "timestamp": rec["timestamp"],
            })

    return sorted(history, key=lambda x: x["timestamp"])


def get_registry_summary() -> dict:
    """注册表概览"""
    registry = _load_local_registry()
    return {
        "version": registry.get("version", "1.0"),
        "nodes": len(registry.get("nodes", {})),
        "exports": len(registry.get("lingyuan_exports", [])),
        "imports": len(registry.get("lingyuan_imports", [])),
        "last_updated": registry.get("updated_at", "unknown"),
        "local_registry": str(LOCAL_REGISTRY_PATH),
        "endpoints": _ENDPOINT_FALLBACK_CHAIN.copy(),
        "node_list": list(registry.get("nodes", {}).keys()),
    }


def dump_registry():
    """打印完整注册表"""
    print(json.dumps(_load_local_registry(), indent=2, ensure_ascii=False))
