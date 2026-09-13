#!/usr/bin/env python3
"""构建单文件 TaskBoard.exe；不打安装包，不携带 WebView2，不改 Web ZIP。"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOARD = ROOT / "board"
TAURI = BOARD / "tauri" / "src-tauri"
DEFAULT_OUTPUT = BOARD / "release-desktop"
BIN_NAME = "TaskBoard.exe"
FORBIDDEN_SUBSTRINGS = (
    "webview2",
    "msedgewebview",
    "python",
    "node",
    "sidecar",
    "nsis",
    "wix",
    "msi",
    "msix",
)
VCVARS = Path(r"C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def pe_machine(data: bytes) -> str:
    if data[:2] != b"MZ":
        raise ValueError("构建产物不是 PE 可执行文件")
    e_lfanew = int.from_bytes(data[0x3C:0x40], "little")
    if data[e_lfanew:e_lfanew + 4] != b"PE\x00\x00":
        raise ValueError("构建产物缺少 PE 头")
    machine = int.from_bytes(data[e_lfanew + 4:e_lfanew + 6], "little")
    names = {0x8664: "x86_64", 0x14C: "x86", 0xAA64: "arm64"}
    return names.get(machine, hex(machine))


def require_tools() -> None:
    for name in ("rustc", "cargo"):
        if shutil.which(name) is None:
            raise ValueError(f"缺少 {name}，无法构建桌面入口")


def cargo_env() -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("CARGO_TERM_COLOR", "never")
    return env


def run_cargo(args: list[str], cwd: Path) -> None:
    if os.name == "nt" and VCVARS.is_file():
        command = "call " + subprocess.list2cmdline([str(VCVARS)]) + " && " + subprocess.list2cmdline(args)
        completed = subprocess.run(command, cwd=str(cwd), env=cargo_env(), shell=True)
    else:
        completed = subprocess.run(args, cwd=str(cwd), env=cargo_env())
    if completed.returncode != 0:
        raise ValueError(f"cargo 构建失败，退出码 {completed.returncode}")


def maybe_install_tauri_cli() -> None:
    # 发布走 cargo build --release --bin TaskBoard，不需要把 cargo-tauri 装进发行物。
    return


def assert_inputs() -> None:
    for rel in ("static/index.html", "static/app.js"):
        path = BOARD / rel
        if not path.is_file():
            raise ValueError(f"缺少嵌入输入：{path}")
        text = path.read_text(encoding="utf-8-sig")
        for needle in ("board.i18n.json", "parseI18n", "translated(", "name_zh", "desc_zh", "summary_zh", "reason_zh"):
            if needle in text:
                raise ValueError(f"{rel} 仍含翻译实现：{needle}")
    conf = json.loads((TAURI / "tauri.conf.json").read_text(encoding="utf-8"))
    if conf.get("bundle", {}).get("active") is not False:
        raise ValueError("tauri.conf.json bundle.active 必须为 false")
    install_mode = conf.get("bundle", {}).get("windows", {}).get("webviewInstallMode", {})
    if install_mode.get("type") != "skip":
        raise ValueError("tauri.conf.json 必须跳过 WebView2 安装")
    dumped = json.dumps(conf).lower()
    for needle in ("webview2loader", "fixedruntime", "offlineinstaller", "bootstrapper"):
        if needle in dumped:
            raise ValueError(f"tauri.conf.json 不得配置 {needle}")


def built_exe() -> Path:
    return TAURI / "target" / "release" / BIN_NAME


def validate_release_dir(output: Path, allow_missing: bool = False) -> None:
    if not output.exists():
        if allow_missing:
            return
        raise ValueError(f"发布目录不存在：{output}")
    if output.is_symlink() or output.resolve() != output:
        raise ValueError("拒绝写入重定向发布目录")
    allowed = {BIN_NAME.lower(), "manifest.json"}
    for path in output.rglob("*"):
        if path.is_symlink():
            raise ValueError(f"发布目录含符号链接：{path}")
        if path.is_file():
            name = path.name.lower()
            if path.relative_to(output).as_posix() not in {BIN_NAME, "manifest.json"} and name not in allowed:
                raise ValueError(f"发布目录存在未知残留，请人工处理后重建：{path}")
            blob = path.name.lower() + str(path).lower()
            if any(item in blob for item in FORBIDDEN_SUBSTRINGS) and path.name not in {BIN_NAME, "manifest.json"}:
                raise ValueError(f"发布目录含禁止文件：{path}")


def copy_atomic(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    if tmp.exists():
        tmp.unlink()
    shutil.copy2(src, tmp)
    tmp.replace(dest)


def build(output: Path) -> Path:
    output = output.resolve()
    if not output.is_relative_to(ROOT):
        raise ValueError("发布目录必须位于当前技能仓库内")
    require_tools()
    assert_inputs()
    validate_release_dir(output, allow_missing=True)
    maybe_install_tauri_cli()
    run_cargo(["cargo", "build", "--release", "--bin", "TaskBoard"], TAURI)
    exe = built_exe()
    if not exe.is_file():
        raise ValueError(f"未生成 {exe}")
    data = exe.read_bytes()
    machine = pe_machine(data)
    if machine != "x86_64":
        raise ValueError(f"仅发布 x86_64，当前为 {machine}")
    output.mkdir(parents=True, exist_ok=True)
    validate_release_dir(output, allow_missing=False)
    dest = output / BIN_NAME
    copy_atomic(exe, dest)
    copied = dest.read_bytes()
    if copied != data:
        raise ValueError("复制后的 EXE 与构建产物不一致")
    manifest = {
        "name": BIN_NAME,
        "version": "1.0.0",
        "sha256": sha256_bytes(copied),
        "size": len(copied),
        "pe_machine": machine,
        "bundle": False,
        "webview2": "system-only",
    }
    manifest_path = output / "manifest.json"
    payload = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    tmp = manifest_path.with_suffix(".json.tmp")
    tmp.write_bytes(payload)
    tmp.replace(manifest_path)
    names = sorted(path.name for path in output.iterdir() if path.is_file())
    if names != [BIN_NAME, "manifest.json"] and names != ["TaskBoard.exe", "manifest.json"]:
        unexpected = [name for name in names if name not in {BIN_NAME, "manifest.json"}]
        if unexpected:
            raise ValueError(f"发布目录只能有 TaskBoard.exe 与 manifest.json，发现：{unexpected}")
    return dest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        exe = build(args.output)
    except (OSError, ValueError) as exc:
        print(f"桌面发布失败：{exc}", file=sys.stderr)
        return 1
    print(f"已生成单文件桌面入口：{exe}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
