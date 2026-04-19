import os
import sys


def resource_path(relative_path: str) -> str:
    """Получить путь к файлу, работает и в разработке, и в exe"""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)
