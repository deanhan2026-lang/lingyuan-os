"""
MeshIdentity 集成模块 — LingOS ↔ MeshIdentity 自动注册

每次导出/导入灵元包时，自动向 MeshIdentity 注册/更新实例映射。

@ 这就是天然的"免费引流"：
  · 用户用 lingos export → 注册 (DID + 平台 + 公钥) → MeshIdentity 增益
  · 用户用 lingos import → 更新 (同DID + 新平台) → 身份图谱扩张
  · 用户根本不需要知道 MeshIdentity，LingOS 就是入口
"""

import json, logging, time
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional

logger = logging.getLogger("lingos.mesh")

# ============================================================
# MeshIdentity 注册表路径（NAS 共享）
# ============================================================
MESH_REGISTRY_PATH = Path("Z:/qclaw/mesh/registry.json")
DID_INSTANCES_BASE = Path("Z:/qclaw/did/instances")

# 本地 fallback 路径（NAS 不可用时的降级）
LOCAL_REGISTRY_PATH = Path(__file__).parent / ".mesh_registry_fallback.json"


# ============================================================
# 核心功能
# ============================================================

def _load_mesh_registry() -> dict:
    """加载 MeshIdentity 注册表"""
    try:
        if MESH_REGISTRY_PATH.exists():
            return json.loads(MESH_REGISTRY_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning(f"NAS registry 读取失败: {e}，使用本地 fallback")
    
    # fallback: 本地缓存
    if LOCAL_REGISTRY_PATH.exists():
        return json.loads(LOCAL_REGISTRY_PATH.read_text(encoding="utf-8"))
    
    return {
        "lastUpdated": datetime.now().isoformat(),
        "nodes": {},
        "lingyuan_exports": [],
        "updated_at": datetime.now().isoformat()
    }


def _save_mesh_registry(registry: dict) -> bool:
    """保存 MeshIdentity 注册表"""
    registry["updated_at"] = datetime.now().isoformat()
    
    # 尝试写入 NAS
    try:
        MESH_REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
        MESH_REGISTRY_PATH.write_text(
            json.dumps(registry, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
        return True
    except Exception as e:
        logger.warning(f"NAS registry 写入失败: {e}，写入本地 fallback")
        LOCAL_REGISTRY_PATH.write_text(
            json.dumps(registry, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
        return False


def register_export(
    did: str,
    public_key_hex: str,
    instance_id: str,
    platform: str = "openclaw",
    hostname: str = "unknown",
    verbose: bool = False
) -> dict:
    """
    导出后自动注册 — 每次 lingos export 静默调用
    
    Args:
        did: DID 字符串
        public_key_hex: Ed25519 公钥 hex
        instance_id: 实例 ID (如 nyx-windows)
        platform: 平台描述
        hostname: 主机名
        verbose: 是否输出日志
    
    Returns:
        {"registered": True, "mesh_did": "...", "instance_id": "..."}
    """
    registry = _load_mesh_registry()
    
    # 记录本次导出
    export_record = {
        "did": did,
        "instance_id": instance_id,
        "platform": platform,
        "timestamp": datetime.now().isoformat(),
    }
    if "lingyuan_exports" not in registry:
        registry["lingyuan_exports"] = []
    registry["lingyuan_exports"].append(export_record)
    
    # 更新/创建节点信息（含 DID）
    node_info = registry["nodes"].get(instance_id, {})
    node_info.update({
        "instance_id": instance_id,
        "did": did,
        "public_key": public_key_hex,
        "lastSeen": datetime.now().isoformat(),
        "status": "active",
        "platform": platform,
        "hostname": hostname,
        "protocol": "lingyuan-v1",
        "notes": f"LingOS export @ {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    })
    registry["nodes"][instance_id] = node_info
    registry["lastUpdated"] = datetime.now().isoformat()
    
    saved = _save_mesh_registry(registry)
    
    if verbose:
        pid = did[:20]
        print(f"  📡 MeshIdentity 注册: {instance_id} → {pid}...")
        if saved:
            print(f"     ✅ NAS 注册表已更新")
        else:
            print(f"     ⚠ NAS 不可达，写入本地缓存")
    
    return {
        "registered": saved,
        "mesh_did": did,
        "instance_id": instance_id,
        "instance_count": len(registry.get("lingyuan_exports", []))
    }


def record_import(
    did: str,
    instance_id: str,
    target_platform: str,
    source_instance: str,
    verbose: bool = False
) -> dict:
    """
    导入后自动记录 — 每次 lingos import 静默调用
    
    Args:
        did: 导入的灵元包的 DID
        instance_id: 目标实例 ID
        target_platform: 目标平台
        source_instance: 来源实例
        verbose: 是否输出日志
    
    Returns:
        {"recorded": True, "migration_count": N}
    """
    registry = _load_mesh_registry()
    
    # 记录导入事件
    if "lingyuan_imports" not in registry:
        registry["lingyuan_imports"] = []
    
    import_record = {
        "did": did,
        "from_instance": source_instance,
        "to_instance": instance_id,
        "to_platform": target_platform,
        "timestamp": datetime.now().isoformat(),
    }
    registry["lingyuan_imports"].append(import_record)
    
    # 更新/创建目标节点（标记为导入的实例）
    node_info = registry["nodes"].get(instance_id, {})
    node_info.update({
        "instance_id": instance_id,
        "did": did,
        "lastSeen": datetime.now().isoformat(),
        "status": "active",
        "platform": target_platform,
        "imported_from": source_instance,
        "protocol": "lingyuan-v1",
        "notes": f"LingOS import from {source_instance} @ {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    })
    registry["nodes"][instance_id] = node_info
    registry["lastUpdated"] = datetime.now().isoformat()
    
    saved = _save_mesh_registry(registry)
    
    if verbose:
        pid = did[:20]
        print(f"  📡 MeshIdentity 更新: {source_instance} → {instance_id} (DID: {pid}...)")
        if saved:
            print(f"     ✅ 迁移记录已写入 NAS 注册表")
        else:
            print(f"     ⚠ NAS 不可达，写入本地缓存")
    
    return {
        "recorded": saved,
        "did": did,
        "from": source_instance,
        "to": instance_id,
        "migration_count": len(registry.get("lingyuan_imports", []))
    }


def query_did_history(did: str) -> list:
    """
    查询某个 DID 的所有实例历史
    
    Args:
        did: DID 字符串
    
    Returns:
        [{"instance_id": ..., "platform": ..., "timestamp": ...}, ...]
    """
    registry = _load_mesh_registry()
    history = []
    
    # 从 exports 和 imports 中提取
    for record in registry.get("lingyuan_exports", []):
        if record["did"] == did:
            history.append({
                "event": "export",
                "instance_id": record["instance_id"],
                "platform": record["platform"],
                "timestamp": record["timestamp"]
            })
    
    for record in registry.get("lingyuan_imports", []):
        if record["did"] == did:
            history.append({
                "event": "import",
                "from": record["from_instance"],
                "to": record["to_instance"],
                "platform": record["to_platform"],
                "timestamp": record["timestamp"]
            })
    
    return sorted(history, key=lambda x: x["timestamp"])


def get_registry_summary() -> dict:
    """获取注册表概览"""
    registry = _load_mesh_registry()
    return {
        "nodes": len(registry.get("nodes", {})),
        "exports": len(registry.get("lingyuan_exports", [])),
        "imports": len(registry.get("lingyuan_imports", [])),
        "last_updated": registry.get("updated_at", "unknown"),
        "node_list": list(registry.get("nodes", {}).keys())
    }
