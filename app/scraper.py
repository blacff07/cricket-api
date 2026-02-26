import re
import random
import requests
import logging
from bs4 import BeautifulSoup
from .config import Config

logger = logging.getLogger(__name__)

def get_random_agent():
    return random.choice(Config.USER_AGENTS)

def fetch_page(url):
    headers = {
        "User-Agent": get_random_agent(),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Cache-Control": "no-cache"
    }

    try:
        resp = requests.get(url, headers=headers, timeout=Config.REQUEST_TIMEOUT)
        resp.raise_for_status()
        return BeautifulSoup(resp.content, "lxml"), None
    except requests.exceptions.Timeout:
        return None, "timeout"
    except requests.exceptions.ConnectionError:
        return None, "connection_error"
    except requests.exceptions.HTTPError as e:
        return None, f"http_{e.response.status_code}"
    except Exception:
        return None, "unknown"

# ------------------------------------------------------------
# LIVE MATCHES
# ------------------------------------------------------------
def extract_live_matches(soup):
    matches = []
    links = soup.find_all("a", href=True)

    for a in links:
        href = a["href"]

        if "/live-cricket-scorecard/" not in href:
            continue

        match = re.search(r"/live-cricket-scorecard/(\d+)", href)
        if not match:
            continue

        match_id = int(match.group(1))

        header = a.find("h3", class_="cb-lv-scr-mtch-hdr")
        if not header:
            continue

        title = header.get_text(strip=True)

        teams = []
        if " vs " in title:
            team_part = title.split(",")[0]
            teams = [t.strip() for t in team_part.split(" vs ")]

        status = "Upcoming"
        if a.find_next("div", class_="cb-text-live"):
            status = "Live"
        elif a.find_next("div", class_="cb-text-complete"):
            status = "Completed"

        start_time = None
        info_div = a.find_next("div", class_="cb-font-12")
        if info_div:
            start_time = info_div.get_text(strip=True)

        matches.append({
            "id": match_id,
            "teams": teams[:2],
            "title": title,
            "status": status,
            "start_time": start_time
        })

    unique = {m["id"]: m for m in matches}
    return list(unique.values())

# ------------------------------------------------------------
# START TIME FROM SCORECARD PAGE
# ------------------------------------------------------------
def extract_start_time_from_match_page(soup):
    time_pattern = re.compile(r"\d{1,2}:\d{2}\s*(AM|PM).*?LOCAL", re.I)
    text = soup.find(string=time_pattern)
    if text:
        return text.strip()
    return None

# ------------------------------------------------------------
# MATCH DATA
# ------------------------------------------------------------
def extract_match_data(soup):
    title_elem = soup.find("h1", class_="cb-nav-hdr")
    title = title_elem.get_text(strip=True) if title_elem else None

    teams = []
    if title and " vs " in title:
        parts = title.split(" vs ")
        teams = [parts[0].strip(), parts[1].split(",")[0].strip()]

    return {
        "title": title,
        "teams": teams,
        "status": extract_status(soup),
        "start_time": extract_start_time_from_match_page(soup),
        "current_score": extract_current_score(soup),
        "run_rate": extract_run_rate(soup),
        "batting": extract_batting(soup),
        "bowling": extract_bowling(soup)
    }

def extract_status(soup):
    div = soup.find("div", class_="cb-text-live")
    if div:
        return div.get_text(strip=True)

    div = soup.find("div", class_="cb-text-complete")
    if div:
        return div.get_text(strip=True)

    div = soup.find("div", class_="cb-text-preview")
    if div:
        return div.get_text(strip=True)

    return "Match Stats will Update Soon..."

def extract_current_score(soup):
    header = soup.find("div", class_="cb-col cb-col-100 cb-scrd-hdr-rw")
    if not header:
        return None

    score_text = header.get_text(strip=True)
    match = re.search(r"([A-Z]+)\s+(\d+)-(\d+)\s*\((\d+\.?\d*)\)", score_text)
    if match:
        return {
            "team": match.group(1),
            "runs": int(match.group(2)),
            "wickets": int(match.group(3)),
            "overs": float(match.group(4))
        }
    return None

def extract_run_rate(soup):
    rr_text = soup.find(string=re.compile(r"RR:\s*(\d+\.?\d*)"))
    if rr_text:
        match = re.search(r"RR:\s*(\d+\.?\d*)", rr_text)
        if match:
            return float(match.group(1))
    return None

def extract_batting(soup):
    batting = []
    rows = soup.find_all("div", class_="cb-scrd-itms")

    for row in rows:
        cells = row.find_all("div", class_=lambda c: c and "cb-col" in c)
        if len(cells) < 6:
            continue

        name_link = cells[0].find("a")
        if not name_link:
            continue

        try:
            runs = int(cells[1].get_text(strip=True))
            balls = int(cells[2].get_text(strip=True))
            fours = int(cells[3].get_text(strip=True))
            sixes = int(cells[4].get_text(strip=True))
            sr = float(cells[5].get_text(strip=True))
        except:
            continue

        batting.append({
            "name": name_link.get_text(strip=True).replace("*", ""),
            "runs": runs,
            "balls": balls,
            "fours": fours,
            "sixes": sixes,
            "sr": sr
        })

    return batting

def extract_bowling(soup):
    bowling = []
    rows = soup.find_all("div", class_="cb-scrd-itms")

    for row in rows:
        cells = row.find_all("div", class_=lambda c: c and "cb-col" in c)
        if len(cells) < 6:
            continue

        name_link = cells[0].find("a", href=lambda h: h and "/profiles/" in h)
        if not name_link:
            continue

        try:
            overs = float(cells[1].get_text(strip=True))
            maidens = int(cells[2].get_text(strip=True))
            runs = int(cells[3].get_text(strip=True))
            wickets = int(cells[4].get_text(strip=True))
            econ = float(cells[5].get_text(strip=True))
        except:
            continue

        bowling.append({
            "name": name_link.get_text(strip=True),
            "overs": overs,
            "maidens": maidens,
            "runs": runs,
            "wickets": wickets,
            "econ": econ
        })

    return bowling