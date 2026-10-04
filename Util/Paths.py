import os
import sys
from pathlib import Path


def to_abs_path(*parts):
    # Frozen builds keep user data next to the executable (portable mode).
    root = Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parent.parent
    return str(root.joinpath(*parts))


def get_assets_path(*parts):
    root = getattr(sys, '_MEIPASS', Path(__file__).resolve().parent.parent)
    return os.path.join(root, 'assets', *parts)
