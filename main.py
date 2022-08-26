import json
import csv
from random import randrange
import aiohttp
import asyncio
from itertools import islice
from bs4 import BeautifulSoup

from mark_time import mark_time
from get_categories import categories_file, data_path
from proxy_auth_data import proxy_ip, proxy_port, proxy_login, proxy_password

receipts_path = data_path / "receipts"

headers = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/104.0.0.0 Safari/537.36",
}
proxy = f"http://{proxy_login}:{proxy_password}@{proxy_ip}:{proxy_port}"


def get_categories():
    """Возвращает словарь с названиями категорий и ссылками на них"""
    with open(categories_file, "r", encoding="utf8") as f:
        return json.load(f)


async def get_category_page_data(session, category_name, category_url):
    page = 1
    while page != 10000:
        page_url = category_url if page == 1 else f"{category_url}~{page}/"
        # TODO: добавить
        async with session.get(url=page_url, proxy=proxy, headers=headers) as response:
            if response.status != 200:
                break
            response_text = await response.text()
            category_bs4 = BeautifulSoup(response_text, "lxml")
            all_articles_per_page = category_bs4.find_all("article", class_="item-bl")
            category_path = receipts_path / category_name
            if all_articles_per_page == []:
                break
            links_per_page = {}
            for article in all_articles_per_page:
                try:
                    header = article.find("h2")
                    receipt_header = header.text.strip()
                    receipt_link = header.find("a").get("href", None)
                    print(
                        f"{category_name} / Страница {page} --- {receipt_header} {receipt_link}"
                    )
                    links_per_page[receipt_header] = receipt_link
                except Exception as e:
                    print("ERROR! ", e)

            if links_per_page != {}:
                if not category_path.exists() or not category_path.is_dir():
                    category_path.mkdir()
                links_file = category_path / "links.csv"
                fieldnames = ["header", "url"]
                if not links_file.exists():
                    with open(links_file, "w", encoding="utf8", newline="") as f:
                        writer = csv.DictWriter(f, fieldnames=fieldnames)
                        writer.writeheader()
                        for header, url in links_per_page.items():
                            writer.writerow({"header": header, "url": url})
                else:
                    with open(links_file, "a", encoding="utf8", newline="") as f:
                        writer = csv.DictWriter(f, fieldnames=fieldnames)
                        for header, url in links_per_page.items():
                            writer.writerow({"header": header, "url": url})

            await asyncio.sleep(
                randrange(0, 3),
            )

        page += 1


async def gather_data():
    categories = get_categories()
    categories = dict(islice(categories.items(), 3))
    async with aiohttp.ClientSession() as session:
        tasks = []
        for category_name, category_url in categories.items():
            task = asyncio.create_task(
                get_category_page_data(session, category_name, category_url)
            )
            tasks.append(task)

        await asyncio.gather(*tasks)


@mark_time
def main():
    if not receipts_path.exists() or not receipts_path.is_dir():
        receipts_path.mkdir()
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(gather_data())


if __name__ == "__main__":
    main()
