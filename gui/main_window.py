import json
import os
import threading
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk
from tkinter.filedialog import askdirectory

from core.auth import KinopubAuth
from core.rss_manager import RSSManager
from gui.rss_tab import RssTab
from gui.search_tab import SearchTab
from gui.settings_tab import SettingsTab
from utils.resource import resource_path


class KinopubApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Kinopub Downloader v1.0")
        self.root.geometry("950x800")

        try:
            icon_path = resource_path("my_icon.ico")
            self.root.iconbitmap(icon_path)
        except:
            pass
        
        # Переменные
        self.auth = None
        self.rss_manager = RSSManager()
        
        # Настройки
        self.download_path = tk.StringVar(value=os.path.join(os.getcwd(), "downloads"))
        self.rss_url = tk.StringVar()
        self.user_rss_token = tk.StringVar()
        self.saved_email = tk.StringVar()
        
        # Создание интерфейса
        self.setup_ui()
        self.load_settings()
        self.setup_global_hotkeys()
    
    def setup_ui(self):
        style = ttk.Style()
        style.theme_use('clam')
        
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        
        # Панель авторизации
        auth_frame = ttk.LabelFrame(main_frame, text="🔐 Авторизация на Kinopub", padding="5")
        auth_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        ttk.Label(auth_frame, text="Email:").grid(row=0, column=0, padx=(0, 5))
        self.email_entry = ttk.Entry(auth_frame, textvariable=self.saved_email, width=25)
        self.email_entry.grid(row=0, column=1, padx=(0, 15))
        
        ttk.Label(auth_frame, text="Пароль:").grid(row=0, column=2, padx=(0, 5))
        self.password_entry = ttk.Entry(auth_frame, width=20, show="*")
        self.password_entry.grid(row=0, column=3, padx=(0, 15))
        
        self.login_btn = ttk.Button(auth_frame, text="🔑 Войти", command=self.do_login)
        self.login_btn.grid(row=0, column=4)
        
        self.auth_status_label = ttk.Label(auth_frame, text="❌ Не авторизован", foreground="red")
        self.auth_status_label.grid(row=0, column=5, padx=(10, 0))
        
        # Вкладки
        notebook = ttk.Notebook(main_frame)
        notebook.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        main_frame.rowconfigure(1, weight=1)
        
        self.search_tab = SearchTab(notebook, self)
        notebook.add(self.search_tab, text="🔍 Поиск и скачивание")
        
        self.rss_tab = RssTab(notebook, self)
        notebook.add(self.rss_tab, text="📡 Мои подписки (RSS)")
        
        self.settings_tab = SettingsTab(notebook, self)
        notebook.add(self.settings_tab, text="⚙️ Настройки")
        
        # Прогресс загрузки
        progress_frame = ttk.LabelFrame(main_frame, text="Загрузки", padding="5")
        progress_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        progress_frame.columnconfigure(0, weight=1)
        
        self.progress_text = scrolledtext.ScrolledText(progress_frame, height=8, wrap=tk.WORD)
        self.progress_text.grid(row=0, column=0, sticky=(tk.W, tk.E))
        
        # Статусбар
        self.status_var = tk.StringVar(value="Готов к работе")
        status_bar = ttk.Label(main_frame, textvariable=self.status_var, relief=tk.SUNKEN)
        status_bar.grid(row=3, column=0, sticky=(tk.W, tk.E))
    
    def do_login(self):
        email = self.email_entry.get().strip()
        password = self.password_entry.get()
        
        if not email or not password:
            messagebox.showerror("Ошибка", "Введите email и пароль")
            return
        
        self.login_btn.config(state="disabled", text="⏳ Вход...")
        self.auth_status_label.config(text="Авторизация...", foreground="orange")
        
        def login_thread():
            auth = KinopubAuth()
            success, message = auth.login(email, password)
            
            if success:
                self.auth = auth
                self.rss_manager = RSSManager(session=auth.scraper)
                self.root.after(0, lambda: self.auth_status_label.config(text="✅ Авторизован", foreground="green"))
                self.root.after(0, lambda: self.login_btn.config(text="🔑 Войти", state="normal"))
                self.add_progress_message(f"✅ {message}")
                
                rss_url = auth.get_rss_url()
                if rss_url:
                    self.root.after(0, lambda: self.rss_url.set(rss_url))
                self.save_settings()
            elif message == "2FA_REQUIRED":
                self.root.after(0, lambda: self.request_2fa_code(auth, email, password))
            else:
                self.root.after(0, lambda: self.auth_status_label.config(text="❌ Ошибка входа", foreground="red"))
                self.root.after(0, lambda: self.login_btn.config(text="🔑 Войти", state="normal"))
                self.root.after(0, lambda: messagebox.showerror("Ошибка", message))
        
        threading.Thread(target=login_thread, daemon=True).start()
    
    def request_2fa_code(self, auth, email, password):
        from tkinter import simpledialog
        code = simpledialog.askstring("Проверочный код", "Введите код из письма:", parent=self.root)
        
        if code:
            def verify_thread():
                success, message = auth.login(email, password, formcode=code)
                if success:
                    self.auth = auth
                    self.rss_manager = RSSManager(session=auth.scraper)
                    self.root.after(0, lambda: self.auth_status_label.config(text="✅ Авторизован", foreground="green"))
                    self.add_progress_message(f"✅ {message}")
                else:
                    self.root.after(0, lambda: messagebox.showerror("Ошибка", message))
            
            threading.Thread(target=verify_thread, daemon=True).start()
    
    def add_progress_message(self, message):
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.progress_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.progress_text.see(tk.END)
    
    def load_settings(self):
        settings_file = resource_path("kinopub_settings.json")
        if os.path.exists(settings_file):
            try:
                with open(settings_file, 'r') as f:
                    settings = json.load(f)
                    self.download_path.set(settings.get("download_path", self.download_path.get()))
                    self.user_rss_token.set(settings.get("user_rss_token", ""))
                    self.saved_email.set(settings.get("saved_email", ""))
                    if self.user_rss_token.get():
                        self.rss_url.set(f"https://kino.pub/rss/user/{self.user_rss_token.get()}/")
            except:
                pass
    
    def save_settings(self):
        settings = {
            "download_path": self.download_path.get(),
            "user_rss_token": self.user_rss_token.get(),
            "saved_email": self.email_entry.get().strip()
        }
        try:
            settings_file = resource_path("kinopub_settings.json")
            with open(settings_file, 'w') as f:
                json.dump(settings, f)
        except:
            pass
    
    def select_download_folder(self):
        folder = askdirectory(title="Выберите папку для загрузки")
        if folder:
            self.download_path.set(folder)
            self.save_settings()

    def setup_global_hotkeys(self):
        """Настройка глобальных горячих клавиш"""
        
        # Для всех Entry виджетов
        def on_focus_in(event):
            widget = event.widget
            if isinstance(widget, (ttk.Entry, tk.Entry)):
                widget.bind("<Control-v>", self.paste_from_clipboard)
                widget.bind("<Control-V>", self.paste_from_clipboard)
                widget.bind("<Control-c>", self.copy_to_clipboard)
                widget.bind("<Control-C>", self.copy_to_clipboard)
        
        def on_focus_out(event):
            widget = event.widget
            if isinstance(widget, (ttk.Entry, tk.Entry)):
                widget.unbind("<Control-v>")
                widget.unbind("<Control-V>")
                widget.unbind("<Control-c>")
                widget.unbind("<Control-C>")
        
        self.root.bind("<FocusIn>", on_focus_in)
        self.root.bind("<FocusOut>", on_focus_out)

    def paste_from_clipboard(self, event=None):
        """Вставка из буфера обмена"""
        try:
            text = self.root.clipboard_get()
            widget = self.root.focus_get()
            if widget and isinstance(widget, (ttk.Entry, tk.Entry, tk.Text)):
                widget.insert(tk.INSERT, text)
            return "break"
        except:
            pass

    def copy_to_clipboard(self, event=None):
        """Копирование в буфер обмена"""
        try:
            widget = self.root.focus_get()
            if widget and isinstance(widget, (ttk.Entry, tk.Entry, tk.Text)):
                if widget.selection_get():
                    self.root.clipboard_clear()
                    self.root.clipboard_append(widget.selection_get())
            return "break"
        except:
            pass