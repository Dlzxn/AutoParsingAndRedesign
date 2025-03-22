
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

chrome_options = Options()
chrome_options.add_argument("--headless")
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--no-sandbox")


def parse_vk_video(hashtag: str)-> tuple[bool, list[str]]:
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

    href_list: list[str] = []
    driver.get(f"https://vkvideo.ru/?q={hashtag}")

    try:
        div_element = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "ListVideos__horizontalVideo--TNL0D"))
        )
        elem = div_element.get_attribute('outerHTML')
    except:
        print("Элемент не найден")
        return False, href_list
    finally:
        driver.quit()

    print(elem)

    for i in range(10):
        index_href: int | None | str = elem.find("href")
        if index_href == None:
            break
        else:
            elem = elem[index_href:]
            href_list.append(elem[:elem[6:].find('"')])
            print(href_list)
    return True, href_list
parse_vk_video("mash")
