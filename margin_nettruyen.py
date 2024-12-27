import os
import requests
import cloudscraper
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import concurrent.futures
import time
from pathlib import Path
import re
import random
import json
import logging
from queue import Queue
from threading import Lock
import fake_useragent
from datetime import datetime

class MangaDownloader:
    def __init__(self):
        # Thiết lập logging
        self.setup_logging()
        
        # Khởi tạo các queue và lock
        self.download_queue = Queue()
        self.failed_queue = Queue()
        self.lock = Lock()
        
        # Khởi tạo fake user agent
        self.ua = fake_useragent.UserAgent()
        
        # Danh sách proxy (thêm proxy của bạn vào đây)
        self.proxies = [
            # 'http://proxy1:port',
            # 'http://proxy2:port',
        ]
        
        # Load cookies và progress nếu có
        self.load_cookies()
        self.load_progress()
        
        # Khởi tạo cloudscraper
        self.scraper = cloudscraper.create_scraper(
            browser={
                'browser': 'chrome',
                'platform': 'windows',
                'mobile': False
            }
        )
        
    def setup_logging(self):
        """Thiết lập logging system"""
        logging.basicConfig(
            filename=f'manga_downloader_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log',
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)

    def load_cookies(self):
        """Load cookies từ file nếu có"""
        try:
            with open('cookies.json', 'r') as f:
                self.cookies = json.load(f)
        except FileNotFoundError:
            self.cookies = {}

    def load_progress(self):
        """Load tiến trình download từ file nếu có"""
        self.progress = {}
        try:
            with open('progress.json', 'r') as f:
                self.progress = json.load(f)
        except FileNotFoundError:
            pass

    def save_progress(self, chapter_url, status):
        """Lưu tiến trình download"""
        with self.lock:
            self.progress[chapter_url] = status
            with open('progress.json', 'w') as f:
                json.dump(self.progress, f)

    def get_headers(self):
        """Tạo headers ngẫu nhiên"""
        return {
            'User-Agent': self.ua.random,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'max-age=0',
        }

    def get_proxy(self):
        """Lấy proxy ngẫu nhiên nếu có"""
        return random.choice(self.proxies) if self.proxies else None

    def download_with_retry(self, url, headers=None, is_image=False, max_retries=5, initial_delay=3):
        """Download với retry và rotation"""
        if headers is None:
            headers = self.get_headers()

        for attempt in range(max_retries):
            try:
                # Delay ngẫu nhiên
                time.sleep(initial_delay + random.uniform(1, 3))
                
                # Chọn proxy nếu có
                proxy = self.get_proxy()
                
                # Sử dụng cloudscraper cho HTML và requests thường cho ảnh
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
                
                # Cập nhật cookies
                self.cookies.update(response.cookies.get_dict())
                
                return response

            except requests.exceptions.RequestException as e:
                self.logger.error(f"Attempt {attempt + 1} failed for {url}: {str(e)}")
                
                if attempt == max_retries - 1:
                    raise
                
                if hasattr(response, 'status_code') and response.status_code == 429:
                    wait_time = initial_delay * (2 ** attempt)
                    self.logger.warning(f"Rate limited, waiting {wait_time}s...")
                    time.sleep(wait_time)
                    
                # Thử đổi proxy nếu có lỗi
                if proxy and self.proxies:
                    self.proxies.remove(proxy)
                    if not self.proxies:
                        self.logger.error("Hết proxy khả dụng!")
                        raise
                
                continue
                
        return None

    def sanitize_filename(self, filename):
        """Làm sạch tên file"""
        # Loại bỏ ký tự đặc biệt và khoảng trắng thừa
        filename = re.sub(r'[\\/*?:"<>|]', "", filename)
        filename = re.sub(r'\s+', " ", filename)
        return filename.strip()

    def download_image(self, img_url, referer, save_path):
        """Download một ảnh"""
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
            # Thêm vào queue thất bại để thử lại sau
            self.failed_queue.put((img_url, referer, save_path))
            return False

    def process_chapter(self, chapter_url, manga_folder):
        """Xử lý một chương truyện"""
        # Kiểm tra tiến trình
        if chapter_url in self.progress and self.progress[chapter_url] == 'completed':
            self.logger.info(f"Chapter already downloaded: {chapter_url}")
            return

        try:
            response = self.download_with_retry(chapter_url)
            if not response:
                return

            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Lấy tên chương
            chapter_name = soup.select_one('h1') or urlparse(chapter_url).path.split('/')[-1]
            chapter_name = str(chapter_name.text if hasattr(chapter_name, 'text') else chapter_name)
            chapter_name = self.sanitize_filename(chapter_name)
            
            chapter_folder = os.path.join(manga_folder, chapter_name)
            os.makedirs(chapter_folder, exist_ok=True)
            
            # Tìm ảnh
            images = soup.select('img.lazy')
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
                
                # Thêm delay nhỏ giữa các ảnh
                time.sleep(random.uniform(0.5, 1.5))
            
            # Kiểm tra hoàn thành
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
            
            # Lấy tên truyện
            manga_name = soup.select_one('h1[itemprop="name"]')
            manga_name = manga_name.text if manga_name else "manga"
            manga_name = self.sanitize_filename(manga_name)
            manga_folder = os.path.join(os.getcwd(), manga_name)
            os.makedirs(manga_folder, exist_ok=True)
            
            # Lấy danh sách chapter
            chapters = soup.select('div.works-chapter-list a[href]')
            chapter_urls = [urljoin(manga_url, chapter.get('href')) for chapter in chapters]
            
            # Download các chapter
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                futures = [
                    executor.submit(self.process_chapter, chapter_url, manga_folder)
                    for chapter_url in chapter_urls
                ]
                concurrent.futures.wait(futures)
            
            # Thử lại các download thất bại
            self.retry_failed()
            
            # Lưu cookies
            with open('cookies.json', 'w') as f:
                json.dump(self.cookies, f)
            
            self.logger.info(f"Download completed: {manga_folder}")
            
        except Exception as e:
            self.logger.error(f"Error: {str(e)}")
            print("Please check the URL!")

if __name__ == "__main__":
    downloader = MangaDownloader()
    url = input("Enter manga URL: ")
    downloader.download_manga(url)