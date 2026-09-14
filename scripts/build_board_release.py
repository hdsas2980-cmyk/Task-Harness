#!/usr/bin/env python3
"""从单一源码生成独立看板与 ZIP；仅允许仓库内输出，拒绝未知残留文件。"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
BOARD = ROOT / "board"
ASSETS = {name: BOARD / name for name in (
    "serve.py", "sessions.py", "pick_dir.py", "start.bat", "start.ps1", "start.sh",
    "static/index.html", "static/app.js",
)}
ASSETS["使用说明.txt"] = BOARD / "README.md"
ASSETS["scripts/check_task_harness_language.py"] = ROOT / "scripts/check_task_harness_language.py"
ASSETS["harness_db.py"] = ROOT / "harness_db.py"


def build(output):
    output = output.resolve()
    if not output.is_relative_to(ROOT):
        raise ValueError("发布目录必须位于当前技能仓库内")
    bundle = output / "TaskBoard"
    if bundle.is_symlink() or (bundle.exists() and bundle.resolve() != bundle):
        raise ValueError("拒绝写入重定向发布目录")
    expected = {*ASSETS, "manifest.json"}
    if bundle.exists():
        for path in bundle.rglob("*"):
            if path.is_symlink() or not path.resolve().is_relative_to(bundle):
                raise ValueError(f"发布目录含重定向路径：{path}")
            if path.is_file() and path.relative_to(bundle).as_posix() not in expected:
                raise ValueError(f"发布目录存在未知残留，请人工处理后重建：{path}")
    # 先检查全部输入，避免缺失源码时发布一半。
    payload = {name: path.read_bytes() for name, path in ASSETS.items()}
    for name in ("static/index.html", "static/app.js"):
        text = payload[name].decode("utf-8-sig")
        for forbidden in ("board.i18n.json", "parseI18n", "translated(", "name_zh", "desc_zh", "summary_zh", "reason_zh"):
            if forbidden in text:
                raise ValueError(f"{name} 仍含翻译实现：{forbidden}")
    manifest = {name: hashlib.sha256(data).hexdigest() for name, data in sorted(payload.items())}
    payload["manifest.json"] = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    bundle.mkdir(parents=True, exist_ok=True)
    for name, data in payload.items():
        path = bundle / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    archive = output / "TaskBoard-windows.zip"
    temporary = output / "TaskBoard-windows.zip.tmp"
    with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as dest:
        for name, data in sorted(payload.items()):
            info = zipfile.ZipInfo("TaskBoard/" + name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            dest.writestr(info, data)
    temporary.replace(archive)
    with zipfile.ZipFile(archive) as check:
        for name, data in payload.items():
            if (bundle / name).read_bytes() != data or check.read("TaskBoard/" + name) != data:
                raise ValueError(f"发布内容不一致：{name}")
    return archive


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=BOARD / "release")
    args = parser.parse_args()
    try:
        archive = build(args.output)
    except (OSError, ValueError) as exc:
        print(f"发布失败：{exc}", file=sys.stderr)
        return 1
    print(f"已生成并逐字节校验：{archive}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
