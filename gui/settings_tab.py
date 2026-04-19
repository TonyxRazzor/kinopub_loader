import tkinter as tk
from tkinter import messagebox, ttk
from tkinter.filedialog import askdirectory

from utils.helpers import setup_context_menu
from utils.resource import resource_path


class SettingsTab(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.setup_ui()
    
    def setup_ui(self):
        # Папка загрузки
        folder_frame = ttk.LabelFrame(self, text="Папка для загрузок", padding="5")
        folder_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(folder_frame, text="Путь:").grid(row=0, column=0, sticky=tk.W)
        ttk.Entry(folder_frame, textvariable=self.app.download_path, width=60).grid(row=0, column=1, padx=(5, 10))
        ttk.Button(folder_frame, text="📁 Обзор", command=self.select_download_folder).grid(row=0, column=2)
        
        # Персональный RSS токен
        rss_token_frame = ttk.LabelFrame(self, text="Персональный RSS ключ (из подписок)", padding="5")
        rss_token_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(rss_token_frame, text="RSS ключ:").grid(row=0, column=0, sticky=tk.W)
        self.rss_token_entry = ttk.Entry(rss_token_frame, textvariable=self.app.user_rss_token, width=60, show="*")
        setup_context_menu(self.rss_token_entry)
        self.rss_token_entry.grid(row=0, column=1, padx=(5, 10))
        
        ttk.Label(rss_token_frame, text="\nПример ссылки: https://kino.pub/rss/user/ВАШ_КЛЮЧ/", foreground="gray").grid(row=1, column=0, columnspan=3, sticky=tk.W)
        
        # Кнопка сохранения
        ttk.Button(self, text="💾 Сохранить настройки", command=self.app.save_settings).pack(pady=10)
    
    def select_download_folder(self):
        folder = askdirectory(title="Выберите папку для загрузки")
        if folder:
            self.app.download_path.set(folder)
            self.app.save_settings()
