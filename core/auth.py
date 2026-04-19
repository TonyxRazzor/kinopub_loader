import re
from typing import Dict, List, Optional, Tuple

import cloudscraper


class KinopubAuth:
    def __init__(self):
        self.scraper = cloudscraper.create_scraper(
            browser={
                'browser': 'chrome',
                'platform': 'windows',
                'desktop': True
            }
        )
        self.is_authenticated = False
        self.user_id = None
        self.rss_token = None
    
    def login(self, email: str, password: str, formcode: str = None) -> Tuple[bool, str]:
        """Авторизация на сайте с поддержкой 2FA"""
        try:
            print("🔄 Обход Cloudflare...")
            
            login_page_url = "https://kino.pub/user/login"
            response = self.scraper.get(login_page_url, timeout=30)
            
            if response.status_code != 200:
                return False, f"Ошибка загрузки страницы: {response.status_code}"
            
            # Ищем CSRF токен
            csrf_token = None
            match = re.search(r'<meta name="csrf-token" content="([^"]+)"', response.text)
            if match:
                csrf_token = match.group(1)
            
            if not csrf_token:
                match = re.search(r'<input type="hidden" name="_csrf" value="([^"]+)"', response.text)
                if match:
                    csrf_token = match.group(1)
            
            if not csrf_token:
                return False, "Не удалось найти CSRF токен"
            
            # Отправляем данные для входа
            login_data = {
                "_csrf": csrf_token,
                "login-form[login]": email,
                "login-form[password]": password,
                "login-form[rememberMe]": "1",
            }
            
            if formcode:
                login_data["login-form[formcode]"] = formcode
            
            headers = {
                "Referer": login_page_url,
                "Origin": "https://kino.pub",
                "Content-Type": "application/x-www-form-urlencoded",
            }
            
            response = self.scraper.post(
                login_page_url, data=login_data, headers=headers,
                timeout=30, allow_redirects=True
            )
            
            # Проверяем, не запрашивается ли код
            if 'login-form[formcode]' in response.text or 'Проверочный код' in response.text:
                return False, "2FA_REQUIRED"
            
            # Проверяем успешность
            is_logged_in = False
            
            if response.url == "https://kino.pub/":
                is_logged_in = True
            
            for cookie in self.scraper.cookies:
                if cookie.name == 'token':
                    self.rss_token = cookie.value
                    is_logged_in = True
            
            if 'href="/user/logout"' in response.text:
                is_logged_in = True
            
            if is_logged_in:
                self.is_authenticated = True
                return True, "Авторизация успешна"
            else:
                return False, "Неверный логин или пароль"
                
        except Exception as e:
            return False, f"Ошибка: {e}"
    
    def get_rss_url(self) -> Optional[str]:
        if self.rss_token:
            return f"https://kino.pub/rss/user/{self.rss_token}/"
        return None
    
    def search(self, query: str) -> List[Dict]:
        """Поиск контента"""
        if not self.is_authenticated:
            return []
        
        try:
            response = self.scraper.get(
                "https://kino.pub/item/search",
                params={"query": query},
                timeout=30
            )
            
            if response.status_code != 200:
                return []
            
            html = response.text
            results = []
            
            item_pattern = r'<div class="item r" data-id="item-(\d+)">.*?<div class="item-media">.*?<img src="([^"]+)".*?</div>.*?<span class="label">([^<]+)</span>.*?<a href="/item/view/\d+/(?:[^"]+)"[^>]*>([^<]+)</a>.*?<div class="item-author text-ellipsis text-muted">\s*(?:<a[^>]*>)?([^<]+)?(?:</a>)?\s*</div>\s*<div class="item-author text-ellipsis text-muted">\s*(\d{4})?'
            
            for match in re.finditer(item_pattern, html, re.DOTALL):
                try:
                    item_id = match.group(1)
                    poster_url = match.group(2).strip()
                    content_type = match.group(3).strip()
                    title = match.group(4).strip()
                    original_title = match.group(5).strip() if match.group(5) else ""
                    year = match.group(6) if match.group(6) else "0"
                    
                    if poster_url.startswith("//"):
                        poster_url = "https:" + poster_url
                    
                    if "Сериал" in content_type:
                        type_name = "serial"
                    elif "Фильм" in content_type:
                        type_name = "movie"
                    else:
                        type_name = "movie"
                    
                    results.append({
                        "id": int(item_id),
                        "title": title.strip(),
                        "original_title": original_title.strip(),
                        "year": int(year) if year.isdigit() else 0,
                        "type": type_name,
                        "poster": poster_url
                    })
                except:
                    continue
            
            return results[:50]
            
        except Exception as e:
            print(f"Ошибка поиска: {e}")
            return []
    
    def get_series_rss(self, series_id: int) -> Optional[str]:
        try:
            series_url = f"https://kino.pub/series/{series_id}"
            response = self.scraper.get(series_url, timeout=30)
            match = re.search(r'href="(https://kino\.pub/rss/series/\d+)"', response.text)
            if match:
                return match.group(1)
        except:
            pass
        return None
