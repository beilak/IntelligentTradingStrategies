# """Loader Investor Calendar and save to CSV"""
# import csv
#
# # open the file in the write mode
# with open("path/to/csv_file", "w", encoding="UTF8") as f:
#     # create the csv writer
#     writer = csv.writer(f)
#
#     # write a row to the csv file
#     writer.writerow(row)
#
#
import asyncio
from bs4 import BeautifulSoup
import requests


class QiwiInvestorCalendarHist:
    def __init__(self, urls: set) -> None:
        self._urls = urls

    @classmethod
    def parse_html(cls, content):
        soup = BeautifulSoup(content, "html.parser")
        # print(soup)
        calendar_block = soup.find_all("div", class_="card__inner")
        # print(calendar_block)
        for i in calendar_block:
            print(i.find("div", class_="card__date"))
            print(i.find("div", class_="card__title"))
            break

    async def execute(self, url):
        # async with httpx.AsyncClient() as client:
        #     cont = await client.get(url)
        cont = requests.get(url=url, verify=False)

        # load_url_tasks: set = {client.get(url=url) for url in self._urls}

        # contents: list[httpx.Response] = await asyncio.gather(*load_url_tasks)
        self.parse_html(cont.content)
        # for content in contents:
        #     self.parse_html(content.content)


# class="calendar-card__content"


if __name__ == "__main__":
    qiwi = QiwiInvestorCalendarHist(
        urls={
            "https://investor.qiwi.com/news-and-events/investors-calendar/#tabs-2018",
        }
    )

    asyncio.run(qiwi.execute("https://group.ptsecurity.com/ru/calendar/"))
