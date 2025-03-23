import json
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

chrome_options = Options()
chrome_options.add_argument("--headless")
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--no-sandbox")


def json_dump(href_list: list) -> bool:
    try:
        with open("Data/href.json", "w", encoding="utf-8") as file:
            json.dump(href_list, file, ensure_ascii=False, indent=4)
        return True
    except FileNotFoundError:
        return False



def scroll_to_bottom(driver, max_scrolls=10):
    """Плавный скроллинг с проверкой появления новых элементов"""
    last_height = driver.execute_script("return document.body.scrollHeight")
    scroll_attempts = 0
    collected = 0

    while scroll_attempts < max_scrolls:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)  # Увеличенное время для загрузки

        # Ждем появления новых элементов
        try:
            WebDriverWait(driver, 10).until(
                lambda d: len(d.find_elements(By.XPATH, '//a[contains(@href, "/video")]')) > collected
            )
            collected = len(driver.find_elements(By.XPATH, '//a[contains(@href, "/video")]'))
        except:
            pass

        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height
        scroll_attempts += 1


def parse_vk_video(hashtag: str) -> tuple[bool, list[str]]:
    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=chrome_options
    )
    href_list = []

    try:
        driver.get(f"https://vkvideo.ru/?q={hashtag}")

        # Ожидание первичной загрузки
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.XPATH, '//a[contains(@href, "/video")]'))
        )

        # Динамический скроллинг
        scroll_to_bottom(driver)

        # Сбор всех видео-ссылок
        video_links = driver.find_elements(By.XPATH, '//a[contains(@href, "/video")]')

        for i, link in enumerate(video_links):
            try:
                url = link.get_attribute('href')

                if url not in [x['url'] for x in href_list]:
                    if url[25] != '@' and 'playlist' not in url and 'club' not in url:
                        href_list.append({
                        "id": i,
                        "title": url[19:],
                        "url": url
                    })
            except Exception as e:
                print(f"Ошибка при обработке элемента {i}: {str(e)}")
                continue

            finally:
                if len(href_list) >= 10:
                    json_dump(href_list)
                    return True, href_list

    except Exception as e:
        print(f"Критическая ошибка: {e}")
        return False, href_list
    finally:
        driver.quit()
    json_dump(href_list)
    return True, href_list