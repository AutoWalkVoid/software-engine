"""在没有 pip 的虚拟环境里安装纯 Python / Windows wheel 依赖。

本机（Windows + DSH 文件沙箱）执行 `python -m venv .venv` 时 ensurepip 失败，
`.venv` 里没有 pip；`python -m pip install --target ...` 也会因为 pip 自己的临时
目录被沙箱拒绝而报 PermissionError。这个脚本绕开 pip：直接从 PyPI 下载 wheel
（wheel 本身就是 zip），解压到指定 site-packages 目录。

用法（在 backend 目录下）：
    D:\\Python\\Python313\\python.exe tools\\bootstrap_deps.py .venv\\Lib\\site-packages

正常环境请优先使用：
    .venv\\Scripts\\pip install -r requirements.txt
"""
import json
import pathlib
import sys
import urllib.request
import zipfile

# (包名, 版本前缀)；版本前缀为 None 表示取最新
PACKAGES = [
    ("django", "5.2."),
    ("djangorestframework", None),
    ("asgiref", None),
    ("sqlparse", None),
    ("tzdata", None),
    ("pillow", None),
]

TARGET = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else ".venv/Lib/site-packages")
DOWNLOAD = TARGET.parent.parent.parent / "var" / "wheels"
DOWNLOAD.mkdir(parents=True, exist_ok=True)


def fetch_json(name):
    with urllib.request.urlopen(f"https://pypi.org/pypi/{name}/json", timeout=60) as response:
        return json.load(response)


def pick_wheel(name, prefix=None):
    release = fetch_json(name)["releases"]
    candidates = []
    for version, files in release.items():
        if prefix and not version.startswith(prefix):
            continue
        for file in files:
            filename = file["filename"]
            if not filename.endswith(".whl"):
                continue
            # 纯 Python 包优先；Pillow 需要匹配本机解释器与平台
            pure = filename.endswith("py3-none-any.whl") or filename.endswith("py2.py3-none-any.whl")
            native = ("cp313" in filename) and ("win_amd64" in filename)
            if pure or native:
                candidates.append((version, file, pure))
                break
    if not candidates:
        raise SystemExit(f"没有可用的 wheel: {name}")
    # 纯 Python 优先，否则取版本号最大者
    candidates.sort(key=lambda item: (item[2], [int(p) for p in item[0].split(".") if p.isdigit()]))
    return candidates[-1]


def main():
    for name, prefix in PACKAGES:
        version, wheel, _pure = pick_wheel(name, prefix)
        dest = DOWNLOAD / wheel["filename"]
        print(f"{name}=={version}: {wheel['filename']}")
        if not dest.exists():
            with urllib.request.urlopen(wheel["url"], timeout=180) as response:
                dest.write_bytes(response.read())
        with zipfile.ZipFile(dest) as archive:
            archive.extractall(TARGET)
    print("done ->", TARGET)


if __name__ == "__main__":
    main()
