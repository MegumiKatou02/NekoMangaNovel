from bs4 import BeautifulSoup
import re
import requests
import os

class LightNovel:
    def __init__(self, logger_callback=None):
        self.logger_callback = logger_callback

    def download_lightNovel(self, light_novel_url):
        ln_folder = os.path.join(os.getcwd(), "LightNovel")
        os.makedirs(ln_folder, exist_ok=True)

        response = requests.get(light_novel_url)
        soup = BeautifulSoup(response.text, 'html.parser')

        list_items = soup.find_all(class_='chapter-name')

        for item in list_items:
            link = item.find('a')
            if link:
                title = link.get('title')
                title = re.sub(r'[\/:*?"<>|]', '', title) 

                chapter_url = "https://ln.hako.vn" + link.get('href')
                print(f"Downloading chapter: {title} - URL: {chapter_url}")

                chapter_response = requests.get(chapter_url)
                chapter_soup = BeautifulSoup(chapter_response.text, 'html.parser')

                filename = os.path.join(ln_folder, f"{title}.txt")
                with open(filename, 'w', encoding='utf-8') as file:
                    txt = f"{title}\n\n"  # Tiêu đề chương
                    for element in chapter_soup.find_all(id=True):
                        try:
                            id_num = int(element['id']) 
                            txt += element.get_text() + "\n\n"
                        except ValueError:
                            pass
                    file.write(txt)

                    print(f"Saved to: {filename}")
            else:
                print("No link found for chapter.")

# if __name__ == "__main__":
#     ln_url = 'https://ln.hako.vn/truyen/11727-the-villainess-who-only-had-100-days-to-live-had-fun-every-day'  # Thay URL của bạn vào đây
#     light_novel = LightNovel()
#     light_novel.download_lightNovel(ln_url)