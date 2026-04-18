import os
import random
import re
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from http.client import IncompleteRead

import requests
from tqdm import tqdm

DOWNLOADS_DIR = "downloads"
MAX_WORKERS = 1
MAX_RETRIES = 3

def sanitize_filename(name):
    return re.sub(r'[\\/*?:"<>|]', "", name)

def parse_duration(duration_str):
    parts = list(map(int, duration_str.split(":")))
    if len(parts) == 3:
        h, m, s = parts
    elif len(parts) == 2:
        h, m, s = 0, *parts
    else:
        return 0
    return h * 3600 + m * 60 + s

def get_content_length(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }

    # 🔸 Добавляем паузу перед HEAD-запросом, чтобы избежать блокировок
    time.sleep(5 + random.random() * 5)

    # Пробуем HEAD-запрос
    try:
        head_resp = requests.head(url, headers=headers, timeout=10, allow_redirects=True)
        # print(f"HEAD status: {head_resp.status_code}, headers: {head_resp.headers}")

        if head_resp.status_code == 403:
            print("🚫 HEAD-запрос заблокирован (403)")
        else:
            content_length = head_resp.headers.get("Content-Length")
            if content_length and content_length.isdigit():
                size = int(content_length)
                if size > 100:
                    return size
    except Exception as e:
        print(f"HEAD request failed: {e}")

    return None

def download_episode(title, url, season_number, retries=3):
    season_folder = os.path.join("downloads", f"Season {int(season_number)}")
    os.makedirs(season_folder, exist_ok=True)

    filename = f"{title}.mp4"
    filepath = os.path.join(season_folder, filename)

    expected_size = get_content_length(url)
    # print(f"DEBUG: expected_size = {expected_size}")

    if os.path.exists(filepath):
        actual_size = os.path.getsize(filepath)
        # print(f"DEBUG: expected_size = {expected_size}, actual_size = {actual_size}")

        if actual_size >= expected_size * 0.99:
            messege = f"⏭ ✅ Уже есть (проверен размер): {filepath}"
            time.sleep(3)
            return messege
        else:
            os.remove(filepath)
            print(f"⚠️ Удалён файл с неправильным размером: {filepath} (был {actual_size} байт, ожидалось {expected_size} байт).")

    total = expected_size if expected_size and expected_size > 100 else None
    if total is None:
        print(f"⚠️ Неизвестный или маленький размер файла для {title}, прогресс не будет показываться.")
        time.sleep(3.0)

    print(f"🍀 Начинаем скачивание {title}")
    # print(f"DEBUG: URL = {url}")

    for attempt in range(1, retries + 1):
        try:
            response = requests.get(url, stream=True, timeout=60)
            # print(f"DEBUG: response.status_code = {response.status_code}")

            if response.status_code != 200:
                raise Exception(f"Ошибка HTTP: {response.status_code}")

            with open(filepath, 'wb') as file, tqdm(
                desc=f"{filename} (попытка {attempt})",
                total=total,
                unit='B',
                unit_scale=True,
                unit_divisor=1024,
                leave=False
            ) as bar:
                chunks_written = 0
                for chunk in response.iter_content(chunk_size=1024):
                    if chunk:
                        file.write(chunk)
                        bar.update(len(chunk))
                        chunks_written += 1
                # print(f"DEBUG: chunks_written = {chunks_written}")

            actual_size = os.path.getsize(filepath)
            # print(f"DEBUG: actual_size = {actual_size}")

            if total is not None and actual_size < total * 0.99:
                raise Exception(f"Размер меньше ожидаемого ({actual_size} < {total})")

            return f"✅ Скачано: {filepath}"

        except Exception as e:
            if attempt < retries:
                print(f"⚠️ Ошибка при скачивании {title}, попытка {attempt}/{retries}: {e}")
            else:
                return f"❌ Ошибка при загрузке {title}: {e}"


def parse_episodes(rss_path):
    tree = ET.parse(rss_path)
    root = tree.getroot()

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
        season_set.add(season_number)
        duration_seconds = parse_duration(duration_str)

        episodes.append((title, url, season_number, duration_seconds))

    return channel_title, sorted(season_set), episodes

def parse_seasons_input(raw_input: str) -> list[int]:
    """Парсит строку с номерами сезонов (например '1,3-5,7')."""
    seasons = set()
    for part in raw_input.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:  # диапазон
            try:
                start, end = map(int, part.split("-", 1))
                seasons.update(range(start, end + 1))
            except ValueError:
                continue
        else:
            if part.isdigit():
                seasons.add(int(part))
    return sorted(seasons)

def main():
    # rss_url = input("🔗 Введите RSS URL: ").strip()
    rss_path = "rss.xml"

    # Если нужно скачивать по URL:
    # print("⬇️ Загружаем RSS...")
    # response = requests.get(rss_url)
    # with open(rss_path, "wb") as f:
    #     f.write(response.content)
    # print("📂 RSS сохранён как rss.xml")

    title, seasons, all_episodes = parse_episodes(rss_path)

    print(f"\n🎬 Название: {title}")
    print(f"📅 Сезонов найдено: {len(seasons)} ({', '.join(map(str, seasons))})")

    raw_input_str = input(
        f"📥 Какие сезоны скачать? (например: 1,3-5,7): "
    ).strip()

    selected_seasons = parse_seasons_input(raw_input_str)

    if not selected_seasons:
        print("❌ Ошибка: не удалось распознать сезоны")
        return

    # Фильтруем эпизоды
    filtered = [
        (title, url, season)
        for title, url, season, duration in all_episodes
        if season in selected_seasons
    ]

    if not filtered:
        print("⚠️ Нет эпизодов для выбранных сезонов!")
        return

    print(f"\n📦 Эпизодов к загрузке: {len(filtered)}\n")

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [
            executor.submit(download_episode, title, url, season, retries=MAX_RETRIES)
            for title, url, season in filtered
        ]
        for future in as_completed(futures):
            print(future.result())

if __name__ == "__main__":
    main()
