#!/usr/bin/env python3
"""Download the uv binary for the current platform into vendor/."""

import io
import platform
import shutil
import sys
import tarfile
import urllib.request
import zipfile
from pathlib import Path

BASE_URL = "https://github.com/astral-sh/uv/releases/latest/download"

PLATFORM_MAP = {
    ("Linux", "x86_64"): "uv-x86_64-unknown-linux-gnu.tar.gz",
    ("Linux", "aarch64"): "uv-aarch64-unknown-linux-gnu.tar.gz",
    ("Darwin", "x86_64"): "uv-x86_64-apple-darwin.tar.gz",
    ("Darwin", "arm64"): "uv-aarch64-apple-darwin.tar.gz",
    ("Windows", "AMD64"): "uv-x86_64-pc-windows-msvc.zip",
}


def get_archive_name() -> str:
    key = (platform.system(), platform.machine())
    name = PLATFORM_MAP.get(key)
    if not name:
        sys.exit(f"Unsupported platform: {key[0]} {key[1]}")
    return name


def download(url: str) -> bytes:
    print(f"Downloading {url} ...")
    req = urllib.request.Request(url, headers={"User-Agent": "pyplug-download"})
    with urllib.request.urlopen(req) as resp:
        return resp.read()


def extract(data: bytes, archive_name: str, dest: Path):
    if archive_name.endswith(".tar.gz"):
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
            for member in tar.getmembers():
                basename = Path(member.name).name
                if basename in ("uv", "uvx"):
                    member.name = basename
                    tar.extract(member, dest)
                    (dest / basename).chmod(0o755)
    elif archive_name.endswith(".zip"):
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            for info in zf.infolist():
                basename = Path(info.filename).name
                if basename in ("uv.exe", "uvx.exe"):
                    info.filename = basename
                    zf.extract(info, dest)


def main():
    vendor = Path(__file__).resolve().parent.parent / "vendor"
    vendor.mkdir(exist_ok=True)

    archive_name = get_archive_name()
    url = f"{BASE_URL}/{archive_name}"
    data = download(url)
    extract(data, archive_name, vendor)

    binary = "uv.exe" if platform.system() == "Windows" else "uv"
    path = vendor / binary
    if path.exists():
        print(f"Installed {path} ({path.stat().st_size / 1024 / 1024:.1f} MB)")
    else:
        sys.exit("Failed to extract uv binary")


if __name__ == "__main__":
    main()
