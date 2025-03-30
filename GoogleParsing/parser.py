import asyncio
import time
import random
import json
import os, datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import undetected_chromedriver as uc

from WebApp.logger.log_cfg import logger

class GoogleBot:
    def __init__(self, user_agent=None, headless=True):
        self.browsers = [
            {"name": "Chrome", "versions": ["91.0.4472.124", "93.0.4577.82", "95.0.4638.54"]},
            {"name": "Firefox", "versions": ["89.0", "92.0", "93.0"]},
            {"name": "Safari", "versions": ["14.0", "15.0", "13.1"]},
            {"name": "Edge", "versions": ["91.0.864.59", "92.0.902.62", "93.0.961.52"]},
            {"name": "Opera", "versions": ["76.0.4017.94", "78.0.4093.31", "80.0.4170.34"]}
        ]

        self.operating_systems = [
            {"name": "Windows NT 10.0", "versions": ["Win64; x64", "Win32"]},
            {"name": "Macintosh; Intel Mac OS X", "versions": ["10_15_7", "10_14_6", "10_13_6"]},
            {"name": "X11", "versions": ["Linux x86_64", "Linux i686"]},
            {"name": "Android", "versions": ["10", "11", "12"]},
            {"name": "iPhone", "versions": ["iOS 14_6", "iOS 15_0", "iOS 13_5"]}
        ]

        self.languages = [
            "en-US", "en-GB", "fr-FR", "de-DE", "ru-RU", "es-ES", "it-IT", "pt-PT"
        ]

        self.devices = [
            "Mobile", "Desktop"
        ]
        self.chrome_options = uc.ChromeOptions()
        if headless:
            self.chrome_options.add_argument("--headless")  # для работы без интерфейса

        self.chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        # self.chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        # self.chrome_options.add_experimental_option("useAutomationExtension", False)
        self.chrome_options.add_argument("--window-size=1920,1080")  # Добавить!

        self.chrome_options.add_argument("--no-sandbox")
        self.chrome_options.add_argument("--disable-gpu")
        self.chrome_options.add_argument("--disable-dev-shm-usage")
        self.chrome_options.add_argument("--remote-debugging-port=9222")
        self.generate()

        self.driver = uc.Chrome(options=self.chrome_options)
        self._bypass_bot_detection()  # Добавить!

    def generate(self):
        browser = random.choice(self.browsers)
        os = random.choice(self.operating_systems)
        language = random.choice(self.languages)
        device = random.choice(self.devices)

        browser_name = browser["name"]
        browser_version = random.choice(browser["versions"])
        os_name = os["name"]
        os_version = random.choice(os["versions"])

        if device == "Mobile":
            user_agent = f"Mozilla/5.0 ({os_name} {os_version}) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{browser_version} Mobile Safari/537.36"
        else:
            user_agent = f"Mozilla/5.0 ({os_name} {os_version}) AppleWebKit/537.36 (KHTML, like Gecko) {browser_name}/{browser_version} Safari/537.36"

        user_agent += f" Accept-Language: {language}"
        self.chrome_options.add_argument(f"user-agent={user_agent}")
        return user_agent

    def _wait_for_element(self, by, value, timeout = random.randint(2, 6)):
        """Ожидаем появления элемента на странице."""
        wait = WebDriverWait(self.driver, timeout)
        return wait.until(EC.element_to_be_clickable((by, value)))

    def _bypass_bot_detection(self):
        """Убирает navigator.webdriver и другие параметры, которые палят бота"""
        self.driver.execute_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )

    def save_html_page(self, driver):
        try:
            print("сохраняем")
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            logger.info(f"сохраняем html {timestamp}")
            file_path = f"Data/page_{timestamp}.html"
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            logger.info(f"HTML страницы сохранён в {file_path}")
            print("сохранили")
        except Exception as e:
            print(e)
            logger.error(f"Ошибка при сохранении HTML страницы: {e}")

    def save_start_html_page(self, driver):
        try:
            print("сохраняем")
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            logger.info(f"сохраняем html {timestamp}")
            file_path = f"Data/page.html"
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            logger.info(f"HTML страницы сохранён в {file_path}")
            print("сохранили")
        except Exception as e:
            print(e)
            logger.error(f"Ошибка при сохранении HTML страницы: {e}")

    async def _get_random_sleep(self):
        """Случайная задержка, чтобы имитировать поведение реального пользователя."""
        await asyncio.sleep(random.uniform(0.9, 3.5))

    async def open_google(self):
        """Открывает главную страницу Google."""
        self.driver.get("https://www.google.com")
        await self._get_random_sleep()

    def apply_vk_filter(self):
        """Применяет фильтр для поиска только на vk.com и нажимает на кнопку 'Инструменты' рядом с поисковой строкой."""
        try:
            # Ожидаем появления элемента с кнопкой "Инструменты" рядом с поисковой строкой
            tools_button = self._wait_for_element(By.XPATH,
                                                  "//div[@class='T7Ko6']//div[@class='BaegVc YmvwI' and @id='hdtb-tls']")

            # Прокручиваем страницу до кнопки "Инструменты"
            self.driver.execute_script("arguments[0].scrollIntoView(true);", tools_button)

            # Кликаем по кнопке "Инструменты"
            tools_button.click()
            print("Кнопка 'Инструменты' нажата.")

            # Ожидаем появления элемента с выпадающим меню
            filter_menu = self._wait_for_element(By.XPATH, "//div[@jsname='V68bde']")

            # Ожидаем, пока меню откроется
            self._wait_for_element(By.XPATH, "//g-menu-item//a[contains(text(), 'vk.com')]")

            # Прокручиваем страницу до элемента фильтра
            self.driver.execute_script("arguments[0].scrollIntoView(true);", filter_menu)

            # Кликаем по элементу фильтра "vk.com"
            vk_filter = self.driver.find_element(By.XPATH, "//g-menu-item//a[contains(text(), 'vk.com')]")
            vk_filter.click()
            print("Фильтр vk.com применен.")
            self._get_random_sleep()  # Задержка после клика
        except Exception as e:
            print(f"Ошибка при применении фильтра 'vk.com': {e}")


    def accept_cookies(self):
        """Принять cookies, если появляется окно."""
        try:
            agree_button = self._wait_for_element(By.XPATH, "//div[text()='Отклонить все']")
            agree_button.click()
            print("Кнопка 'Принять все' нажата.")
        except Exception as e:
            print(f"Ошибка при поиске кнопки 'Принять все': {e}")

    async def search(self, search_query):
        """Выполняет поиск по запросу."""
        search_box = self.driver.find_element(By.NAME, "q")
        search_box.send_keys(search_query + " вк клипы")
        await self._get_random_sleep()
        search_box.send_keys(Keys.RETURN)
        await self._get_random_sleep()

    def go_to_short_videos_section(self):
        """Переход в раздел 'Короткие видео'."""
        try:
            # Ожидаем появления кнопки 'Короткие видео' по тексту внутри div
            short_videos_button = self._wait_for_element(By.XPATH, "//div[contains(text(), 'Короткие видео')]")

            # Прокручиваем страницу до кнопки, если она не видна
            self.driver.execute_script("arguments[0].scrollIntoView(true);", short_videos_button)

            # Кликаем по кнопке
            short_videos_button.click()
            print("Кнопка 'Короткие видео' нажата.")

            self._get_random_sleep()  # добавляем задержку после клика

        except Exception as e:
            print(f"Ошибка при переходе в раздел 'Короткие видео': {e}")

    def load_video_data(self):
        """Загружает существующие данные о видео из JSON файла."""
        try:
            file_path = '../Data/clips.json'
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return []
        except Exception as e:
            print(f"{e}")
            return []

    def save_video_data(self, video_data):
        """Сохраняет видео данные в JSON файл."""
        file_path = '../Data/clips.json'
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(video_data, f, ensure_ascii=False, indent=4)

    async def get_video_links(self, search_query, required_video_count=10):
        """Извлекает ссылки на видео с результатов поиска и из раздела 'Короткие видео'."""
        await self.open_google()

        await self._get_random_sleep()
        self.accept_cookies()

        await self._get_random_sleep()
        await self.search(search_query)

        await self._get_random_sleep()
        self.save_start_html_page(self.driver)

        # Переходим в раздел коротких видео
        await self._get_random_sleep()
        self.go_to_short_videos_section()

        await self._get_random_sleep()
        self.apply_vk_filter()

        # Загружаем уже сохраненные ссылки
        # saved_videos = self.load_video_data()

        video_data = []
        video_count = 0
        try:
            i = 0
            while video_count < required_video_count:
                # Извлекаем все видео на странице
                if i > 15:
                    break
                video_elements = self.driver.find_elements(By.XPATH, "//a[contains(@href, 'vk.com/video')]")
                if len(video_elements) == 0:
                    logger.error("0 elements on page")
                    self.save_html_page(self.driver)
                    return video_data
                for video in video_elements:
                    href = video.get_attribute("href")
                    video_id = href.split('/')[-1]  # Получаем ID видео из ссылки

                    # # Проверяем, было ли уже сохранено это видео
                    # if any(v['id'] == video_id for v in saved_videos):
                    #     print(f"Видео {video_id} уже сохранено, пропускаем.")
                    # else:
                    name = video.text[:5]  # Берем первые 5 символов названия видео
                    video_data.append({"id": video_id, "name": name, "url": href})
                    video_count += 1

                    print(f"Найдено новое видео {video_id}, сохраняем.")

                    # Если собрано 10 видео, выходим
                    if video_count >= required_video_count:
                        break

                # Если видео меньше 10, проверяем наличие кнопки "Ещё результаты" и кликаем на неё
                if video_count < required_video_count:
                    try:
                        # Проверка наличия кнопки "Ещё результаты"
                        load_more_button = self._wait_for_element(By.XPATH,
                                                                  "//h3[@aria-hidden='true']//span[text()='Ещё результаты']")
                        self.driver.execute_script("arguments[0].scrollIntoView(true);",
                                                   load_more_button)  # Прокрутка до кнопки
                        load_more_button.click()  # Клик по кнопке "Ещё результаты"
                        print("Нажата кнопка 'Ещё результаты'.")
                        await self._get_random_sleep()
                    except Exception as e:
                        print("Кнопка 'Ещё результаты' не найдена или ошибка:", e)
                        logger.error(f"Кнопка 'Ещё результаты' не найдена или ошибка: {e}")
                        print("Недостаточно видео, продолжаем скроллинг...")

                        self.driver.execute_script("window.scrollBy(0, document.body.scrollHeight);")
                        await self._get_random_sleep()

                    finally:
                        self.save_html_page(self.driver)

                # Если видео меньше 10, продолжаем скроллинг
                if video_count < required_video_count:
                    print("Недостаточно видео, продолжаем скроллинг...")
                    logger.info("Недостаточно видео, продолжаем скроллить")
                    self.driver.execute_script("window.scrollBy(0, document.body.scrollHeight);")
                    await self._get_random_sleep()

        except Exception as e:
            print("Ошибка при извлечении данных о видео:", e)
            logger.error("Ошибка при извлечении данных о видео")
            self.save_html_page(self.driver)
        return video_data

    def close(self):
        """Закрытие браузера."""
        self.driver.quit()

