import io
import os
import threading
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk

import requests
from PIL import Image, ImageTk

from utils.helpers import sanitize_filename, setup_context_menu


class SearchTab(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.search_results = []
        self.selected_series = None
        self.episode_checkboxes = []
        self.episode_vars = []
        self.poster_cache = {}
        
        self.setup_ui()
    
    def setup_ui(self):
        # Панель поиска
        search_frame = ttk.Frame(self)
        search_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(search_frame, text="Название:").pack(side=tk.LEFT, padx=(0, 5))
        self.search_entry = ttk.Entry(search_frame, width=40)
        setup_context_menu(self.search_entry)
        self.search_entry.pack(side=tk.LEFT, padx=(0, 10))
        self.search_entry.bind("<Return>", lambda e: self.search_series())
        
        ttk.Button(search_frame, text="🔍 Найти", command=self.search_series).pack(side=tk.LEFT)
        
        # Результаты поиска
        results_frame = ttk.LabelFrame(self, text="Результаты поиска", padding="5")
        results_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        columns = ("poster", "id", "title", "year", "type")
        self.results_tree = ttk.Treeview(results_frame, columns=columns, show="headings", height=6)
        self.results_tree.heading("poster", text="")
        self.results_tree.heading("id", text="ID")
        self.results_tree.heading("title", text="Название")
        self.results_tree.heading("year", text="Год")
        self.results_tree.heading("type", text="Тип")
        
        self.results_tree.column("poster", width=35, anchor="center")
        self.results_tree.column("id", width=50)
        self.results_tree.column("title", width=400)
        self.results_tree.column("year", width=60)
        self.results_tree.column("type", width=80)
        
        scrollbar = ttk.Scrollbar(results_frame, orient=tk.VERTICAL, command=self.results_tree.yview)
        self.results_tree.configure(yscrollcommand=scrollbar.set)
        self.results_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.results_tree.bind("<<TreeviewSelect>>", self.on_search_select)
        
        # Информация и серии
        info_frame = ttk.Frame(self)
        info_frame.pack(fill=tk.BOTH, expand=True)
        info_frame.columnconfigure(0, weight=2)
        info_frame.columnconfigure(1, weight=1)
        info_frame.columnconfigure(2, weight=3)
        
        # Левая панель - информация
        info_left = ttk.LabelFrame(info_frame, text="Информация", padding="5")
        info_left.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 5))
        
        self.info_text = scrolledtext.ScrolledText(info_left, height=8, wrap=tk.WORD)
        self.info_text.pack(fill=tk.BOTH, expand=True)
        
        # Центральная панель - постер
        poster_frame = ttk.LabelFrame(info_frame, text="Постер", padding="5")
        poster_frame.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 5))
        self.poster_frame = poster_frame
        
        # Правая панель - серии
        info_right = ttk.LabelFrame(info_frame, text="Серии (из RSS)", padding="5")
        info_right.grid(row=0, column=2, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        episodes_container = ttk.Frame(info_right)
        episodes_container.pack(fill=tk.BOTH, expand=True)
        
        canvas = tk.Canvas(episodes_container)
        scrollbar_ep = ttk.Scrollbar(episodes_container, orient="vertical", command=canvas.yview)
        self.episodes_frame = ttk.Frame(canvas)
        
        self.episodes_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.episodes_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar_ep.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar_ep.pack(side="right", fill="y")
        
        # Кнопки действий
        actions_frame = ttk.Frame(self)
        actions_frame.pack(fill=tk.X, pady=(10, 0))
        
        ttk.Button(actions_frame, text="📥 Скачать выбранные серии", command=self.download_selected_episodes).pack(side=tk.LEFT, padx=5)
        ttk.Button(actions_frame, text="📦 Выбрать все", command=self.select_all_episodes).pack(side=tk.LEFT, padx=5)
        ttk.Button(actions_frame, text="❌ Отменить все", command=self.deselect_all_episodes).pack(side=tk.LEFT, padx=5)
    
    def search_series(self):
        if not self.app.auth or not self.app.auth.is_authenticated:
            messagebox.showwarning("Внимание", "Сначала авторизуйтесь")
            return
        
        query = self.search_entry.get().strip()
        if len(query) < 3:
            messagebox.showwarning("Внимание", "Введите минимум 3 символа")
            return
        
        self.app.status_var.set(f"Поиск: {query}...")
        self.app.root.config(cursor="watch")
        
        def search_thread():
            results = self.app.auth.search(query)
            self.app.root.after(0, lambda: self.display_search_results(results))
        
        threading.Thread(target=search_thread, daemon=True).start()
    
    def display_search_results(self, results):
        for item in self.results_tree.get_children():
            self.results_tree.delete(item)
        
        self.search_results = results
        
        for i, item in enumerate(results):
            self.results_tree.insert("", tk.END, iid=str(i), values=(
                "⏳",
                item.get("id", "N/A"),
                item.get("title", "Unknown"),
                item.get("year", "N/A"),
                item.get("type", "unknown")
            ))
        
        self.load_posters_batch(0)
        self.app.status_var.set(f"Найдено: {len(results)} результатов")
        self.app.root.config(cursor="")
    
    def load_posters_batch(self, start_index):
        end_index = min(start_index + 5, len(self.search_results))
        
        for i in range(start_index, end_index):
            item = self.search_results[i]
            poster_url = item.get("poster", "")
            
            if poster_url:
                try:
                    response = requests.get(poster_url, timeout=10, headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                    })
                    
                    if response.status_code == 200:
                        img = Image.open(io.BytesIO(response.content))
                        img.thumbnail((30, 40), Image.Resampling.LANCZOS)
                        photo = ImageTk.PhotoImage(img)
                        
                        if not hasattr(self, 'poster_cache'):
                            self.poster_cache = {}
                        self.poster_cache[i] = photo
                        
                        icon = "📺" if item.get("type") == "serial" else "🎬"
                        self.results_tree.set(str(i), column="poster", value=icon)
                    else:
                        self.results_tree.set(str(i), column="poster", value="❌")
                except:
                    self.results_tree.set(str(i), column="poster", value="❌")
            else:
                icon = "📺" if item.get("type") == "serial" else "🎬"
                self.results_tree.set(str(i), column="poster", value=icon)
        
        if end_index < len(self.search_results):
            self.app.root.after(500, lambda: self.load_posters_batch(end_index))
    
    def on_search_select(self, event):
        selection = self.results_tree.selection()
        if not selection:
            return
        
        item_values = self.results_tree.item(selection[0])["values"]
        if len(item_values) >= 2:
            item_id = item_values[1]
        else:
            return
        
        for search_item in self.search_results:
            if search_item.get("id") == item_id:
                self.selected_series = search_item
                self.show_series_info(search_item)
                self.show_poster(search_item.get("poster", ""))
                self.load_series_rss(search_item)
                break
    
    def show_series_info(self, series):
        self.info_text.delete(1.0, tk.END)
        self.info_text.insert(tk.END, f"Название: {series.get('title', 'N/A')}\n")
        self.info_text.insert(tk.END, f"Оригинальное название: {series.get('original_title', 'N/A')}\n")
        self.info_text.insert(tk.END, f"Год: {series.get('year', 'N/A')}\n")
        self.info_text.insert(tk.END, f"Тип: {series.get('type', 'N/A')}\n")
        self.info_text.insert(tk.END, f"ID: {series.get('id', 'N/A')}\n")
        
        if series.get('id'):
            self.info_text.insert(tk.END, f"\nСсылка: https://kino.pub/item/view/{series.get('id')}\n")
    
    def show_poster(self, poster_url):
        for widget in self.poster_frame.winfo_children():
            widget.destroy()
        
        if not poster_url:
            ttk.Label(self.poster_frame, text="Нет постера").pack(expand=True, pady=20)
            return
        
        loading_label = ttk.Label(self.poster_frame, text="⏳ Загрузка...")
        loading_label.pack(expand=True, pady=20)
        
        def load_poster_thread():
            try:
                response = requests.get(poster_url, timeout=15, headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                })
                
                if response.status_code == 200:
                    img = Image.open(io.BytesIO(response.content))
                    img.thumbnail((180, 260), Image.Resampling.LANCZOS)
                    photo = ImageTk.PhotoImage(img)
                    self.app.root.after(0, lambda: self.update_poster_display(photo))
                else:
                    self.app.root.after(0, self.show_poster_error)
            except:
                self.app.root.after(0, self.show_poster_error)
        
        threading.Thread(target=load_poster_thread, daemon=True).start()
    
    def update_poster_display(self, photo):
        for widget in self.poster_frame.winfo_children():
            widget.destroy()
        label = ttk.Label(self.poster_frame, image=photo)
        label.image = photo
        label.pack(expand=True, pady=10)
    
    def show_poster_error(self):
        for widget in self.poster_frame.winfo_children():
            widget.destroy()
        ttk.Label(self.poster_frame, text="❌ Не удалось\nзагрузить постер").pack(expand=True, pady=20)
    
    def load_series_rss(self, series):
        self.app.status_var.set(f"Поиск RSS для: {series.get('title')}")
        
        def load_thread():
            rss_url = None
            if self.app.auth and self.app.auth.is_authenticated:
                rss_url = self.app.auth.get_series_rss(series.get("id"))
            
            if not rss_url:
                rss_url = f"https://kino.pub/rss/series/{series.get('id')}"
            
            root = self.app.rss_manager.get_rss_from_url(rss_url)
            if root:
                title, seasons, episodes = self.app.rss_manager.parse_episodes(root)
                self.app.root.after(0, lambda: self.display_episodes_from_rss(episodes, title))
            else:
                self.app.root.after(0, self.clear_episodes_display)
        
        threading.Thread(target=load_thread, daemon=True).start()
    
    def display_episodes_from_rss(self, episodes, title):
        self.clear_episodes_display()
        
        if not episodes:
            ttk.Label(self.episodes_frame, text="Нет доступных серий").pack()
            return
        
        seasons_dict = {}
        for ep in episodes:
            season = ep.get("season", 0)
            if season not in seasons_dict:
                seasons_dict[season] = []
            seasons_dict[season].append(ep)
        
        for season_num in sorted(seasons_dict.keys()):
            if season_num == 0:
                continue
            season_label = ttk.Label(self.episodes_frame, text=f"Сезон {season_num}", font=("Arial", 10, "bold"))
            season_label.pack(anchor=tk.W, pady=(10, 5))
            
            for ep in seasons_dict[season_num]:
                var = tk.BooleanVar()
                self.episode_vars.append(var)
                
                cb = ttk.Checkbutton(self.episodes_frame,
                    text=f"Серия: {ep.get('title')} ({ep.get('duration_str', '?')})",
                    variable=var)
                cb.pack(anchor=tk.W, padx=20)
                
                self.episode_checkboxes.append({"var": var, "episode": ep})
        
        self.app.add_progress_message(f"✅ Загружено {len(episodes)} серий для {title}")
    
    def clear_episodes_display(self):
        for widget in self.episodes_frame.winfo_children():
            widget.destroy()
        self.episode_checkboxes = []
        self.episode_vars = []
    
    def select_all_episodes(self):
        for item in self.episode_checkboxes:
            item["var"].set(True)
    
    def deselect_all_episodes(self):
        for item in self.episode_checkboxes:
            item["var"].set(False)
    
    def download_selected_episodes(self):
        selected = [item["episode"] for item in self.episode_checkboxes if item["var"].get()]
        
        if not selected:
            messagebox.showwarning("Внимание", "Не выбрано ни одной серии")
            return
        
        self.app.add_progress_message(f"\n🚀 Начинаем скачивание {len(selected)} серий...")
        
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
        
        episode_num = 1
        import re
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
