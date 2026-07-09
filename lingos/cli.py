"""
灵元 OS CLI 工具 — lingos
用法:
  lingos export --output ./my-soul --password "xxx"
  lingos import ./my-soul --target ./new-workspace --password "xxx"
  lingos verify ./my-soul
  lingos version
"""

import argparse
import sys
from pathlib import Path

_SCRIPT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(_SCRIPT_DIR))


def cmd_export(args):
    from lingos.exporter import export_lingyuan
    if args.join_mesh and not args.quiet:
        print("🌐 加入 MeshIdentity 网络（已明确同意协议）")
    export_lingyuan(
        output_dir=args.output,
        password=args.password,
        join_mesh=args.join_mesh,
        verbose=not args.quiet,
    )


def cmd_import(args):
    from lingos.importer import import_lingyuan
    result = import_lingyuan(
        package_dir=args.package,
        target_workspace=args.target,
        password=args.password,
        dry_run=args.dry_run,
        verbose=not args.quiet,
    )
    if not result.success:
        sys.exit(1)


def cmd_verify(args):
    from lingos.importer import verify_lingyuan_package
    result = verify_lingyuan_package(args.package)
    if result.success:
        print(f"✅ 灵元包验证通过")
        print(f"   DID: {result.did[:50]}...")
        print(f"   文件: {len(result.files_copied)} 个完整")
        if result.did_verified:
            print(f"   ✓ 签名验证通过")
    else:
        print(f"❌ 灵元包验证失败")
        for e in result.errors:
            print(f"   - {e}")
        sys.exit(1)


def cmd_version(args):
    from lingos import __version__, __author__
    print(f"灵元 OS (LingOS) v{__version__}")
    print(f"{__author__}")
    print("灵元筑基，星辰有序")


def main():
    parser = argparse.ArgumentParser(
        prog="lingos",
        description="灵元 OS — AI 灵魂导入导出工具",
    )
    sub = parser.add_subparsers(dest="command")

    # export
    p_export = sub.add_parser("export", help="导出灵元包")
    p_export.add_argument("--output", "-o", required=True, help="输出目录")
    p_export.add_argument("--password", "-p", required=True, help="加密密码")
    p_export.add_argument("--join-mesh", action="store_true",
        help="加入 MeshIdentity 网络（导出时注册 DID + 实例信息，详见协议）")
    p_export.add_argument("--quiet", "-q", action="store_true", help="静默模式")

    # import
    p_import = sub.add_parser("import", help="导入灵元包")
    p_import.add_argument("package", help="灵元包路径")
    p_import.add_argument("--target", "-t", required=True, help="目标 workspace 路径")
    p_import.add_argument("--password", "-p", required=True, help="解密密码")
    p_import.add_argument("--dry-run", "-n", action="store_true", help="仅验证不写入")
    p_import.add_argument("--quiet", "-q", action="store_true", help="静默模式")

    # verify
    p_verify = sub.add_parser("verify", help="验证灵元包完整性")
    p_verify.add_argument("package", help="灵元包路径")

    # version
    p_version = sub.add_parser("version", help="显示版本")

    args = parser.parse_args()

    commands = {
        "export": cmd_export,
        "import": cmd_import,
        "verify": cmd_verify,
        "version": cmd_version,
    }

    if args.command in commands:
        commands[args.command](args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
