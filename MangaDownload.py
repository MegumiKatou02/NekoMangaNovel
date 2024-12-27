import os
import requests
import cloudscraper
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import concurrent.futures
import time
import re
import random
import json
import logging
from queue import Queue
from threading import Lock
import fake_useragent
from datetime import datetime

class MangaDownloader:
    def __init__(self, logger_callback=None):
        self.image_select = "img.lozad"
        self.chapters_select = ".col-xs-5.chapter a[href]" #nettruyen auto :3

        self.setup_logging(logger_callback)
        
        self.download_queue = Queue()
        self.failed_queue = Queue()
        self.lock = Lock()
        
        self.ua = fake_useragent.UserAgent()
        
        self.proxies = []
        
        self.load_cookies()
        self.load_progress()
        
        self.scraper = cloudscraper.create_scraper(
            browser={
                'browser': 'chrome',
                'platform': 'windows',
                'mobile': False
            }
        )
    def setup_website(self, option: str): 
        if(option == 'Nettruyen'):
            self.image_select = "img.lozad"
            self.chapters_select = ".col-xs-5.chapter a[href]"
        if(option == 'TruyenQQ'):
            self.image_select = "img.lazy"
            self.chapters_select = "div.works-chapter-list a[href]"
        
        
    def setup_logging(self, callback=None):
        class CallbackHandler(logging.Handler):
            def __init__(self, callback):
                super().__init__()
                self.callback = callback

            def emit(self, record):
                if self.callback:
                    self.callback(self.format(record))

        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        
        self.logger.handlers = []
        
        file_handler = logging.FileHandler(
            f'manga_downloader_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log', encoding="utf-8"
        )
        file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        self.logger.addHandler(file_handler)
        
        if callback:
            callback_handler = CallbackHandler(callback)
            callback_handler.setFormatter(logging.Formatter('%(message)s'))
            self.logger.addHandler(callback_handler)

    def load_cookies(self):
        try:
            with open('cookies.json', 'r') as f:
                self.cookies = json.load(f)
        except FileNotFoundError:
            self.cookies = {}

    def load_progress(self):
        self.progress = {}
        try:
            with open('progress.json', 'r') as f:
                self.progress = json.load(f)
        except FileNotFoundError:
            pass

    def save_progress(self, chapter_url, status):
        with self.lock:
            self.progress[chapter_url] = status
            with open('progress.json', 'w') as f:
                json.dump(self.progress, f)

    def get_headers(self):
        return {
            'User-Agent': self.ua.random,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'max-age=0',
        }

    def get_proxy(self):
        return random.choice(self.proxies) if self.proxies else None

    def download_with_retry(self, url, headers=None, is_image=False, max_retries=5, initial_delay=3):
        if headers is None:
            headers = self.get_headers()

        response = None
        for attempt in range(max_retries):
            try:
                time.sleep(initial_delay + random.uniform(1, 3))
                
                proxy = self.get_proxy()
                
                if is_image:
                    response = requests.get(
                        url,
                        headers=headers,
                        proxies={'http': proxy, 'https': proxy} if proxy else None,
                        timeout=30,
                        cookies=self.cookies
                    )
                else:
                    response = self.scraper.get(
                        url,
                        headers=headers,
                        proxies={'http': proxy, 'https': proxy} if proxy else None,
                        cookies=self.cookies
                    )

                response.raise_for_status()
                
                self.cookies.update(response.cookies.get_dict())
                
                return response

            except requests.exceptions.RequestException as e:
                self.logger.error(f"Attempt {attempt + 1} failed for {url}: {str(e)}")
                
                if attempt == max_retries - 1:
                    raise
                
                if response and response.status_code == 429:
                    wait_time = initial_delay * (2 ** attempt)
                    self.logger.warning(f"Rate limited, waiting {wait_time}s...")
                    time.sleep(wait_time)
                    
                if proxy and self.proxies:
                    self.proxies.remove(proxy)
                    if not self.proxies:
                        self.logger.error("Hết proxy khả dụng!")
                        raise
                
                continue
                
        return None

    def sanitize_filename(self, filename):
        filename = re.sub(r'[\\/*?:"<>|]', "", filename)
        filename = re.sub(r'\s+', " ", filename)
        return filename.strip()

    def download_image(self, img_url, referer, save_path):
        headers = self.get_headers()
        headers.update({
            'Referer': referer,
            'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8'
        })
        
        try:
            response = self.download_with_retry(img_url, headers, is_image=True)
            if response:
                with open(save_path, 'wb') as f:
                    f.write(response.content)
                self.logger.info(f"Downloaded: {os.path.basename(save_path)}")
                return True
        except Exception as e:
            self.logger.error(f"Error downloading {img_url}: {str(e)}")
            self.failed_queue.put((img_url, referer, save_path))
            return False

    def process_chapter(self, chapter_url, manga_folder):
        """Xử lý một chương truyện"""
        if chapter_url in self.progress and self.progress[chapter_url] == 'completed':
            self.logger.info(f"Chapter already downloaded: {chapter_url}")
            return

        try:
            response = self.download_with_retry(chapter_url)
            if not response:
                return

            soup = BeautifulSoup(response.text, 'html.parser')
            
            chapter_name = soup.select_one('h1') or urlparse(chapter_url).path.split('/')[-1]
            chapter_name = str(chapter_name.text if hasattr(chapter_name, 'text') else chapter_name)
            chapter_name = self.sanitize_filename(chapter_name)
            
            chapter_folder = os.path.join(manga_folder, chapter_name)
            os.makedirs(chapter_folder, exist_ok=True)
            
            images = soup.select(self.image_select)
            total_images = len(images)
            downloaded_images = 0
            
            for idx, img in enumerate(images, 1):
                img_url = img.get('src') or img.get('data-src')
                if not img_url:
                    continue
                    
                img_url = urljoin(chapter_url, img_url)
                file_ext = os.path.splitext(urlparse(img_url).path)[1] or '.jpg'
                save_path = os.path.join(chapter_folder, f"{idx:03d}{file_ext}")
                
                if os.path.exists(save_path):
                    downloaded_images += 1
                    continue
                
                if self.download_image(img_url, chapter_url, save_path):
                    downloaded_images += 1
                
                time.sleep(random.uniform(0.5, 1.5))
            
            if downloaded_images == total_images:
                self.save_progress(chapter_url, 'completed')
                self.logger.info(f"Completed chapter: {chapter_name}")
            else:
                self.save_progress(chapter_url, 'incomplete')
                self.logger.warning(f"Incomplete chapter: {chapter_name} ({downloaded_images}/{total_images})")
                
        except Exception as e:
            self.logger.error(f"Error processing chapter {chapter_url}: {str(e)}")
            self.failed_queue.put((chapter_url, manga_folder))

    def retry_failed(self):
        """Thử lại các download thất bại"""
        while not self.failed_queue.empty():
            try:
                item = self.failed_queue.get()
                if len(item) == 2:  # chapter
                    chapter_url, manga_folder = item
                    self.process_chapter(chapter_url, manga_folder)
                else:  # image
                    img_url, referer, save_path = item
                    self.download_image(img_url, referer, save_path)
            except Exception as e:
                self.logger.error(f"Error in retry: {str(e)}")
            finally:
                self.failed_queue.task_done()

    def download_manga(self, manga_url):
        """Download toàn bộ manga"""
        try:
            self.logger.info(f"Starting download from: {manga_url}")
            
            response = self.download_with_retry(manga_url)
            if not response:
                return
                
            soup = BeautifulSoup(response.text, 'html.parser')
            
            manga_name = soup.select_one('h1[itemprop="name"]')
            manga_name = manga_name.text if manga_name else "manga"
            manga_name = self.sanitize_filename(manga_name)
            manga_folder = os.path.join(os.getcwd(), manga_name)
            os.makedirs(manga_folder, exist_ok=True)
            
            chapters = soup.select(self.chapters_select)
            chapter_urls = [urljoin(manga_url, chapter.get('href')) for chapter in chapters]
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                futures = [
                    executor.submit(self.process_chapter, chapter_url, manga_folder)
                    for chapter_url in chapter_urls
                ]
                concurrent.futures.wait(futures)
            
            self.retry_failed()
            
            with open('cookies.json', 'w') as f:
                json.dump(self.cookies, f)
            
            self.logger.info(f"Download completed: {manga_folder}")
            
        except Exception as e:
            self.logger.error(f"Error: {str(e)}")
            raise