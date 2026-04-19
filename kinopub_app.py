import json
import os
import queue
import sys
import threading
import time
import tkinter as tk
from datetime import datetime
from tkinter import messagebox, scrolledtext, ttk
from tkinter.filedialog import askdirectory
from typing import Dict, List, Optional

import requests
from tqdm import tqdm


def resource_path(relative_path):
    """Получить путь к файлу, работает и в разработке, и в exe"""
    try:
        # PyInstaller создает временную папку и хранит путь в _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


# ============== API КЛАСС ==============
class KinopubAPI:
    def __init__(self, token: str):
        self.base_url = "https://api.service-kp.com/v1"
        self.access_token = token
        self.session = requests.Session()

        self.session.headers.update({
            "Content-Type": "application/json",
            "User-Agent": "KinopubDownloader/1.0"
        })
    
    def _add_token(self, params: dict = None) -> dict:
        """Добавляет access_token к параметрам запроса"""
        if params is None:
            params = {}
        params["access_token"] = self.access_token
        return params
    
    def search(self, query: str, content_type: str = "all") -> List[Dict]:
        """Поиск контента"""
        url = f"{self.base_url}/items/search"
        params = self._add_token({
            "q": query,
            "sectioned": 1,
            "perpage": 50
        })
        if content_type != "all":
            params["type"] = content_type
        
        try:
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            # Собираем все результаты из секций
            results = []
            for section, section_data in data.get("items", {}).items():
                if isinstance(section_data, dict) and "items" in section_data:
                    for item in section_data["items"]:
                        item["_section"] = section
                        results.append(item)
            return results
        except requests.exceptions.Timeout:
            print(f"Сервер не отвечает (Timeout). Попробуйте позже.")
            return []
        except Exception as e:
            print(f"Ошибка поиска: {e}")
            return []
    
    def get_item_info(self, item_id: int) -> Optional[Dict]:
        """Получение информации о контенте"""
        url = f"{self.base_url}/items/{item_id}"
        params = self._add_token()
        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Ошибка получения информации: {e}")
            return None
    
    def get_media_links(self, media_id: int) -> Optional[Dict]:
        """Получение ссылок на видео"""
        url = f"{self.base_url}/items/media-links"
        params = self._add_token({"mid": media_id})
        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Ошибка получения ссылок: {e}")
            return None
    
    def download_file(self, url: str, filepath: str, progress_callback=None) -> bool:
        """Скачивание файла с прогрессом"""
        try:
            # Для скачивания файлов токен может не требоваться,
            # так как URL уже содержит все необходимые параметры
            response = self.session.get(url, stream=True, timeout=60)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            
            with open(filepath, 'wb') as file:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        file.write(chunk)
                        downloaded += len(chunk)
                        if progress_callback and total_size:
                            progress_callback(downloaded, total_size)
            
            return True
        except Exception as e:
            print(f"Ошибка скачивания: {e}")
            return False


