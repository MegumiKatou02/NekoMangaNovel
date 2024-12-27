import os
import re
import requests

class TruyenDexImageDownloader:
    def __init__(self, logger_callback):
        self.logger_callback = logger_callback

    def fetch_chapters(self, manga_id):
        """Lấy danh sách các chapter của manga từ MangaDex API."""
        api_url = f"https://api.mangadex.org/manga/{manga_id}/aggregate?translatedLanguage[]=vi"
        response = requests.get(api_url)
        
        if response.status_code == 200:
            data = response.json()
            chapters = []
            
            for volume_number, volume_data in data.get('volumes', {}).items():
                for chapter_number, chapter_info in volume_data.get('chapters', {}).items():
                    chapters.append((volume_number, chapter_number, chapter_info['id'])) 
            return chapters
        else:
            self.logger_callback(f"Failed to fetch chapters. Status code: {response.status_code}")
            return []

    def fetch_images(self, chapter_id):
        api_url = f"https://api.mangadex.org/at-home/server/{chapter_id}"
        response = requests.get(api_url)
        
        if response.status_code == 200:
            data = response.json()
            base_url = data.get('baseUrl', '')
            chapter_hash = data.get('chapter', {}).get('hash', '')  # hash
            images = data.get('chapter', {}).get('data', [])
            
            return [f"{base_url}/data/{chapter_hash}/{image}" for image in images]
        else:
            self.logger_callback(f"Failed to fetch images for chapter {chapter_id}. Status code: {response.status_code}")
            return []

    def download_manga(self, manga_url):
        manga_id_match = re.search(r"/title/([a-f0-9\-]+)", manga_url)
        if not manga_id_match:
            self.logger_callback("Invalid manga URL.")
            return
    
        manga_id = manga_id_match.group(1)

        self.logger_callback(f"Starting download for manga: {manga_id}")

        chapters = self.fetch_chapters(manga_id)
        if not chapters:
            return

        manga_folder = os.path.join(os.getcwd(), f"manga_{manga_id}")
        os.makedirs(manga_folder, exist_ok=True)

        for volume, chapter, chapter_id in chapters:
            self.logger_callback(f"Downloading volume {volume}, chapter {chapter}...")

            images = self.fetch_images(chapter_id)
            if images:
                chapter_folder = os.path.join(manga_folder, f"volume_{volume}", f"chapter_{chapter}")
                os.makedirs(chapter_folder, exist_ok=True)

                for image_url in images:
                    self.download_image(image_url, chapter_folder)
            else:
                self.logger_callback(f"No images found for chapter {chapter}.")

        self.logger_callback(f"Download completed for manga: {manga_id}")

    def download_image(self, image_url, save_folder):
        try:
            response = requests.get(image_url)
            if response.status_code == 200:
                image_name = os.path.basename(image_url)
                image_path = os.path.join(save_folder, image_name)
                
                with open(image_path, 'wb') as f:
                    f.write(response.content)

                self.logger_callback(f"Downloaded image: {image_name}")
            else:
                self.logger_callback(f"Failed to download image from {image_url}. Status code: {response.status_code}")
        except Exception as e:
            self.logger_callback(f"Error downloading image: {e}")
