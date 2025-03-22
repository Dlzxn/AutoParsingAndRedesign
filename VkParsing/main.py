import json
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
        index_href: int | None | str = elem.find("/video-")
        if index_href == -1:
            break
        else:
            elem = elem[index_href:]
            print(elem[6:elem[6:].find('"')])
            end_elem = elem.find('"')
            data = {
                "id": i,
                "url": f"https://vkvideo.ru{elem[:end_elem]}",

            }
            flag = 0
            for i in range(len(href_list)):
                if href_list[i]["url"] == data["url"]:
                    flag = 1
                    break
            if flag == 0:
                href_list.append(data)
            elem = elem[end_elem:]
            print(href_list)

    with open("Data/href.json", "w", encoding="utf-8") as f:
        json.dump(href_list, f, ensure_ascii=False)
    return True, href_list
