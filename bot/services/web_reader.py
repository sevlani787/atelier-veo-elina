import httpx
import re
import html
import asyncio
from typing import Optional
from bot.services.apify import apify_service

class WebReader:
    def __init__(self):
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3"
        }

    def clean_html(self, html_content: str) -> str:
        """Очищает HTML-код с помощью BeautifulSoup и преобразует его в качественный читаемый текст."""
        from bs4 import BeautifulSoup
        
        try:
            soup = BeautifulSoup(html_content, "html.parser")
        except Exception as e:
            print(f"[WEB_READER] Ошибка парсинга BeautifulSoup: {e}")
            return self._clean_html_regex(html_content)

        # 1. Удаляем ненужные теги
        ignored_tags = ["script", "style", "header", "footer", "nav", "noscript", "iframe", "head", "aside", "form", "svg"]
        for tag in soup(ignored_tags):
            tag.decompose()

        # 2. Удаляем элементы с классами или id, содержащими слова-шум
        noise_patterns = re.compile(
            r'(menu|nav|header|footer|sidebar|adsense|banner|social|share|comment|cookie|popup|modal|widget|promo|button-container)', 
            re.IGNORECASE
        )
        
        for tag in soup.find_all(True):
            if not hasattr(tag, "attrs") or tag.attrs is None:
                continue
                
            tag_id = tag.get("id")
            if tag_id:
                tag_id_str = " ".join(tag_id) if isinstance(tag_id, list) else str(tag_id)
                if noise_patterns.search(tag_id_str):
                    tag.decompose()
                    continue
            
            tag_classes = tag.get("class")
            if tag_classes:
                class_str = " ".join(tag_classes) if isinstance(tag_classes, list) else str(tag_classes)
                if noise_patterns.search(class_str):
                    tag.decompose()
                    continue

        # 3. Сохраняем переводы строк после блочных элементов
        block_tags = ["div", "p", "h1", "h2", "h3", "h4", "h5", "h6", "li", "tr", "section", "article"]
        for tag in soup.find_all(block_tags):
            tag.append('\n')

        text = soup.get_text()
        text = html.unescape(text)
        text = re.sub(r'[ \t]+', ' ', text)
        text = re.sub(r'\r\n', '\n', text)
        text = re.sub(r'\n\s*\n+', '\n\n', text)
        
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        cleaned = '\n'.join(lines)
        
        # Если очистка оказалась слишком агрессивной, откатываемся на регулярки
        if len(cleaned) < 50:
            return self._clean_html_regex(html_content)
            
        return cleaned

    def _clean_html_regex(self, html_content: str) -> str:
        """Резервный метод очистки HTML с помощью регулярных выражений."""
        text = re.sub(
            r'<(script|style|header|footer|nav|noscript|iframe|head|aside)[^>]*?>.*?</\1>', 
            ' ', 
            html_content, 
            flags=re.DOTALL | re.IGNORECASE
        )
        text = re.sub(r'<!--.*?-->', ' ', text, flags=re.DOTALL)
        text = re.sub(r'</?(div|p|h1|h2|h3|h4|h5|h6|li|tr|br|section|article)[^>]*?>', '\n', text, flags=re.IGNORECASE)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = html.unescape(text)
        text = re.sub(r'[ \t]+', ' ', text)
        text = re.sub(r'\r\n', '\n', text)
        text = re.sub(r'\n\s*\n+', '\n\n', text)
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        return '\n'.join(lines)

    async def read_url(self, url: str) -> str:
        """
        Пытается прочитать сайт напрямую через HTTP-запрос.
        В случае неудачи (Cloudflare, JS-защита, ошибки) обращается к Apify.
        """
        print(f"[WEB_READER] Попытка прямого скачивания {url}...")
        
        try:
            async with httpx.AsyncClient(timeout=15.0, headers=self.headers, follow_redirects=True) as client:
                response = await client.get(url)
                
                # Если ответ успешен и это HTML-страница
                if response.status_code == 200 and "text/html" in response.headers.get("content-type", "").lower():
                    html_content = response.text
                    
                    # Проверяем, не натолкнулись ли на страницу защиты Cloudflare или аналогичную заглушку
                    if "cloudflare" in html_content.lower() and ("ddos" in html_content.lower() or "checking your browser" in html_content.lower()):
                        print("[WEB_READER] Обнаружена защита Cloudflare. Переключаемся на Apify...")
                        return await self.scrape_via_apify(url)
                    
                    cleaned_text = self.clean_html(html_content)
                    if len(cleaned_text) < 150:
                        # Слишком короткий текст может говорить о том, что контент подгружается через JS
                        print("[WEB_READER] Прямой текст слишком короткий, возможно JS-рендеринг. Переключаемся на Apify...")
                        return await self.scrape_via_apify(url)
                        
                    # Ограничиваем длину текста для LLM
                    max_chars = 6000
                    if len(cleaned_text) > max_chars:
                        cleaned_text = cleaned_text[:max_chars] + "\n\n...[Контент обрезан из-за большого объема]..."
                        
                    return f"--- КОНТЕНТ САЙТА (Прямое чтение: {url}) ---\n\n{cleaned_text}"
                else:
                    print(f"[WEB_READER] HTTP ошибка {response.status_code} или неверный тип контента. Переключаемся на Apify...")
                    return await self.scrape_via_apify(url)
                    
        except Exception as e:
            print(f"[WEB_READER] Исключение при прямом скачивании ({e}). Переключаемся на Apify...")
            return await self.scrape_via_apify(url)

    async def scrape_via_apify(self, url: str) -> str:
        """Резервный метод: использование Apify для сайтов с защитой или JS-рендерингом."""
        if not apify_service.api_token:
            return "Не удалось прочитать сайт напрямую. Для обхода защиты требуется настроить API-токен Apify в .env."
            
        print(f"[WEB_READER] Запуск Apify Website Content Crawler для {url}...")
        
        # Конфигурируем запуск для Website Content Crawler
        actor_id = "apify~website-content-crawler"
        input_payload = {
            "startUrls": [{"url": url}],
            "maxCrawlPages": 1,
            "crawlerType": "cheerio", # Быстрый статический скрапер
            "proxyConfiguration": {
                "useApifyProxy": True,
                "apifyProxyGroups": ["RESIDENTIAL"]
            }
        }
        
        headers = {"Content-Type": "application/json"}
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # 1. Запуск
                run_url = f"{apify_service.base_url}/acts/{actor_id}/runs?token={apify_service.api_token}"
                response = await client.post(run_url, json=input_payload, headers=headers)
                if response.status_code not in (200, 201):
                    return f"Ошибка при запуске резервного скрапинга Apify: {response.status_code} | {response.text}"
                    
                run_data = response.json().get("data", {})
                run_id = run_data.get("id")
                dataset_id = run_data.get("defaultDatasetId")
                
                if not run_id or not dataset_id:
                    return "Ошибка запуска резервного скрапинга (нет ID)."
                    
                # 2. Поллинг
                status_url = f"{apify_service.base_url}/actor-runs/{run_id}?token={apify_service.api_token}"
                max_wait = 180
                elapsed = 0
                while elapsed < max_wait:
                    await asyncio.sleep(5)
                    elapsed += 5
                    status_resp = await client.get(status_url)
                    if status_resp.status_code == 200:
                        status = status_resp.json().get("data", {}).get("status")
                        if status == "SUCCEEDED":
                            break
                        elif status in ("FAILED", "ABORTED", "TIMED-OUT"):
                            return f"Резервный скрапинг Apify завершился с ошибкой: {status}."
                            
                # 3. Извлечение данных
                items_url = f"{apify_service.base_url}/datasets/{dataset_id}/items?token={apify_service.api_token}"
                items_resp = await client.get(items_url)
                if items_resp.status_code == 200:
                    items = items_resp.json()
                    if items:
                        first_item = items[0]
                        content = first_item.get("markdown") or first_item.get("text") or first_item.get("description") or ""
                        
                        content = content.strip()
                        if len(content) > 6000:
                            content = content[:6000] + "\n\n...[Контент обрезан]..."
                            
                        return f"--- КОНТЕНТ САЙТА (Через Apify: {url}) ---\n\n{content}"
                        
                    return "Резервный скрапинг завершился успешно, но контент страницы пуст."
                return f"Не удалось получить результаты резервного скрапинга: {items_resp.status_code}"
                
        except Exception as e:
            return f"Ошибка при выполнении резервного скрапинга Apify: {e}"

web_reader = WebReader()