# ============== GUI ПРИЛОЖЕНИЕ ==============
class KinopubApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Kinopub Downloader v1.0")
        self.root.geometry("900x700")

        try:
            icon_path = resource_path("my_icon.ico")
            self.root.iconbitmap(icon_path)
        except:
            pass
        
        # Переменные
        self.api = None
        self.search_results = []
        self.selected_item = None
        self.selected_seasons = []
        self.selected_episodes = []
        self.download_queue = queue.Queue()
        self.downloading = False
        
        # Настройки
        self.download_path = tk.StringVar(value=os.path.join(os.getcwd(), "downloads"))
        self.quality = tk.StringVar(value="1080p")
        self.token = tk.StringVar()
        
        # Создание интерфейса
        self.setup_ui()
        
        # Загрузка сохраненных настроек
        self.load_settings()
    
    def setup_ui(self):
        # Стиль
        style = ttk.Style()
        style.theme_use('clam')
        
        # Основной контейнер
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        
        # ===== Верхняя панель (авторизация) =====
        auth_frame = ttk.LabelFrame(main_frame, text="Авторизация", padding="5")
        auth_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        ttk.Label(auth_frame, text="Токен:").grid(row=0, column=0, sticky=tk.W)
        token_entry = ttk.Entry(auth_frame, textvariable=self.token, width=50, show="*")
        token_entry.grid(row=0, column=1, padx=(5, 10))
        
        ttk.Button(auth_frame, text="Подключиться", command=self.connect).grid(row=0, column=2)
        ttk.Button(auth_frame, text="Показать/Скрыть", command=self.toggle_token_visibility).grid(row=0, column=3, padx=(5, 0))
        
        # ===== Поиск =====
        search_frame = ttk.LabelFrame(main_frame, text="Поиск", padding="5")
        search_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        ttk.Label(search_frame, text="Название:").grid(row=0, column=0, sticky=tk.W)
        self.search_entry = ttk.Entry(search_frame, width=50)
        self.search_entry.grid(row=0, column=1, padx=(5, 10))
        self.search_entry.bind("<Return>", lambda e: self.search())
        
        ttk.Label(search_frame, text="Тип:").grid(row=0, column=2, sticky=tk.W)
        self.content_type = ttk.Combobox(search_frame, values=["all", "movie", "serial"], width=10)
        self.content_type.set("all")
        self.content_type.grid(row=0, column=3, padx=(5, 10))
        
        ttk.Button(search_frame, text="🔍 Найти", command=self.search).grid(row=0, column=4)
        
        # ===== Результаты поиска =====
        results_frame = ttk.LabelFrame(main_frame, text="Результаты поиска", padding="5")
        results_frame.grid(row=2, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        results_frame.columnconfigure(0, weight=1)
        results_frame.rowconfigure(0, weight=1)
        
        # Таблица результатов
        columns = ("id", "title", "year", "type")
        self.results_tree = ttk.Treeview(results_frame, columns=columns, show="headings", height=8)
        self.results_tree.heading("id", text="ID")
        self.results_tree.heading("title", text="Название")
        self.results_tree.heading("year", text="Год")
        self.results_tree.heading("type", text="Тип")
        self.results_tree.column("id", width=50)
        self.results_tree.column("title", width=400)
        self.results_tree.column("year", width=60)
        self.results_tree.column("type", width=80)
        
        scrollbar = ttk.Scrollbar(results_frame, orient=tk.VERTICAL, command=self.results_tree.yview)
        self.results_tree.configure(yscrollcommand=scrollbar.set)
        
        self.results_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        self.results_tree.bind("<<TreeviewSelect>>", self.on_item_select)
        
        # ===== Детали и выбор =====
        details_frame = ttk.Frame(main_frame)
        details_frame.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        details_frame.columnconfigure(0, weight=1)
        details_frame.columnconfigure(1, weight=1)
        
        # Левая панель - информация
        info_frame = ttk.LabelFrame(details_frame, text="Информация", padding="5")
        info_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 5))
        
        self.info_text = scrolledtext.ScrolledText(info_frame, height=8, wrap=tk.WORD)
        self.info_text.pack(fill=tk.BOTH, expand=True)
        
        # Правая панель - выбор качества
        quality_frame = ttk.LabelFrame(details_frame, text="Настройки скачивания", padding="5")
        quality_frame.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(5, 0))
        
        ttk.Label(quality_frame, text="Качество:").grid(row=0, column=0, sticky=tk.W, pady=5)
        quality_combo = ttk.Combobox(quality_frame, textvariable=self.quality, 
                                     values=["2160p", "1080p", "720p", "480p", "360p"])
        quality_combo.grid(row=0, column=1, sticky=tk.W, padx=(5, 0))
        
        ttk.Label(quality_frame, text="Папка загрузки:").grid(row=1, column=0, sticky=tk.W, pady=5)
        ttk.Entry(quality_frame, textvariable=self.download_path, width=30).grid(row=1, column=1, padx=(5, 0))
        ttk.Button(quality_frame, text="📁 Обзор", command=self.select_download_folder).grid(row=1, column=2, padx=(5, 0))
        
        # Кнопки действий
        actions_frame = ttk.Frame(quality_frame)
        actions_frame.grid(row=2, column=0, columnspan=3, pady=10)
        
        ttk.Button(actions_frame, text="📥 Скачать фильм", command=self.download_movie).pack(side=tk.LEFT, padx=5)
        ttk.Button(actions_frame, text="🎬 Выбрать серии", command=self.open_season_selector).pack(side=tk.LEFT, padx=5)
        
        # ===== Прогресс загрузки =====
        progress_frame = ttk.LabelFrame(main_frame, text="Загрузки", padding="5")
        progress_frame.grid(row=4, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        progress_frame.columnconfigure(0, weight=1)
        
        self.progress_list = []
        self.progress_text = scrolledtext.ScrolledText(progress_frame, height=6, wrap=tk.WORD)
        self.progress_text.grid(row=0, column=0, sticky=(tk.W, tk.E))
        
        # Статусбар
        self.status_var = tk.StringVar(value="Готов к работе")
        status_bar = ttk.Label(main_frame, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.grid(row=5, column=0, sticky=(tk.W, tk.E))
        
        # Настройка весов для растягивания
        main_frame.rowconfigure(2, weight=1)
    
    def toggle_token_visibility(self):
        """Показать/скрыть токен"""
        current = self.token.get()
        # Логика переключения
        pass
    
    def load_settings(self):
        """Загрузка сохраненных настроек"""
        settings_file = resource_path("kinopub_settings.json")
        if os.path.exists(settings_file):
            try:
                with open(settings_file, 'r') as f:
                    settings = json.load(f)
                    self.download_path.set(settings.get("download_path", self.download_path.get()))
                    self.quality.set(settings.get("quality", self.quality.get()))
                    if "token" in settings:
                        self.token.set(settings["token"])
            except:
                pass
    
    def save_settings(self):
        """Сохранение настроек"""
        settings = {
            "download_path": self.download_path.get(),
            "quality": self.quality.get(),
            "token": self.token.get()
        }
        try:
            settings_file = resource_path("kinopub_settings.json")
            with open(settings_file, 'w') as f:
                json.dump(settings, f)
        except:
            pass
    
    def connect(self):
        """Подключение к API"""
        token = self.token.get().strip()
        if not token:
            messagebox.showerror("Ошибка", "Введите токен авторизации")
            return
        
        try:
            self.api = KinopubAPI(token)
            # Тестовый запрос
            test_result = self.api.search("тест", "all")
            if test_result is not None:
                self.status_var.set("✓ Подключено к Kinopub API")
                self.save_settings()
                messagebox.showinfo("Успех", "Подключение выполнено успешно!")
            else:
                raise Exception("Не удалось подключиться")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось подключиться: {e}")
            self.api = None
    
    def search(self):
        """Поиск контента"""
        if not self.api:
            messagebox.showerror("Ошибка", "Сначала подключитесь к API")
            return
        
        query = self.search_entry.get().strip()
        if len(query) < 3:
            messagebox.showwarning("Внимание", "Введите минимум 3 символа для поиска")
            return
        
        self.status_var.set(f"Поиск: {query}...")
        self.root.config(cursor="watch")
        
        def search_thread():
            results = self.api.search(query, self.content_type.get())
            self.root.after(0, lambda: self.display_results(results))
        
        threading.Thread(target=search_thread, daemon=True).start()
    
    def display_results(self, results):
        """Отображение результатов поиска"""
        self.results_tree.delete(*self.results_tree.get_children())
        self.search_results = results
        
        for item in results:
            self.results_tree.insert("", tk.END, values=(
                item.get("id", "N/A"),
                item.get("title", "Unknown"),
                item.get("year", "N/A"),
                item.get("_section", item.get("type", "unknown"))
            ))
        
        self.status_var.set(f"Найдено: {len(results)} результатов")
        self.root.config(cursor="")
    
    def on_item_select(self, event):
        """Обработка выбора элемента"""
        selection = self.results_tree.selection()
        if not selection:
            return
        
        item = self.results_tree.item(selection[0])
        item_id = item["values"][0]
        
        # Находим полную информацию
        for search_item in self.search_results:
            if search_item.get("id") == item_id:
                self.selected_item = search_item
                self.show_item_info(search_item)
                break
    
    def show_item_info(self, item):
        """Отображение информации о выбранном контенте"""
        self.info_text.delete(1.0, tk.END)
        self.info_text.insert(tk.END, f"Название: {item.get('title', 'N/A')}\n")
        self.info_text.insert(tk.END, f"Оригинальное название: {item.get('original_title', 'N/A')}\n")
        self.info_text.insert(tk.END, f"Год: {item.get('year', 'N/A')}\n")
        self.info_text.insert(tk.END, f"Тип: {item.get('_section', item.get('type', 'N/A'))}\n")
        
        if item.get('plot'):
            self.info_text.insert(tk.END, f"\nОписание:\n{item['plot'][:500]}...\n")
        
        if item.get('cast'):
            self.info_text.insert(tk.END, f"\nАктеры: {item['cast'][:200]}\n")
        
        if item.get('director'):
            self.info_text.insert(tk.END, f"Режиссер: {item['director']}\n")
        
        if item.get('rating'):
            self.info_text.insert(tk.END, f"Рейтинг: {item['rating']}\n")
    
    def select_download_folder(self):
        """Выбор папки для загрузки"""
        folder = askdirectory(title="Выберите папку для загрузки")
        if folder:
            self.download_path.set(folder)
            self.save_settings()
    
    def download_movie(self):
        """Скачивание фильма"""
        if not self.selected_item:
            messagebox.showwarning("Внимание", "Сначала выберите фильм/сериал")
            return
        
        item_type = self.selected_item.get("_section", "")
        if "serial" in item_type:
            messagebox.showinfo("Информация", "Для сериала используйте 'Выбрать серии'")
            return
        
        # Для фильма
        threading.Thread(target=self.download_single_item, daemon=True).start()
    
    def download_single_item(self):
        """Скачивание одного элемента (фильма)"""
        self.downloading = True
        self.add_progress_message(f"Начинаем скачивание: {self.selected_item.get('title')}")
        
        # Получаем информацию о медиа
        item_info = self.api.get_item_info(self.selected_item["id"])
        if not item_info:
            self.add_progress_message("❌ Не удалось получить информацию о медиа")
            self.downloading = False
            return
        
        # Извлекаем ссылки
        media_links = None
        if "videos" in item_info.get("item", {}):
            for video in item_info["item"]["videos"]:
                # Пробуем получить ссылки для этого видео
                media_links = self.api.get_media_links(video.get("id"))
                if media_links and media_links.get("files"):
                    break
                
                if not media_links or not media_links.get("files"):
                    self.add_progress_message("❌ Не найдены ссылки для скачивания")
                    self.downloading = False
                    return
        
        # Выбираем нужное качество
        video_url = None
        for file_info in media_links["files"]:
            if file_info.get("quality") == self.quality.get():
                video_url = file_info.get("urls", {}).get("http")
                break
        
        if not video_url and media_links["files"]:
            video_url = media_links["files"][0].get("urls", {}).get("http")
        
        if not video_url:
            self.add_progress_message("❌ Не удалось получить URL видео")
            self.downloading = False
            return
        
        # Формируем имя файла
        filename = f"{self.selected_item.get('title')} ({self.selected_item.get('year')}).mp4"
        filename = re.sub(r'[\\/*?:"<>|]', "", filename)
        filepath = os.path.join(self.download_path.get(), filename)
        
        # Скачиваем
        def progress_callback(current, total):
            percent = (current / total) * 100
            self.root.after(0, lambda: self.update_status(f"Скачивание: {percent:.1f}%"))
        
        success = self.api.download_file(video_url, filepath, progress_callback)
        
        if success:
            self.add_progress_message(f"✅ Скачано: {filepath}")
        else:
            self.add_progress_message(f"❌ Ошибка при скачивании {filename}")
        
        self.downloading = False
        self.update_status("Готов")
    
    def open_season_selector(self):
        """Открыть окно выбора сезонов и серий"""
        if not self.selected_item:
            messagebox.showwarning("Внимание", "Сначала выберите сериал")
            return
        
        # Проверяем, что это сериал
        item_type = self.selected_item.get("_section", "")
        if "serial" not in item_type and self.selected_item.get("type") != "serial":
            messagebox.showwarning("Внимание", "Выбранный элемент не является сериалом")
            return
        
        # Создаем окно выбора
        selector = SeasonSelector(self.root, self.api, self.selected_item, self.download_path.get(), self.quality.get())
        self.root.wait_window(selector)
    
    def add_progress_message(self, message):
        """Добавление сообщения в лог прогресса"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.root.after(0, lambda: self.progress_text.insert(tk.END, f"[{timestamp}] {message}\n"))
        self.root.after(0, lambda: self.progress_text.see(tk.END))
    
    def update_status(self, message):
        """Обновление статуса"""
        self.root.after(0, lambda: self.status_var.set(message))


# ============== ОКНО ВЫБОРА СЕЗОНОВ И СЕРИЙ ==============
class SeasonSelector(tk.Toplevel):
    def __init__(self, parent, api, series_item, download_path, quality):
        super().__init__(parent)
        self.title(f"Выбор серий - {series_item.get('title')}")
        self.geometry("800x600")
        self.api = api
        self.series_item = series_item
        self.download_path = download_path
        self.quality = quality
        self.seasons_data = []
        self.selected_episodes = []
        
        self.setup_ui()
        self.load_seasons()
    
    def setup_ui(self):
        # Основной контейнер
        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Информация о сериале
        info_label = ttk.Label(main_frame, text=f"Сериал: {self.series_item.get('title')} ({self.series_item.get('year')})", 
                               font=("Arial", 10, "bold"))
        info_label.pack(anchor=tk.W, pady=(0, 10))
        
        # Панель с сезонами (чекбоксы)
        seasons_frame = ttk.LabelFrame(main_frame, text="Сезоны", padding="5")
        seasons_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.seasons_vars = {}
        self.seasons_frame_inner = ttk.Frame(seasons_frame)
        self.seasons_frame_inner.pack()
        
        # Панель с сериями (список с чекбоксами)
        episodes_frame = ttk.LabelFrame(main_frame, text="Серии", padding="5")
        episodes_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Canvas + Scrollbar для списка серий
        canvas = tk.Canvas(episodes_frame)
        scrollbar = ttk.Scrollbar(episodes_frame, orient="vertical", command=canvas.yview)
        self.episodes_inner = ttk.Frame(canvas)
        
        self.episodes_inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.episodes_inner, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Кнопки действий
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.pack(fill=tk.X)
        
        ttk.Button(buttons_frame, text="✅ Скачать выбранные", command=self.download_selected).pack(side=tk.LEFT, padx=5)
        ttk.Button(buttons_frame, text="📦 Выбрать все", command=self.select_all).pack(side=tk.LEFT, padx=5)
        ttk.Button(buttons_frame, text="❌ Отменить все", command=self.deselect_all).pack(side=tk.LEFT, padx=5)
        
        # Прогресс
        self.progress_text = scrolledtext.ScrolledText(main_frame, height=5, wrap=tk.WORD)
        self.progress_text.pack(fill=tk.BOTH, expand=True)
    
    def load_seasons(self):
        """Загрузка информации о сезонах и сериях"""
        self.progress_text.insert(tk.END, "Загрузка информации о сериале...\n")
        self.update()
        
        def load_thread():
            item_info = self.api.get_item_info(self.series_item["id"])
            if not item_info:
                self.progress_text.insert(tk.END, "❌ Не удалось загрузить информацию о сериале\n")
                return
            
            seasons = item_info.get("item", {}).get("seasons", [])
            self.seasons_data = seasons
            
            # Отображаем сезоны
            self.root().after(0, self.display_seasons)
        
        threading.Thread(target=load_thread, daemon=True).start()
    
    def display_seasons(self):
        """Отображение чекбоксов сезонов"""
        # Очищаем предыдущие
        for widget in self.seasons_frame_inner.winfo_children():
            widget.destroy()
        
        self.seasons_vars.clear()
        
        for i, season in enumerate(self.seasons_data):
            var = tk.BooleanVar()
            self.seasons_vars[season.get("number", i+1)] = var
            cb = ttk.Checkbutton(self.seasons_frame_inner, 
                                 text=f"Сезон {season.get('number', i+1)} - {season.get('title', '')}",
                                 variable=var,
                                 command=lambda s=season: self.on_season_toggle(s))
            cb.pack(side=tk.LEFT, padx=10)
        
        # Автоматически выбираем первый сезон
        if self.seasons_data:
            first_season_num = self.seasons_data[0].get("number", 1)
            self.seasons_vars[first_season_num].set(True)
            self.on_season_toggle(self.seasons_data[0])
    
    def on_season_toggle(self, season):
        """Обработка переключения сезона"""
        season_num = season.get("number")
        is_selected = self.seasons_vars[season_num].get()
        
        if is_selected:
            self.display_episodes(season)
        else:
            # Если сезон отключен, удаляем его серии из выбора
            episodes = season.get("episodes", [])
            for ep in episodes:
                ep_id = ep.get("id", id(ep))
                if ep_id in self.selected_episodes:
                    self.selected_episodes.remove(ep_id)
            # Перерисовываем серии (если это был последний выбранный сезон)
            if not any(var.get() for var in self.seasons_vars.values()):
                self.clear_episodes_display()
    
    def display_episodes(self, season):
        """Отображение серий выбранного сезона"""
        self.clear_episodes_display()
        
        season_num = season.get("number", 1)
        episodes = season.get("episodes", [])
        
        # Заголовок
        title_label = ttk.Label(self.episodes_inner, text=f"Сезон {season_num}", font=("Arial", 10, "bold"))
        title_label.pack(anchor=tk.W, pady=(5, 5))
        
        # Создаем чекбоксы для каждой серии
        for i, episode in enumerate(episodes, 1):
            ep_id = episode.get("id", id(episode))
            var = tk.BooleanVar()
            
            # Сохраняем информацию о серии
            episode_info = {
                "id": ep_id,
                "title": episode.get("title", f"Серия {i}"),
                "season": season_num,
                "episode_num": i,
                "duration": episode.get("duration", 0),
                "data": episode
            }
            
            cb = ttk.Checkbutton(self.episodes_inner, 
                                text=f"Серия {i}: {episode_info['title']} ({self.format_duration(episode_info['duration'])})",
                                variable=var,
                                command=lambda e=episode_info, v=var: self.on_episode_toggle(e, v))
            cb.pack(anchor=tk.W, padx=20)
            
            episode_info["var"] = var
            self.episode_checkboxes.append(episode_info)
    
    def clear_episodes_display(self):
        """Очистка отображения серий"""
        for widget in self.episodes_inner.winfo_children():
            widget.destroy()
        self.episode_checkboxes = []
    
    def on_episode_toggle(self, episode_info, var):
        """Обработка выбора серии"""
        if var.get():
            if episode_info not in self.selected_episodes:
                self.selected_episodes.append(episode_info)
        else:
            if episode_info in self.selected_episodes:
                self.selected_episodes.remove(episode_info)
    
    def select_all(self):
        """Выбрать все серии в текущем сезоне"""
        for episode in self.episode_checkboxes:
            episode["var"].set(True)
            if episode not in self.selected_episodes:
                self.selected_episodes.append(episode)
    
    def deselect_all(self):
        """Отменить все выборы"""
        for episode in self.episode_checkboxes:
            episode["var"].set(False)
        self.selected_episodes.clear()
    
    def format_duration(self, seconds):
        """Форматирование длительности"""
        if not seconds:
            return "?"
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        if hours > 0:
            return f"{hours}ч {minutes}м"
        return f"{minutes}м"
    
    def download_selected(self):
        """Скачивание выбранных серий"""
        if not self.selected_episodes:
            self.progress_text.insert(tk.END, "⚠️ Не выбрано ни одной серии\n")
            return
        
        self.progress_text.insert(tk.END, f"\n🚀 Начинаем скачивание {len(self.selected_episodes)} серий...\n")
        
        def download_thread():
            for episode in self.selected_episodes:
                self.download_episode(episode)
        
        threading.Thread(target=download_thread, daemon=True).start()
    
    def download_episode(self, episode_info):
        """Скачивание одной серии"""
        episode_data = episode_info["data"]
        season_num = episode_info["season"]
        episode_num = episode_info["episode_num"]
        
        # Получаем ссылки на видео
        media_links = self.api.get_media_links(episode_info["id"])
        if not media_links or not media_links.get("files"):
            self.add_log(f"❌ Не удалось получить ссылки для {episode_info['title']}")
            return
        
        # Выбираем нужное качество
        video_url = None
        for file_info in media_links["files"]:
            if file_info.get("quality") == self.quality:
                video_url = file_info.get("urls", {}).get("http")
                break
        
        if not video_url and media_links["files"]:
            video_url = media_links["files"][0].get("urls", {}).get("http")
        
        if not video_url:
            self.add_log(f"❌ Не удалось получить URL для {episode_info['title']}")
            return
        
        # Формируем имя файла
        series_title = re.sub(r'[\\/*?:"<>|]', "", self.series_item.get("title", "series"))
        season_folder = os.path.join(self.download_path, f"Season {season_num}")
        os.makedirs(season_folder, exist_ok=True)
        
        filename = f"S{season_num:02d}E{episode_num:02d} - {episode_info['title']}.mp4"
        filename = re.sub(r'[\\/*?:"<>|]', "", filename)
        filepath = os.path.join(season_folder, filename)
        
        self.add_log(f"📥 Скачивание: {filename}")
        
        # Скачиваем
        success = self.api.download_file(video_url, filepath)
        
        if success:
            self.add_log(f"✅ Скачано: {filename}")
        else:
            self.add_log(f"❌ Ошибка при скачивании {filename}")
    
    def add_log(self, message):
        """Добавление сообщения в лог"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.progress_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.progress_text.see(tk.END)
        self.update()


# ============== ЗАПУСК ==============
if __name__ == "__main__":
    import re  # для sanitize_filename
    root = tk.Tk()
    app = KinopubApp(root)
    root.mainloop()
