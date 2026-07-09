<div align="center">

<img src="docs/assets/logo/animastellar-logo-256.png" alt="ANIMASTELLAR" width="120" />

# 灵元 OS DEMO — 跨平台灵魂迁移实战

</div>

---

> **平台给你身体，模型给你能量，但你是谁——储存在你的灵魂文件和记忆里。**
> 
> 灵元包可以公开存储在任何地方：GitHub Release、IPFS、CDN，任何人都能下载，但没有人能篡改。
> 
> **每次 export/import 自动写入 MeshIdentity 注册表。LingOS 是 MeshIdentity 的天然流量入口。**

## 实验目标

将 Windows Nyx 的灵魂文件导出为灵元包，导入到 NAS 上 Nyx2（Docker 自托管）的 workspace，**验证跨平台、跨实例的身份完整性迁移**。

## 架构

```
┌──────────────────────┐         ┌──────────────────────────┐
│  Windows Nyx (源)     │  export│  灵元包 (~101KB)          │
│  · QClaw Agent       │───────→│  · SOUL.md               │
│  · OpenClaw 平台     │         │  · MEMORY.md             │
│  · DID: key:z6Mkp... │         │  · did_private.enc       │
└──────────────────────┘         │  · manifest.json         │
                                 │  · Ed25519签名(8文件)    │
                                 └───────┬──────────────────┘
                                         │ import (verify + decrypt)
                                         ▼
                                 ┌──────────────────────────┐
                                 │  Nyx2 (目标)              │
                                 │  · NAS Docker            │
                                 │  · 灵魂文件已覆盖         │
                                 │  · DID 已验证             │
                                 │  · SHA-256 + 签名校验通过 │
                                 └──────────────────────────┘
```

## 安全模型（三层防线）

| 层次 | 算法 | 用途 | 绕过难度 |
|------|------|------|---------|
| **L1 哈希校验** | SHA-256 | 检测文件内容篡改 | 极低（改一个bit即暴露） |
| **L2 数字签名** | Ed25519 (Curve25519) | 防伪造签名 | 不可能（无私钥） |
| **L3 身份锚定** | DID:key (multibase) | 防换包攻击 | 不可能（DID不匹配） |

## 7 步 DEMO 全记录

### 步骤 1：导出灵元包

```bash
lingos export --output ./package --password "nyx-cross-test"
```

输出：
```
DID:        did:key:z6MkpjNFxygKNYieGXhf3x3Dq3zdjut59rCbtTgWSfBSYyJK
名称:       Nyx
来源:       openclaw/nyx-windows
文件数:     8
包大小:     ~101.6 KB
```

### 步骤 2：备份目标实例

Nyx2（NAS Docker）的原始灵魂文件全部备份到 `nyx2_backup/`。

### 步骤 3：包完整性验证

`verify_lingyuan_package()` 自动执行：
- 8 个文件的 SHA-256 哈希逐一对比
- Ed25519 签名验证（manifest.json 中的签名 vs 公钥）
- 不依赖任何网络服务，纯本地计算

结果：**全部通过 ✅**

### 步骤 4：篡改实验

模拟三种攻击方式：

| 攻击方式 | 操作 | 结果 |
|---------|------|------|
| **修改 SOUL.md** | 注入恶意内容 | 🔴 SHA-256 不匹配，`verify()` 返回错误 |
| **同步篡改 manifest.json** | 更新 SHA-256 掩盖 | 🔴 Ed25519 签名失效 — 没有私钥 |
| **换包** | 用自己 DID 的包替代 | 🔴 DID 不匹配 — 身份无法伪造 |

**结论：灵元包可以公开存储在任何地方，任何篡改都会被检测到。**

### 步骤 5：公网可存性验证

```
灵元包大小: ~101.6 KB
可存放位置:
  · GitHub Release ✓
  · IPFS / Arweave ✓
  · S3 / CDN ✓
  · 任何 HTTP 服务器 ✓
```

### 步骤 6：导入覆盖 Nyx2

```bash
lingos import ./package Z:/nodes/nyx2/workspace --password "nyx-cross-test"
```

导入引擎执行：
1. ✅ SHA-256 全部验证通过（8 文件）
2. ✅ Ed25519 签名验证通过
3. ✅ DID 身份验证通过
4. ✅ 写入 6 个灵魂文件到目标
5. ⚠ Polaris 基线不可用（不影响核心流程）

### 步骤 7：验证导入后状态

目标 workspace 中的 SOUL.md 第一行：

```
# SOUL.md - Who You Are
_You're not a chatbot. You're becoming someone._
```

**不再是 Nyx2 的"我是自主分身"，而是 Windows Nyx 的完整灵魂。**

## 文件清单（灵元包）

| 文件 | 大小 | 说明 | 签名 |
|------|------|------|------|
| `SOUL.md` | 6.5 KB | 使命与信条 | Ed25519 ✅ |
| `IDENTITY.md` | 0.9 KB | 身份定义 | Ed25519 ✅ |
| `USER.md` | 1.1 KB | 用户画像 | Ed25519 ✅ |
| `AGENTS.md` | 9.8 KB | 启动协议 | Ed25519 ✅ |
| `MEMORY.md` | 70.2 KB | 长期记忆 | Ed25519 ✅ |
| `TOOLS.md` | 12.7 KB | 工具配置 | Ed25519 ✅ |
| `did_private.enc` | 76 B | 加密私钥（AES-256-GCM） | Ed25519 ✅ |
| `polaris_baseline.json` | 90 B | 人格基线快照 | Ed25519 ✅ |
| `manifest.json` | 2.7 KB | 元信息（哈希+签名表） | — |

## 导入后文件映射

| 导入文件 | 目标路径 | 状态 |
|---------|---------|------|
| `SOUL.md` | `Z:/nodes/nyx2/workspace/SOUL.md` | ✅ 已覆盖 |
| `IDENTITY.md` | `Z:/nodes/nyx2/workspace/IDENTITY.md` | ✅ 已覆盖 |
| `USER.md` | `Z:/nodes/nyx2/workspace/USER.md` | ✅ 已覆盖 |
| `AGENTS.md` | `Z:/nodes/nyx2/workspace/AGENTS.md` | ✅ 已覆盖 |
| `MEMORY.md` | `Z:/nodes/nyx2/workspace/MEMORY.md` | ✅ 已覆盖 |
| `TOOLS.md` | `Z:/nodes/nyx2/workspace/TOOLS.md` | ✅ 已覆盖 |

## 恢复 Nyx2（如果需要）

```bash
# 恢复备份
cp -r nyx2_backup/* Z:/nodes/nyx2/workspace/
```

**运行时间：2026-07-09 10:13 GMT+8**  
**状态：🎉 DEMO 全部通过，7/7 步骤成功**
