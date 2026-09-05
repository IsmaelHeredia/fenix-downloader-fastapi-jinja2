import requests
from bs4 import BeautifulSoup


class DuckDuckGoSearch:
    def __init__(self, user_agent=None):
        self.headers = {
            "User-Agent": user_agent or (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            )
        }

    def send_first_result(self, query):
        try:
            response = requests.post(
                "https://html.duckduckgo.com/html/",
                headers=self.headers,
                data={"q": query},
                timeout=10,
            )
            response.raise_for_status()
        except requests.RequestException:
            return None

        soup = BeautifulSoup(response.text, "html.parser")
        results = soup.find_all("a", href=True)

        for link in results:
            href = link["href"]
            if href.startswith("http") and "duckduckgo.com/l/?uddg=" in href:
                real_url = requests.utils.unquote(href.split("uddg=")[-1])
                if real_url.startswith("http"):
                    return real_url
            elif href.startswith("http") and "youtube.com" in href:
                return href

        return None
