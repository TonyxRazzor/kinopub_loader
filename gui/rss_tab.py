import os
import threading
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk
from tkinter.filedialog import askopenfilename

from utils.helpers import sanitize_filename, setup_context_menu


class RssTab(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.rss_episodes_list = []
        self.rss_episode_vars = []
        
        self.setup_ui()
    
    def setup_ui(self):
        info_label = ttk.Label(self, text="Используйте персональную RSS-ссылку из ваших подписок на kino.pub", foreground="blue")
        info_label.pack(anchor=tk.W, pady=(0, 10))
        
        url_frame = ttk.LabelFrame(self, text="RSS URL", padding="5")
        url_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(url_frame, text="Ссылка:").grid(row=0, column=0, sticky=tk.W)
        self.rss_url_entry = ttk.Entry(url_frame, textvariable=self.app.rss_url, width=70)
        setup_context_menu(self.rss_url_entry)
        self.rss_url_entry.grid(row=0, column=1, padx=(5, 10))
        
        ttk.Button(url_frame, text="📥 Загрузить", command=self.load_rss_by_url).grid(row=0, column=2)
        ttk.Button(url_frame, text="📂 Из файла", command=self.load_rss_from_file).grid(row=0, column=3, padx=(5, 0))
        
        load_frame = ttk.LabelFrame(self, text="Загруженные подписки", padding="5")
        load_frame.pack(fill=tk.BOTH, expand=True)
        
        self.rss_episodes_frame = ttk.Frame(load_frame)
        self.rss_episodes_frame.pack(fill=tk.BOTH, expand=True)
        
        rss_canvas = tk.Canvas(self.rss_episodes_frame)
        rss_scrollbar = ttk.Scrollbar(self.rss_episodes_frame, orient="vertical", command=rss_canvas.yview)
        self.rss_episodes_inner = ttk.Frame(rss_canvas)
        
        self.rss_episodes_inner.bind("<Configure>", lambda e: rss_canvas.configure(scrollregion=rss_canvas.bbox("all")))
        rss_canvas.create_window((0, 0), window=self.rss_episodes_inner, anchor="nw")
        rss_canvas.configure(yscrollcommand=rss_scrollbar.set)
        
        rss_canvas.pack(side="left", fill="both", expand=True)
        rss_scrollbar.pack(side="right", fill="y")
        
        rss_buttons = ttk.Frame(self)
        rss_buttons.pack(fill=tk.X, pady=(10, 0))
        
        ttk.Button(rss_buttons, text="✅ Скачать выбранные", command=self.download_selected).pack(side=tk.LEFT, padx=5)
        ttk.Button(rss_buttons, text="📦 Выбрать все", command=self.select_all).pack(side=tk.LEFT, padx=5)
        ttk.Button(rss_buttons, text="❌ Отменить все", command=self.deselect_all).pack(side=tk.LEFT, padx=5)
    
    def load_rss_by_url(self):
        url = self.app.rss_url.get().strip()
        if not url:
            messagebox.showwarning("Внимание", "Введите RSS URL")
            return
        
        self.app.status_var.set("Загрузка RSS...")
        
        def load_thread():
            root = self.app.rss_manager.get_rss_from_url(url)
            if root:
                title, seasons, episodes = self.app.rss_manager.parse_episodes(root)
                self.app.root.after(0, lambda: self.display_episodes(episodes, title))
                self.app.root.after(0, lambda: self.app.add_progress_message(f"✅ Загружен RSS: {title} ({len(episodes)} серий)"))
            else:
                self.app.root.after(0, lambda: messagebox.showerror("Ошибка", "Не удалось загрузить RSS"))
            self.app.root.after(0, lambda: self.app.status_var.set("Готов"))
        
        threading.Thread(target=load_thread, daemon=True).start()
    
    def load_rss_from_file(self):
        filepath = askopenfilename(
            title="Выберите RSS файл",
            filetypes=[("XML files", "*.xml"), ("All files", "*.*")]
        )
        if not filepath:
            return
        
        self.app.status_var.set("Загрузка RSS из файла...")
        
        def load_thread():
            root = self.app.rss_manager.get_rss_from_file(filepath)
            if root:
                title, seasons, episodes = self.app.rss_manager.parse_episodes(root)
                self.app.root.after(0, lambda: self.display_episodes(episodes, title))
                self.app.root.after(0, lambda: self.app.add_progress_message(f"✅ Загружен RSS из файла: {title} ({len(episodes)} серий)"))
            else:
                self.app.root.after(0, lambda: messagebox.showerror("Ошибка", "Не удалось прочитать RSS файл"))
            self.app.root.after(0, lambda: self.app.status_var.set("Готов"))
        
        threading.Thread(target=load_thread, daemon=True).start()
    
    def display_episodes(self, episodes, title):
        for widget in self.rss_episodes_inner.winfo_children():
            widget.destroy()
        
        self.rss_episodes_list = []
        self.rss_episode_vars = []
        
        if not episodes:
            ttk.Label(self.rss_episodes_inner, text="Нет доступных серий").pack()
            return
        
        title_label = ttk.Label(self.rss_episodes_inner, text=f"📺 {title}", font=("Arial", 12, "bold"))
        title_label.pack(anchor=tk.W, pady=(0, 10))
        
        # Функция для извлечения номера серии из названия
        def extract_episode_number(title):
            import re
            match = re.search(r'[Ss]\d+[Ee](\d+)', title, re.IGNORECASE)
            return int(match.group(1)) if match else 0
        
        # Добавляем номер серии в каждый эпизод
        for ep in episodes:
            ep["episode_num"] = extract_episode_number(ep.get("title", ""))
        
        # Группируем по сезонам
        seasons_dict = {}
        for ep in episodes:
            season = ep.get("season", 0)
            if season not in seasons_dict:
                seasons_dict[season] = []
            seasons_dict[season].append(ep)
        
        # Отображаем сезоны
        for season_num in sorted(seasons_dict.keys()):
            if season_num == 0:
                continue
            
            season_label = ttk.Label(self.rss_episodes_inner, text=f"Сезон {season_num}", font=("Arial", 10, "bold"))
            season_label.pack(anchor=tk.W, pady=(10, 5))
            
            # СОРТИРУЕМ серии внутри сезона по номеру
            for ep in sorted(seasons_dict[season_num], key=lambda x: x.get("episode_num", 0)):
                var = tk.BooleanVar()
                self.rss_episode_vars.append(var)
                
                duration = ep.get('duration_str', '?')
                episode_num = ep.get("episode_num", 0)
                
                if episode_num > 0:
                    display_text = f"  Серия {episode_num:02d}: {ep.get('title')} ({duration})"
                else:
                    display_text = f"  {ep.get('title')} ({duration})"
                
                cb = ttk.Checkbutton(self.rss_episodes_inner,
                    text=display_text,
                    variable=var)
                cb.pack(anchor=tk.W, padx=20)
                
                self.rss_episodes_list.append({"var": var, "episode": ep})
    
    def select_all(self):
        for item in self.rss_episodes_list:
            item["var"].set(True)
    
    def deselect_all(self):
        for item in self.rss_episodes_list:
            item["var"].set(False)
    
    def download_selected(self):
        selected = [item["episode"] for item in self.rss_episodes_list if item["var"].get()]
        
        if not selected:
            messagebox.showwarning("Внимание", "Не выбрано ни одной серии")
            return
        
        self.app.add_progress_message(f"\n🚀 Начинаем скачивание {len(selected)} серий из RSS...")
        
        def download_thread():
            for episode in selected:
                self.download_single_episode(episode)
        
        threading.Thread(target=download_thread, daemon=True).start()
    
    def download_single_episode(self, episode):
        title = episode.get("title", "unknown")
        url = episode.get("url")
        season = episode.get("season", 1)
        
        if not url:
            self.app.add_progress_message(f"❌ Нет ссылки для: {title}")
            return
        
        import re
        episode_num = 1
        match = re.search(r"[Ss](\d+)[Ee](\d+)", title, re.IGNORECASE)
        if match:
            episode_num = int(match.group(2))
        
        season_folder = os.path.join(self.app.download_path.get(), f"Season {season}")
        os.makedirs(season_folder, exist_ok=True)
        
        safe_title = sanitize_filename(title)
        filename = f"S{season:02d}E{episode_num:02d} - {safe_title}.mp4"
        filepath = os.path.join(season_folder, filename)
        
        if os.path.exists(filepath) and os.path.getsize(filepath) > 1000000:
            self.app.add_progress_message(f"⏭ Пропуск (уже есть): {filename}")
            return
        
        self.app.add_progress_message(f"📥 Скачивание: {filename}")
        
        def progress_callback(current, total):
            percent = (current / total) * 100
            self.app.root.after(0, lambda: self.app.status_var.set(f"Скачивание: {percent:.1f}%"))
        
        success = self.app.rss_manager.download_file(url, filepath, progress_callback)
        
        if success:
            self.app.add_progress_message(f"✅ Скачано: {filename}")
        else:
            self.app.add_progress_message(f"❌ Ошибка при скачивании {filename}")
        
        self.app.root.after(0, lambda: self.app.status_var.set("Готов"))
