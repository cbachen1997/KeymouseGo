# Reproducible Windows build: only remove components not used by this QWidget app.
from pathlib import Path
import sys

root = Path(SPECPATH).parent
ffi = Path(sys.base_prefix) / 'Library' / 'bin' / 'ffi.dll'
assets = [(str(p), str(p.parent.relative_to(root))) for p in (root / 'assets').rglob('*')
          if p.suffix in ('.qm', '.wav')]
a = Analysis(
    [str(root / 'KeymouseGo.py')], pathex=[str(root)],
    binaries=[(str(ffi), '.')] if ffi.exists() else [], datas=assets,
    hiddenimports=[], hookspath=[], runtime_hooks=[],
    excludes=['PySide6.QtMultimedia', 'PySide6.QtMultimediaWidgets',
              'PySide6.QtOpenGL', 'PySide6.QtOpenGLWidgets',
              'PySide6.QtQuick', 'PySide6.QtQml', 'PySide6.QtPdf',
              'PySide6.QtPdfWidgets', 'tkinter', 'unittest', 'pydoc'],
    noarchive=False,
)
# qpdf brings in QtPdf; software OpenGL is unused by the raster QWidget UI.
unused = {'qpdf.dll', 'Qt6Pdf.dll', 'opengl32sw.dll'}
a.binaries = [entry for entry in a.binaries if Path(entry[0]).name not in unused]
a.datas = [entry for entry in a.datas if '__pycache__' not in entry[0]
           and (not entry[0].replace('\\', '/').startswith('PySide6/translations/')
                or Path(entry[0]).stem.endswith(('_en', '_zh_CN', '_zh_TW')))]
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name='KeymouseGo',
          debug=False, strip=False, upx=False, console=False,
          icon=str(root / 'Mondrian.ico'))
