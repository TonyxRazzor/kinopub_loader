import os
import threading
import time
from typing import Callable, Optional

import requests


class Downloader:
    """Класс для скачивания файлов с поддержкой прогресса и очереди"""
    
    def __init__(self, session=None):
        self.session = session or requests.Session()
        self.active_downloads = {}
        self.download_queue = []
        self.is_downloading = False
    
    def download_file(self, url: str, filepath: str, 
                      progress_callback: Optional[Callable] = None,
                      complete_callback: Optional[Callable] = None,
                      error_callback: Optional[Callable] = None) -> threading.Thread:
        """Скачивание файла в отдельном потоке"""
        def download_thread():
            try:
                response = self.session.get(url, stream=True, timeout=60)
                response.raise_for_status()
                
                total_size = int(response.headers.get('content-length', 0))
                downloaded = 0
                
                # Создаем папку если не существует
                os.makedirs(os.path.dirname(filepath), exist_ok=True)
                
                with open(filepath, 'wb') as file:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            file.write(chunk)
                            downloaded += len(chunk)
                            if progress_callback and total_size:
                                progress_callback(downloaded, total_size)
                
                if complete_callback:
                    complete_callback(filepath)
                return True
                
            except Exception as e:
                if error_callback:
                    error_callback(str(e))
                print(f"Ошибка скачивания: {e}")
                return False
        
        thread = threading.Thread(target=download_thread, daemon=True)
        thread.start()
        return thread
    
    def download_with_retry(self, url: str, filepath: str, 
                            retries: int = 3,
                            progress_callback: Optional[Callable] = None,
                            complete_callback: Optional[Callable] = None) -> bool:
        """Скачивание с повторными попытками"""
        
        for attempt in range(retries):
            try:
                response = self.session.get(url, stream=True, timeout=60)
                response.raise_for_status()
                
                total_size = int(response.headers.get('content-length', 0))
                downloaded = 0
                
                os.makedirs(os.path.dirname(filepath), exist_ok=True)
                
                with open(filepath, 'wb') as file:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            file.write(chunk)
                            downloaded += len(chunk)
                            if progress_callback and total_size:
                                progress_callback(downloaded, total_size)
                
                if complete_callback:
                    complete_callback(filepath)
                return True
                
            except Exception as e:
                print(f"Попытка {attempt + 1}/{retries} не удалась: {e}")
                if attempt == retries - 1:
                    return False
                time.sleep(2)  # Ждем перед следующей попыткой
        
        return False
    
    def queue_download(self, url: str, filepath: str,
                       progress_callback: Optional[Callable] = None,
                       complete_callback: Optional[Callable] = None):
        """Добавление в очередь скачивания"""
        
        self.download_queue.append({
            'url': url,
            'filepath': filepath,
            'progress_callback': progress_callback,
            'complete_callback': complete_callback
        })
        
        if not self.is_downloading:
            self.process_queue()
    
    def process_queue(self):
        """Обработка очереди скачивания"""
        
        if not self.download_queue:
            self.is_downloading = False
            return
        
        self.is_downloading = True
        task = self.download_queue.pop(0)
        
        def on_complete(filepath):
            if task['complete_callback']:
                task['complete_callback'](filepath)
            self.process_queue()
        
        self.download_file(
            url=task['url'],
            filepath=task['filepath'],
            progress_callback=task['progress_callback'],
            complete_callback=on_complete
        )
    
    def cancel_download(self, filepath: str):
        """Отмена скачивания (по возможности)"""
        # В текущей реализации сложно отменить requests запрос
        # Можно добавить флаги отмены, но это потребует изменений
        pass
