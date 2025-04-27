from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options
import asyncio
import urllib.parse

import logging, random
import platform

# Инициализация логгера
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class GoogleBot:
    def __init__(self):
        chrome_options = Options()

        # Обязательные параметры для работы в контейнере/на сервере
        # chrome_options.binary_location = "/usr/bin/google-chrome"
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--remote-debugging-port=9222")
        chrome_options.add_argument("--disable-gpu")

        # Headless-режим с эмуляцией реального окна
        chrome_options.add_argument("--headless=new")  # Новый headless-режим Chrome 112+
        chrome_options.add_argument("--window-size=1920,1080")

        # Эмуляция реального пользователя
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option("useAutomationExtension", False)

        # Устанавливаем User-Agent
        user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
        chrome_options.add_argument(f"user-agent={user_agent}")

        # Инициализация драйвера с обработкой ошибок
        try:
            # display = Display(visible=0, size=(800, 800))
            # display.start()
            #
            # display.stop()

            self.driver = webdriver.Chrome(
                # service=Service("/usr/bin/chromedriver"),
                options=chrome_options
            )

            # Маскируем headless-браузер
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        except Exception as e:
            logger.error(f"Ошибка инициализации драйвера: {str(e)}")
            raise

    async def _click_if_exists(self, xpath, timeout=10):

        try:
            element = WebDriverWait(self.driver, timeout).until(
                EC.element_to_be_clickable((By.XPATH, xpath))
            )
            self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", element)
            element.click()
            logger.info(f"Успешный клик по элементу: {xpath}")
            return True
        except Exception as e:
            logger.warning(f"Элемент не найден: {xpath} | {str(e)}")
            return False

    async def get_video_links(self, query, clips, max_results=10):
        try:
            query = urllib.parse.quote_plus(query)
            vk = "+вк+клипы"
            url = f"https://www.google.ru/search?num=12&newwindow=1&sca_esv=4222a1b969aeacfe&q={query+vk}&udm=39"

            self.driver.get(url)
            logger.info(f"Загружена страница: {url}")

            # Обработка куки
            await self._click_if_exists("//button[.//div[contains(text(), 'Отклонить все')]]", timeout=5)

            # Добавляем дополнительное ожидание для загрузки результатов
            await asyncio.sleep(3)

            results = []
            attempts = 0

            # Новый XPath для поиска результатов
            xpath = "//div[@id='search']//a[contains(@href, 'vk.com/video') and @ping and not(contains(@href, 'about'))]"

            while len(results) < max_results and attempts < 5:
                try:
                    WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.XPATH, xpath)))

                    video_cards = self.driver.find_elements(By.XPATH, xpath)
                    logger.info(f"Найдено элементов: {len(video_cards)}")

                    for card in video_cards:
                        try:
                            url = card.get_attribute("href")
                            if url and url not in [r['url'] for r in results] and url not in clips:
                                results.append({
                                    "title": card.text.split('\n')[0][:30] if card.text else "No title",
                                    "url": url,
                                    "id": url.split("/")[-1].split("?")[0]
                                })
                                if len(results) >= max_results:
                                    return results
                        except Exception as e:
                            logger.warning(f"Ошибка обработки карточки: {str(e)}")

                    # Если результатов мало - скроллим вниз
                    if len(results) < max_results:
                        self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                        await asyncio.sleep(2)
                        attempts += 1

                except Exception as e:
                    logger.error(f"Ошибка при поиске элементов: {str(e)}")
                    attempts += 1

            return results[:max_results]

        except Exception as e:
            logger.error(f"Критическая ошибка: {str(e)}")
            return []
        finally:
            if self.driver:
                self.driver.quit()
                logger.info("Браузер закрыт")


async def main():
    bot = GoogleBot()
    try:
        results = await bot.get_video_links("котики большие", 5)
        print("Результаты поиска:")
        for idx, item in enumerate(results, 1):
            print(f"{idx}. {item['title']}\nURL: {item['url']}\nID: {item['id']}\n")
    except Exception as e:
        print(f"Ошибка выполнения: {e}")


if __name__ == "__main__":
    asyncio.run(main())