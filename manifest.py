"""
灵元包 manifest 格式定义与序列化

灵元包目录结构：
  SOUL.md            # 灵魂使命文件
  MEMORY.md          # 长期记忆文件
  manifest.json      # 元信息（DID、版本、签名等）
  polaris_baseline.json  # 人格基线快照
  did_private.enc    # 加密的 DID 私钥（AES-256-GCM，用户密码）
"""

import json
import hashlib
import time
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional

MANIFEST_VERSION = "1.0"


@dataclass
class FileEntry:
    """灵元包中单个文件的元信息"""
    path: str             # 相对路径，如 "SOUL.md"
    sha256: str           # SHA-256 哈希
    size: int             # 文件大小（字节）
    ed25519_sig: str = "" # Ed25519 签名（base64）


@dataclass
class LingManifest:
    """灵元包元信息"""
    version: str = MANIFEST_VERSION
    did: str = ""                           # 智能体 DID
    agent_name: str = ""                    # 智能体名称
    created_at: str = ""                    # ISO 时间戳
    source_platform: str = "openclaw"       # 来源平台
    source_instance: str = ""               # 来源实例 ID
    source_host: str = ""                   # 来源主机名
    files: Dict[str, FileEntry] = field(default_factory=dict)
    polaris_baseline_hash: str = ""         # Polaris 基线快照 SHA-256
    human_readable: bool = True             # 是否人类可读（MEMORY.md 等）
    encrypted: bool = True                  # 私钥是否加密

    def to_dict(self) -> dict:
        d = asdict(self)
        d["files"] = {k: asdict(v) for k, v in self.files.items()}
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    @classmethod
    def from_dict(cls, data: dict) -> "LingManifest":
        files = {}
        for k, v in data.get("files", {}).items():
            files[k] = FileEntry(**v)
        data_copy = {k: v for k, v in data.items() if k != "files"}
        m = cls(**data_copy)
        m.files = files
        return m

    @classmethod
    def from_json(cls, text: str) -> "LingManifest":
        return cls.from_dict(json.loads(text))


def sha256_file(path: Path) -> str:
    """计算文件的 SHA-256 哈希"""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def build_manifest(
    did: str,
    agent_name: str,
    source_platform: str,
    source_instance: str,
    source_host: str,
    files: Dict[str, Path],  # {relative_name: absolute_path}
    encrypted: bool = True,
) -> LingManifest:
    """从文件列表构建 manifest"""
    m = LingManifest(
        did=did,
        agent_name=agent_name,
        created_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        source_platform=source_platform,
        source_instance=source_instance,
        source_host=source_host,
        encrypted=encrypted,
    )
    for rel_name, abs_path in files.items():
        m.files[rel_name] = FileEntry(
            path=rel_name,
            sha256=sha256_file(abs_path),
            size=abs_path.stat().st_size,
        )
    return m
