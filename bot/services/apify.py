import httpx
import asyncio
import re
from typing import Optional, List, Dict, Any
from bot.config import config

class ApifyService:
    def __init__(self):
        self.api_token = config.apify_api_token
        self.base_url = "https://api.apify.com/v2"

    def detect_platform(self, url: str) -> Optional[str]:
        url_lower = url.lower()
        if "instagram.com" in url_lower:
            return "instagram"
        elif "pinterest.com" in url_lower or "pin.it" in url_lower:
            return "pinterest"
        elif "youtube.com" in url_lower or "youtu.be" in url_lower:
            return "youtube"
        elif "twitter.com" in url_lower or "x.com" in url_lower:
            return "twitter"
        elif "facebook.com" in url_lower:
            return "facebook"
        elif "threads.net" in url_lower:
            return "threads"
        return None

    def get_actor_config(self, platform: str, url: str) -> Dict[str, Any]:
        """Возвращает ID актора и входные данные для запуска."""
        proxy_config = {"useApifyProxy": True}
        
        if platform == "instagram":
            return {
                "actor_id": "apify~instagram-scraper",
                "input": {
                    "directUrls": [url],
                    "resultsLimit": 5,
                    "scrapeType": "posts",
                    "proxyConfiguration": proxy_config
                }
            }
        elif platform == "pinterest":
            return {
                "actor_id": "fatihtahta~pinterest-scraper-search",
                "input": {
                    "startUrls": [{"url": url}],
                    "limit": 5,
                    "proxyConfiguration": proxy_config
                }
            }
        elif platform == "youtube":
            return {
                "actor_id": "streamers~youtube-scraper",
                "input": {
                    "startUrls": [{"url": url}],
                    "maxResults": 5,
                    "maxResultsShorts": 5,
                    "maxResultStreams": 5,
                    "proxyConfiguration": proxy_config
                }
            }
        elif platform == "twitter":
            return {
                "actor_id": "apidojo~tweet-scraper",
                "input": {
                    "startUrls": [{"url": url}],
                    "maxItems": 5,
                    "proxyConfiguration": proxy_config
                }
            }
        elif platform == "facebook":
            return {
                "actor_id": "apify~facebook-posts-scraper",
                "input": {
                    "startUrls": [{"url": url}],
                    "resultsLimit": 5,
                    "proxyConfiguration": proxy_config
                }
            }
        elif platform == "threads":
            # Извлекаем имя пользователя из URL (поддерживает threads.net/@username или threads.net/username)
            username_match = re.search(r'threads\.net/@?([a-zA-Z0-9_\.]+)', url)
            username = username_match.group(1) if username_match else ""
            return {
                "actor_id": "apify~threads-profile-api-scraper",
                "input": {
                    "usernames": [username] if username else [],
                    "maxPosts": 5,
                    "proxyConfiguration": proxy_config
                }
            }
        raise ValueError(f"Неподдерживаемая платформа: {platform}")

    async def scrape(self, url: str) -> Optional[str]:
        """
        Запускает скрапинг, опрашивает статус выполнения и возвращает структурированный текст результатов.
        """
        if not self.api_token:
            return "Ошибка: API-токен Apify не настроен в конфигурации."

        platform = self.detect_platform(url)
        if not platform:
            return None

        try:
            actor_cfg = self.get_actor_config(platform, url)
            actor_id = actor_cfg["actor_id"]
            input_payload = actor_cfg["input"]
        except Exception as e:
            return f"Ошибка конфигурации актора для {platform}: {e}"

        print(f"[APIFY] Запуск актора {actor_id} для {url}...")
        
        headers = {"Content-Type": "application/json"}
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            # 1. Запуск актора
            run_url = f"{self.base_url}/acts/{actor_id}/runs?token={self.api_token}"
            try:
                response = await client.post(run_url, json=input_payload, headers=headers)
                if response.status_code not in (200, 201):
                    # Если актор по умолчанию упал, пробуем twitter-scraper-lite в качестве запасного для twitter
                    if platform == "twitter" and actor_id == "apidojo~tweet-scraper":
                        actor_id = "apidojo~twitter-scraper-lite"
                        run_url = f"{self.base_url}/acts/{actor_id}/runs?token={self.api_token}"
                        response = await client.post(run_url, json=input_payload, headers=headers)
                    
                    if response.status_code not in (200, 201):
                        return f"Ошибка при запуске актора {actor_id}: {response.status_code} | {response.text}"
                
                run_data = response.json().get("data", {})
                run_id = run_data.get("id")
                dataset_id = run_data.get("defaultDatasetId")
                
                if not run_id or not dataset_id:
                    return f"Ошибка: не удалось получить ID запуска или датасета."
                
            except Exception as e:
                return f"Исключение при запуске задачи на Apify: {e}"

            # 2. Поллинг (опрос статуса)
            status_url = f"{self.base_url}/actor-runs/{run_id}?token={self.api_token}"
            max_wait_seconds = 180
            elapsed = 0
            interval = 5

            print(f"[APIFY] Задача запущена. ID запуска: {run_id}. Ожидание результатов...")
            while elapsed < max_wait_seconds:
                await asyncio.sleep(interval)
                elapsed += interval
                
                try:
                    status_resp = await client.get(status_url)
                    if status_resp.status_code == 200:
                        status_data = status_resp.json().get("data", {})
                        status = status_data.get("status")
                        
                        print(f"[APIFY] Статус задачи (прошло {elapsed} сек): {status}")
                        if status == "SUCCEEDED":
                            break
                        elif status in ("FAILED", "ABORTED", "TIMED-OUT"):
                            return f"Скрапинг завершился неудачно со статусом: {status}."
                    else:
                        print(f"[APIFY] Ошибка проверки статуса: {status_resp.status_code}")
                except Exception as e:
                    print(f"[APIFY] Ошибка при опросе статуса: {e}")

            if elapsed >= max_wait_seconds:
                return f"Ошибка: Превышено время ожидания скрапинга ({max_wait_seconds} сек)."

            # 3. Получение элементов датасета
            items_url = f"{self.base_url}/datasets/{dataset_id}/items?token={self.api_token}"
            try:
                items_resp = await client.get(items_url)
                if items_resp.status_code != 200:
                    return f"Ошибка при получении результатов: {items_resp.status_code} | {items_resp.text}"
                
                items = items_resp.json()
                if not items:
                    return "Скрапинг завершился успешно, но аккаунт пуст или закрыт (данные не найдены)."
                
                return self.format_results(platform, items)
            except Exception as e:
                return f"Ошибка при разборе результатов: {e}"

    def format_results(self, platform: str, items: List[Dict[str, Any]]) -> str:
        """Форматирует сырые элементы датасета в читаемый текстовый отчет."""
        formatted_lines = [f"--- РЕЗУЛЬТАТЫ СКРАПИНГА ({platform.upper()}) ---"]
        
        for idx, item in enumerate(items[:5], 1):
            text_content = ""
            url = item.get("url") or item.get("link") or ""
            stats = []

            if platform == "instagram":
                text_content = item.get("caption") or ""
                likes = item.get("likesCount")
                comments = item.get("commentsCount")
                if likes is not None: stats.append(f"Лайки: {likes}")
                if comments is not None: stats.append(f"Комментарии: {comments}")
            
            elif platform == "pinterest":
                title = item.get("title") or ""
                desc = item.get("description") or ""
                text_content = f"Заголовок: {title}\nОписание: {desc}"
            
            elif platform == "youtube":
                title = item.get("title") or ""
                desc = item.get("description") or item.get("text") or ""
                text_content = f"Название: {title}\nОписание: {desc}"
                views = item.get("viewCount")
                if views is not None: stats.append(f"Просмотры: {views}")
            
            elif platform == "twitter":
                text_content = item.get("fullText") or item.get("text") or ""
                retweets = item.get("retweetCount")
                likes = item.get("likeCount")
                if likes is not None: stats.append(f"Лайки: {likes}")
                if retweets is not None: stats.append(f"Ретвиты: {retweets}")
            
            elif platform == "facebook":
                text_content = item.get("text") or ""
                likes = item.get("likes")
                if likes is not None: stats.append(f"Лайки: {likes}")
            
            elif platform == "threads":
                text_content = item.get("text") or item.get("caption") or ""
                likes = item.get("likesCount")
                if likes is not None: stats.append(f"Лайки: {likes}")

            text_content = text_content.strip()
            if len(text_content) > 600:
                text_content = text_content[:600] + "..."

            formatted_lines.append(f"\nПубликация #{idx}:")
            if url:
                formatted_lines.append(f"Ссылка: {url}")
            if stats:
                formatted_lines.append(f"Статистика: {', '.join(stats)}")
            if text_content:
                formatted_lines.append(f"Контент:\n{text_content}")
            
            formatted_lines.append("-" * 30)

        return "\n".join(formatted_lines)

apify_service = ApifyService()
