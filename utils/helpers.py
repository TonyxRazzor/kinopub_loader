import re
import tkinter as tk


def sanitize_filename(name: str) -> str:
    """Очистка имени файла от недопустимых символов"""
    return re.sub(r'[\\/*?:"<>|]', "_", name)


def parse_duration(duration_str: str) -> int:
    """Парсинг длительности из строки"""
    try:
        parts = list(map(int, duration_str.split(":")))
        if len(parts) == 3:
            h, m, s = parts
        elif len(parts) == 2:
            h, m, s = 0, *parts
        else:
            return 0
        return h * 3600 + m * 60 + s
    except:
        return 0


def format_duration(seconds: int) -> str:
    """Форматирование длительности"""
    if not seconds:
        return "?"
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    if hours > 0:
        return f"{hours}ч {minutes}м"
    return f"{minutes}м"


def setup_context_menu(widget):
    """Добавляет контекстное меню (правой кнопкой) для вставки/копирования"""
    
    def copy_text():
        try:
            widget.event_generate("<<Copy>>")
        except:
            widget.clipboard_clear()
            widget.clipboard_append(widget.selection_get())
    
    def paste_text():
        try:
            widget.event_generate("<<Paste>>")
        except:
            text = widget.clipboard_get()
            widget.insert(tk.INSERT, text)
    
    def cut_text():
        try:
            widget.event_generate("<<Cut>>")
        except:
            copy_text()
            widget.delete(tk.SEL_FIRST, tk.SEL_LAST)
    
    menu = tk.Menu(widget, tearoff=0)
    menu.add_command(label="✂️ Вырезать", command=cut_text)
    menu.add_command(label="📋 Копировать", command=copy_text)
    menu.add_command(label="📌 Вставить", command=paste_text)
    menu.add_separator()
    menu.add_command(label="🗑️ Удалить", command=lambda: widget.delete(tk.SEL_FIRST, tk.SEL_LAST) if widget.selection_get() else None)
    
    def show_menu(event):
        menu.post(event.x_root, event.y_root)
    
    widget.bind("<Button-3>", show_menu)  # Правая кнопка мыши
    return menu