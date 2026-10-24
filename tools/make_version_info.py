'''生成 PyInstaller 的 Windows 版本资源，版本号从 rekindle.__version__ 读取（单一来源）。'''

from __future__ import annotations

from pathlib import Path

from rekindle import __version__


def _quad(version: str) -> tuple[int, int, int, int]:
    parts = [int(p) for p in version.split('.') if p.isdigit()][:4]
    while len(parts) < 4:
        parts.append(0)
    return parts[0], parts[1], parts[2], parts[3]


def main() -> int:
    a, b, c, d = _quad(__version__)
    text = f"""# 由 tools/make_version_info.py 生成，不要手改
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({a}, {b}, {c}, {d}),
    prodvers=({a}, {b}, {c}, {d}),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable(
        '040904B0',
        [StringStruct('CompanyName', 'rekindle'),
         StringStruct('FileDescription', 'rekindle - local-first contacts manager'),
         StringStruct('FileVersion', '{__version__}'),
         StringStruct('InternalName', 'rekindle'),
         StringStruct('LegalCopyright', 'TBD'),
         StringStruct('OriginalFilename', 'rekindle.exe'),
         StringStruct('ProductName', 'rekindle'),
         StringStruct('ProductVersion', '{__version__}')])
    ]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"""
    out = Path('build') / 'version_info.txt'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding='utf-8')
    print(f'wrote {out} (version {__version__})')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
