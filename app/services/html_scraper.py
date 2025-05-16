from typing import List, Optional, Dict
from urllib.parse import urlparse, parse_qs
from selenium.webdriver import Keys
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from utils.logger import setup_logger
import os
from bs4 import BeautifulSoup
from selenium import webdriver


SELENIUM_REMOTE_URL = os.getenv("SELENIUM_REMOTE_URL")
STATE = os.getenv("STATE")
logger = setup_logger("scraper")
async def fetch_company_details(url: str) -> dict:
    driver = None
    try:
        options = webdriver.ChromeOptions()
        options.add_argument(f'--lang=en-US')
        options.add_argument("--start-maximized")
        options.add_argument("--disable-webrtc")
        options.add_argument("--disable-features=WebRtcHideLocalIpsWithMdns")
        options.add_argument("--force-webrtc-ip-handling-policy=default_public_interface_only")
        options.add_argument("--disable-features=DnsOverHttps")
        options.add_argument("--no-default-browser-check")
        options.add_argument("--no-first-run")
        options.add_argument("--no-sandbox")
        options.add_argument("--test-type")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        options.set_capability("goog:loggingPrefs", {
            "performance": "ALL",
            "browser": "ALL"
        })
        driver = webdriver.Remote(
            command_executor=SELENIUM_REMOTE_URL,
            options=options
        )
        driver.set_page_load_timeout(30)
        driver.get(url)
        WebDriverWait(driver, 10).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        wait = WebDriverWait(driver, 10)
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#content")))
        tableResults = driver.find_element(By.CSS_SELECTOR, "#content")
        html = tableResults.get_attribute("outerHTML")
        query_params = parse_qs(urlparse(url).query)
        org_id = query_params.get("org", [None])[0]
        return await parse_html_details(html, org_id)
    except Exception as e:
        logger.error(f"Error fetching data for query '{url}': {e}")
        return {}
    finally:
        if driver:
            driver.quit()

async def fetch_company_data(query: str) -> list[dict]:
    driver = None
    url = "https://apps.sos.wv.gov/business/corporations/Default.aspx"
    try:

        options = webdriver.ChromeOptions()
        options.add_argument(f'--lang=en-US')
        options.add_argument("--start-maximized")
        options.add_argument("--disable-webrtc")
        options.add_argument("--disable-features=WebRtcHideLocalIpsWithMdns")
        options.add_argument("--force-webrtc-ip-handling-policy=default_public_interface_only")
        options.add_argument("--disable-features=DnsOverHttps")
        options.add_argument("--no-default-browser-check")
        options.add_argument("--no-first-run")
        options.add_argument("--no-sandbox")
        options.add_argument("--test-type")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        options.set_capability("goog:loggingPrefs", {
            "performance": "ALL",
            "browser": "ALL"
        })
        driver = webdriver.Remote(
            command_executor=SELENIUM_REMOTE_URL,
            options=options
        )
        driver.set_page_load_timeout(30)
        driver.get(url)
        WebDriverWait(driver, 10).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        wait = WebDriverWait(driver, 20)
        first_input = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "#txtOrgName"))
        )
        first_input.send_keys(query)
        first_input.send_keys(Keys.RETURN)
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR,
                                                   "#tableResults")))
        tableResults = driver.find_element(By.CSS_SELECTOR, "#tableResults")
        html = tableResults.get_attribute("outerHTML")
        return await parse_html_search(html)
    except Exception as e:
        logger.error(f"Error fetching data for query '{query}': {e}")
        return []
    finally:
        if driver:
            driver.quit()

async def parse_html_search(html: str) -> List[Dict]:
    soup = BeautifulSoup(html, 'html.parser')
    results = []
    table = soup.find('table', id='tableResults')
    if not table:
        return results

    rows = table.find_all('tr')
    for row in rows:
        if 'rowHeader' in row.get('class', []):
            continue

        cells = row.find_all('td')
        if len(cells) != 9:
            continue

        org_name_tag = cells[0].find('a')
        org_name = org_name_tag.text.strip() if org_name_tag else ''
        org_link = org_name_tag['href'] if org_name_tag and org_name_tag.has_attr('href') else ''

        result = {
            "state": STATE,
            "name": org_name,
            "url": "https://apps.sos.wv.gov/business/corporations/" + org_link,
            "id": cells[1].text.strip(),
        }
        results.append(result)

    return results

async def parse_html_details(html: str, org_id: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    def get_text(el):
        return el.get_text(strip=True).replace('\xa0', ' ') if el else ''


    result = {}

    # Название организации
    org_name = soup.select_one("#lblOrg")
    result["state"] = STATE
    result["name"] = get_text(org_name)
    result["registration_number"] = org_id

    # Основная информация (первая таблица)
    org_info_table = soup.select("table.tableData")
    if len(org_info_table) >= 1:
        org_info_cells = org_info_table[0].select("tr.rowNormal td")
        if len(org_info_cells) >= 9:
            status = "Active"
            term_date = get_text(org_info_cells[8])
            if term_date != "":
                status = "Inactive"
            result.update({
                "entity_type": get_text(org_info_cells[1]),
                "date_registered": get_text(org_info_cells[2]),
                "status": status,
            })

    # Адреса (третья таблица)
    if len(org_info_table) >= 3:
        address_table = org_info_table[2]
        for row in address_table.select("tr"):
            th = row.find("th")
            td = row.find("td")
            if th and td:
                label = get_text(th)
                address = td.get_text(separator=" ", strip=True)  # Убираем <br>
                if label == "Mailing Address":
                    result["mailing_address"] = address
                elif label == "Principal Office Address":
                    result["principal_address"] = address

    # Officers (четвёртая таблица)
    if len(org_info_table) >= 4:
        officer_table = org_info_table[3]
        officers = []
        for row in officer_table.select("tr"):
            th = row.find("th")
            td = row.find("td")
            if th and td:
                lines = td.get_text(separator="\n", strip=True).split("\n")
                name = lines[0].strip() if lines else ""
                address = " ".join(line.strip() for line in lines[1:]) if len(lines) > 1 else ""
                officers.append({
                    "title": get_text(th),
                    "name": name,
                    "address": address
                })
        result["officers"] = officers

    return result