'''PyInstaller 打包入口：双击 exe 时启动 GUI。'''

from __future__ import annotations

import sys

from rekindle.interfaces.gui import main

if __name__ == '__main__':
    sys.exit(main())
