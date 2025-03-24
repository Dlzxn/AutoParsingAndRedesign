import time
import random
import json
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


class GoogleBot:
    def __init__(self, user_agent=None, headless=True):
        self.chrome_options = webdriver.ChromeOptions()
        if headless:
            self.chrome_options.add_argument("--headless")  # для работы без интерфейса
        if user_agent:
            self.chrome_options.add_argument(f"user-agent={user_agent}")
        else:
            self.chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                                             "(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")

        self.chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        self.chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        self.chrome_options.add_experimental_option("useAutomationExtension", False)

        self.driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=self.chrome_options)

    def _wait_for_element(self, by, value, timeout=10):
        """Ожидаем появления элемента на странице."""
        wait = WebDriverWait(self.driver, timeout)
        return wait.until(EC.element_to_be_clickable((by, value)))

    def _get_random_sleep(self):
        """Случайная задержка, чтобы имитировать поведение реального пользователя."""
        time.sleep(random.uniform(1, 3))

    def open_google(self):
        """Открывает главную страницу Google."""
        self.driver.get("https://www.google.com")
        self._get_random_sleep()

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
            agree_button = self._wait_for_element(By.XPATH, "//div[text()='Принять все']")
            agree_button.click()
            print("Кнопка 'Принять все' нажата.")
        except Exception as e:
            print(f"Ошибка при поиске кнопки 'Принять все': {e}")

    def search(self, search_query):
        """Выполняет поиск по запросу."""
        search_box = self.driver.find_element(By.NAME, "q")
        search_box.send_keys(search_query + "вк клипы")
        self._get_random_sleep()
        search_box.send_keys(Keys.RETURN)
        self._get_random_sleep()

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

    def get_video_links(self, search_query, required_video_count=10):
        """Извлекает ссылки на видео с результатов поиска и из раздела 'Короткие видео'."""
        self.open_google()
        self.accept_cookies()
        self.search(search_query)


        # Переходим в раздел коротких видео
        self.go_to_short_videos_section()

        self.apply_vk_filter()

        # Загружаем уже сохраненные ссылки
        saved_videos = self.load_video_data()

        video_data = []
        video_count = 0
        try:
            while video_count < required_video_count:
                # Извлекаем все видео на странице
                video_elements = self.driver.find_elements(By.XPATH, "//a[contains(@href, 'vk.com/video')]")
                for video in video_elements:
                    href = video.get_attribute("href")
                    video_id = href.split('/')[-1]  # Получаем ID видео из ссылки

                    # Проверяем, было ли уже сохранено это видео
                    if any(v['id'] == video_id for v in saved_videos):
                        print(f"Видео {video_id} уже сохранено, пропускаем.")
                    else:
                        name = video.text[:5]  # Берем первые 5 символов названия видео
                        video_data.append({"id": video_id, "name": name, "url": href})
                        saved_videos.append({"id": video_id, "name": name, "url": href})
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
                        self._get_random_sleep()  # Ждем перед следующим шагом
                    except Exception as e:
                        print("Кнопка 'Ещё результаты' не найдена или ошибка:", e)
                        print("Недостаточно видео, продолжаем скроллинг...")
                        self.driver.execute_script("window.scrollBy(0, document.body.scrollHeight);")
                        self._get_random_sleep()  # Ждем перед следующим скроллом

                # Если видео меньше 10, продолжаем скроллинг
                if video_count < required_video_count:
                    print("Недостаточно видео, продолжаем скроллинг...")
                    self.driver.execute_script("window.scrollBy(0, document.body.scrollHeight);")
                    self._get_random_sleep()  # Ждем перед следующим скроллом

            # Сохраняем все новые видео в JSON
            if saved_videos:
                self.save_video_data(saved_videos)
        except Exception as e:
            print("Ошибка при извлечении данных о видео:", e)
        return video_data

    def close(self):
        """Закрытие браузера."""
        self.driver.quit()
