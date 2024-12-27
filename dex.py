import os
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import concurrent.futures
import time
from pathlib import Path
import re
import random

class MangaDownloader:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/105.0.0.0 Safari/537.36'
        }
        self.session = requests.Session()
        
    def sanitize_filename(self, filename):
        """Làm sạch tên file không hợp lệ"""
        # Loại bỏ ký tự đặc biệt và khoảng trắng thừa
        filename = re.sub(r'[\\/*?:"<>|]', "", filename)
        filename = re.sub(r'\s+', " ", filename)
        return filename.strip()
    
    def download_with_retry(self, url, headers, max_retries=3, initial_delay=5):
        """Tải với cơ chế retry và delay"""
        for attempt in range(max_retries):
            try:
                # Thêm delay ngẫu nhiên để tránh phát hiện bot
                time.sleep(initial_delay + random.uniform(1, 3))
                response = self.session.get(url, headers=headers, timeout=30)
                response.raise_for_status()
                return response
            except requests.exceptions.RequestException as e:
                if attempt == max_retries - 1:
                    raise
                if response.status_code == 429:
                    # Tăng thời gian chờ nếu bị chặn
                    wait_time = initial_delay * (2 ** attempt)
                    print(f"[!] Bị giới hạn request, chờ {wait_time}s...")
                    time.sleep(wait_time)
                continue
        return None

    def download_image(self, img_url, referer, save_path):
        """Tải một ảnh với headers phù hợp"""
        headers = self.headers.copy()
        headers.update({
            'Referer': referer,
            'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br'
        })
        
        try:
            response = self.download_with_retry(img_url, headers)
            if response:
                with open(save_path, 'wb') as f:
                    f.write(response.content)
                print(f"[✓] Đã tải: {os.path.basename(save_path)}")
                return True
        except Exception as e:
            print(f"[!] Lỗi khi tải {img_url}: {str(e)}")
            return False

    def process_chapter(self, chapter_url, manga_folder):
        """Xử lý và tải ảnh cho một chương"""
        try:
            response = self.download_with_retry(chapter_url, self.headers)
            if not response:
                return
                
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Lấy và làm sạch tên chương
            chapter_name = soup.select_one('h1') or urlparse(chapter_url).path.split('/')[-1]
            chapter_name = str(chapter_name.text if hasattr(chapter_name, 'text') else chapter_name)
            chapter_name = self.sanitize_filename(chapter_name)
            
            chapter_folder = os.path.join(manga_folder, chapter_name)
            os.makedirs(chapter_folder, exist_ok=True)
            
            # Tìm tất cả ảnh trong chương
            images = soup.select('img.lazy')
            for idx, img in enumerate(images, 1):
                img_url = img.get('src') or img.get('data-src')
                if not img_url:
                    continue
                    
                img_url = urljoin(chapter_url, img_url)
                file_ext = os.path.splitext(urlparse(img_url).path)[1] or '.jpg'
                save_path = os.path.join(chapter_folder, f"{idx:03d}{file_ext}")
                
                self.download_image(img_url, chapter_url, save_path)
                # Thêm delay nhỏ giữa các ảnh
                time.sleep(random.uniform(0.5, 1.5))
                
            print(f"[✓] Hoàn thành chương: {chapter_name}")
        except Exception as e:
            print(f"[!] Lỗi khi xử lý chương {chapter_url}: {str(e)}")

    def download_manga(self, manga_url):
        """Tải toàn bộ truyện từ URL chính"""
        try:
            print(f"[*] Bắt đầu tải truyện từ: {manga_url}")
            
            response = self.download_with_retry(manga_url, self.headers)
            if not response:
                return
                
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Lấy và làm sạch tên truyện
            manga_name = soup.select_one('h1[itemprop="name"]')
            manga_name = manga_name.text if manga_name else "manga"
            manga_name = self.sanitize_filename(manga_name)
            manga_folder = os.path.join(os.getcwd(), manga_name)
            os.makedirs(manga_folder, exist_ok=True)
            
            # Lấy danh sách các chương
            chapters = soup.select('div.works-chapter-list a[href]')
            chapter_urls = [urljoin(manga_url, chapter.get('href')) for chapter in chapters]
            
            # Giảm số lượng workers để tránh quá tải
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                futures = [
                    executor.submit(self.process_chapter, chapter_url, manga_folder)
                    for chapter_url in chapter_urls
                ]
                concurrent.futures.wait(futures)
            
            print(f"[✓] Hoàn thành! Truyện được lưu tại:\n{manga_folder}")
            
        except Exception as e:
            print(f"[!] Lỗi: {str(e)}")
            print("Vui lòng kiểm tra lại URL!")

# Sử dụng
if __name__ == "__main__":
    downloader = MangaDownloader()
    url = input("Nhập URL truyện: ")
    downloader.download_manga(url)