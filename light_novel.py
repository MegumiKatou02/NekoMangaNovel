from bs4 import BeautifulSoup
import re
import requests
import os

class LightNovel:
    def __init__(self, logger_callback=None):
        self.logger_callback = logger_callback or print
        self.domain = "ln.hako.vn"

    def setup_domain(self, domain):
        self.domain = domain

    def download_lightNovel(self, light_novel_url):
        print(self.domain)
        ln_folder = os.path.join(os.getcwd(), "LightNovel")
        # os.makedirs(ln_folder, exist_ok=True)

        try:
            os.makedirs(ln_folder, exist_ok=True)
        except PermissionError:
            self.logger.error(f"Permission denied when creating directory: {ln_folder}")

        response = requests.get(light_novel_url)
        soup = BeautifulSoup(response.text, 'html.parser')

        list_items = soup.find_all(class_='chapter-name')

        for item in list_items:
            link = item.find('a')
            if link:
                title = link.get('title')
                title = re.sub(r'[\/:*?"<>|]', '', title) 

                chapter_url = f"https://{self.domain}" + link.get('href')
                self.logger_callback(f"Downloading chapter: {title} - URL: {chapter_url}")

                chapter_response = requests.get(chapter_url)
                chapter_soup = BeautifulSoup(chapter_response.text, 'html.parser')

                filename = os.path.join(ln_folder, f"{title}.txt")
                with open(filename, 'w', encoding='utf-8') as file:
                    txt = f"{title}\n\n"
                    for element in chapter_soup.find_all(id=True):
                        try:
                            id_num = int(element['id']) 
                            txt += element.get_text() + "\n\n"
                        except ValueError:
                            pass
                    file.write(txt)

                    self.logger_callback(f"Saved to: {filename}")
            else:
                self.logger_callback("No link found for chapter.")