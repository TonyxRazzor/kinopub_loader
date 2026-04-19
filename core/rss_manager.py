import re
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Tuple

import cloudscraper

from core.downloader import Downloader
from utils.helpers import format_duration, parse_duration


class RSSManager:
    def __init__(self, session=None):
        if session:
            self.session = session
            self.downloader = Downloader(session=session)
        else:
            self.session = cloudscraper.create_scraper()
            self.downloader = Downloader(session=self.session)
    
    def get_rss_from_url(self, rss_url: str) -> Optional[ET.Element]:
        try:
            response = self.session.get(rss_url, timeout=30)
            response.raise_for_status()
            return ET.fromstring(response.content)
        except Exception as e:
            print(f"Ошибка загрузки RSS: {e}")
            return None
    
    def get_rss_from_file(self, filepath: str) -> Optional[ET.Element]:
        try:
            tree = ET.parse(filepath)
            return tree.getroot()
        except Exception as e:
            print(f"Ошибка чтения RSS файла: {e}")
            return None
    
    def parse_episodes(self, root: ET.Element) -> Tuple[str, List[int], List[Dict]]:
        channel_title = root.findtext("./channel/title") or "Без названия"
        episodes = []
        season_set = set()
        
        for item in root.findall(".//item"):
            title = item.findtext("title") or "no-title"
            enclosure = item.find("enclosure")
            duration_str = item.findtext("{http://www.itunes.com/dtds/podcast-1.0.dtd}duration")
            
            if enclosure is None or not duration_str:
                continue
            
            url = enclosure.get("url")
            match = re.search(r"s(\d{1,2})e\d{1,2}", title.lower())
            season_number = int(match.group(1)) if match else 0
            
            if season_number > 0:
                season_set.add(season_number)
            
            episodes.append({
                "title": title,
                "url": url,
                "season": season_number,
                "duration": parse_duration(duration_str),
                "duration_str": format_duration(parse_duration(duration_str))
            })
        
        return channel_title, sorted(season_set), episodes
    
    def download_file(self, url: str, filepath: str, progress_callback=None) -> bool:
        """Скачивание файла (использует Downloader)"""
        return self.downloader.download_with_retry(
            url=url,
            filepath=filepath,
            retries=3,
            progress_callback=progress_callback
        )
    
    def queue_download(self, url: str, filepath: str, progress_callback=None, complete_callback=None):
        """Добавление в очередь скачивания"""
        self.downloader.queue_download(
            url=url,
            filepath=filepath,
            progress_callback=progress_callback,
            complete_callback=complete_callback
        )
