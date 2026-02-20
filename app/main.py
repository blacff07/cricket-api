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
        'User-Agent': get_random_agent(),
        'Cache-Control': 'no-cache'
    }
    try:
        resp = requests.get(url, headers=headers, timeout=Config.REQUEST_TIMEOUT)
        resp.raise_for_status()
        return BeautifulSoup(resp.content, 'lxml'), None
    except requests.exceptions.Timeout:
        logger.error(f"Timeout fetching {url}")
        return None, "timeout"
    except requests.exceptions.ConnectionError:
        logger.error(f"Connection error fetching {url}")
        return None, "connection_error"
    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP error {e.response.status_code} fetching {url}")
        return None, f"http_{e.response.status_code}"
    except Exception as e:
        logger.error(f"Unexpected error fetching {url}: {e}")
        return None, "unknown"

def extract_live_matches(soup):
    matches = []
    # Method 1: Find all match blocks by common class
    match_blocks = soup.find_all('div', class_='cb-mtch-blk')
    if not match_blocks:
        # Method 2: Look for any div containing a link with match ID
        for link in soup.find_all('a', href=re.compile(r'/live-cricket-scores/\d+')):
            href = link['href']
            match_id = int(re.search(r'/live-cricket-scores/(\d+)', href).group(1))
            title = link.get_text(strip=True)
            parent = link.find_parent('div', class_=lambda c: c and ('cb-col' in c or 'cb-mtch-blk' in c))
            status = "Upcoming"
            start_time = None
            if parent:
                if parent.find('span', class_=lambda c: c and 'cb-plus-live-tag' in c):
                    status = "Live"
                elif parent.find('div', class_=lambda c: c and 'cb-text-complete' in c):
                    status = "Completed"
                elif parent.find('div', string=re.compile(r'won by|win by', re.I)):
                    status = "Completed"
                time_elem = parent.find('span', class_='sch-date')
                if time_elem:
                    start_time = time_elem.get_text(strip=True)
            matches.append({
                'id': match_id,
                'title': title,
                'status': status,
                'teams': [t.strip() for t in title.split(' vs ')[:2]] if ' vs ' in title else [],
                'start_time': start_time
            })
    else:
        # Original method
        for block in match_blocks:
            link = block.find('a', href=True)
            if not link:
                continue
            href = link['href']
            match = re.search(r'/live-cricket-scores/(\d+)', href)
            if not match:
                continue
            match_id = int(match.group(1))
            title_tag = link.find('span', class_=lambda c: c and 'text-hvr-underline' in c)
            title = title_tag.get_text(strip=True) if title_tag else link.get_text(strip=True)
            teams = []
            if ' vs ' in title:
                parts = title.split(' vs ')
                if len(parts) >= 2:
                    teams = [parts[0].split(',')[0].strip(), parts[1].split(',')[0].strip()]
            status = "Upcoming"
            if block.find('span', class_=lambda c: c and 'cb-plus-live-tag' in c):
                status = "Live"
            elif block.find('div', class_=lambda c: c and 'cb-text-complete' in c):
                status = "Completed"
            elif block.find('div', string=re.compile(r'won by|win by', re.I)):
                status = "Completed"
            start_time = None
            time_elem = block.find('span', class_='sch-date')
            if time_elem:
                start_time = time_elem.get_text(strip=True)
            matches.append({
                'id': match_id,
                'teams': teams,
                'title': title,
                'status': status,
                'start_time': start_time
            })

    unique = {m['id']: m for m in matches}
    return list(unique.values())

def extract_match_data(soup):
    title_tag = soup.find('h1')
    title = title_tag.get_text(strip=True).replace(', Commentary', '').replace(' - Scorecard', '').strip() if title_tag else None
    teams = []
    if title and ' vs ' in title:
        parts = title.split(' vs ')
        if len(parts) >= 2:
            teams = [parts[0].split(',')[0].strip(), parts[1].split(',')[0].strip()]
    status = extract_match_status_from_match_page(soup) or 'Match Stats will Update Soon...'
    current_score = extract_current_score(soup)
    run_rate = extract_run_rate(soup)
    batting = extract_batting(soup)
    bowling = extract_bowling(soup)
    start_time = extract_start_time_from_match_page(soup)
    return {
        'title': title,
        'teams': teams,
        'status': status,
        'start_time': start_time,
        'current_score': current_score,
        'run_rate': run_rate,
        'batting': batting,
        'bowling': bowling
    }

def extract_current_score(soup):
    # Try multiple patterns
    for selector in [
        'div.font-bold.text-xl.flex',
        'div[class*="cb-score"]',
        'div[class*="cb-col"] span[class*="cb-font-20"]'
    ]:
        elem = soup.select_one(selector)
        if elem:
            text = elem.get_text(strip=True)
            # Example: "IND 180/5 (20)"
            match = re.match(r'([A-Za-z]+)\s*(\d+)[/-](\d+)\s*\((\d+\.?\d*)\)', text)
            if match:
                return {
                    'team': match.group(1),
                    'runs': int(match.group(2)),
                    'wickets': int(match.group(3)),
                    'overs': float(match.group(4))
                }
    return None

def extract_run_rate(soup):
    rr_elem = soup.find(string=re.compile(r'CRR', re.I))
    if rr_elem:
        parent = rr_elem.parent
        if parent:
            numbers = re.findall(r'\d+\.?\d*', parent.get_text())
            if numbers:
                try:
                    return float(numbers[0])
                except:
                    pass
    return None

def extract_batting(soup):
    batting = []
    rows = soup.find_all('div', class_=lambda c: c and 'scorecard-bat-grid' in c)
    if not rows:
        rows = soup.select('table[class*="scorecard"] tbody tr')
    for row in rows:
        name_link = row.find('a', href=lambda h: h and '/profiles/' in h)
        if not name_link:
            continue
        name = name_link.get_text(strip=True).replace(' *', '').replace('†', '')
        stat_divs = row.find_all('div', class_=lambda c: c and 'flex justify-center items-center' in c)
        if len(stat_divs) < 5:
            # Try td elements in a table
            tds = row.find_all('td')
            if len(tds) >= 6:
                try:
                    runs = int(tds[2].get_text(strip=True)) if tds[2].get_text(strip=True).isdigit() else 0
                    balls = int(tds[3].get_text(strip=True)) if tds[3].get_text(strip=True).isdigit() else 0
                    fours = int(tds[4].get_text(strip=True)) if tds[4].get_text(strip=True).isdigit() else 0
                    sixes = int(tds[5].get_text(strip=True)) if tds[5].get_text(strip=True).isdigit() else 0
                    sr_text = tds[6].get_text(strip=True) if len(tds) > 6 else '0'
                    sr = float(sr_text) if sr_text.replace('.', '').isdigit() else 0.0
                    batting.append({'name': name, 'runs': runs, 'balls': balls, 'fours': fours, 'sixes': sixes, 'sr': sr})
                except:
                    pass
            continue
        try:
            runs = int(stat_divs[0].get_text(strip=True)) if stat_divs[0].get_text(strip=True).isdigit() else 0
            balls = int(stat_divs[1].get_text(strip=True)) if stat_divs[1].get_text(strip=True).isdigit() else 0
            fours = int(stat_divs[2].get_text(strip=True)) if stat_divs[2].get_text(strip=True).isdigit() else 0
            sixes = int(stat_divs[3].get_text(strip=True)) if stat_divs[3].get_text(strip=True).isdigit() else 0
            sr_text = stat_divs[4].get_text(strip=True)
            sr = float(sr_text) if sr_text.replace('.', '').isdigit() else 0.0
            batting.append({'name': name, 'runs': runs, 'balls': balls, 'fours': fours, 'sixes': sixes, 'sr': sr})
        except (ValueError, IndexError):
            continue
    return batting

def extract_bowling(soup):
    bowling = []
    rows = soup.find_all('div', class_=lambda c: c and 'scorecard-bowl-grid' in c)
    if not rows:
        rows = soup.select('table[class*="scorecard"] tbody tr')
    for row in rows:
        name_link = row.find('a', href=lambda h: h and '/profiles/' in h)
        if not name_link:
            continue
        name = name_link.get_text(strip=True)
        stat_divs = row.find_all('div', class_=lambda c: c and 'flex justify-center items-center' in c)
        if len(stat_divs) < 5:
            tds = row.find_all('td')
            if len(tds) >= 6:
                try:
                    overs = float(tds[2].get_text(strip=True)) if tds[2].get_text(strip=True).replace('.', '').isdigit() else 0.0
                    maidens = int(tds[3].get_text(strip=True)) if tds[3].get_text(strip=True).isdigit() else 0
                    runs = int(tds[4].get_text(strip=True)) if tds[4].get_text(strip=True).isdigit() else 0
                    wickets = int(tds[5].get_text(strip=True)) if tds[5].get_text(strip=True).isdigit() else 0
                    econ = float(tds[6].get_text(strip=True)) if len(tds) > 6 and tds[6].get_text(strip=True).replace('.', '').isdigit() else 0.0
                    bowling.append({'name': name, 'overs': overs, 'maidens': maidens, 'runs': runs, 'wickets': wickets, 'econ': econ})
                except:
                    pass
            continue
        try:
            overs_text = stat_divs[0].get_text(strip=True)
            overs = float(overs_text) if overs_text.replace('.', '').isdigit() else 0.0
            maidens = int(stat_divs[1].get_text(strip=True)) if stat_divs[1].get_text(strip=True).isdigit() else 0
            runs = int(stat_divs[2].get_text(strip=True)) if stat_divs[2].get_text(strip=True).isdigit() else 0
            wickets = int(stat_divs[3].get_text(strip=True)) if stat_divs[3].get_text(strip=True).isdigit() else 0
            econ_text = stat_divs[4].get_text(strip=True)
            econ = float(econ_text) if econ_text.replace('.', '').isdigit() else 0.0
            bowling.append({'name': name, 'overs': overs, 'maidens': maidens, 'runs': runs, 'wickets': wickets, 'econ': econ})
        except (ValueError, IndexError):
            continue
    return bowling

def extract_start_time_from_match_page(soup):
    date_time_span = soup.find('span', string=re.compile(r'Date & Time:', re.I))
    if date_time_span and date_time_span.find_parent():
        full_text = date_time_span.find_parent().get_text(strip=True)
        return full_text.replace('Date & Time:', '').strip()
    time_pattern = re.compile(r'\d{1,2}:\d{2}\s*(AM|PM)', re.I)
    time_elem = soup.find(string=time_pattern)
    if time_elem:
        return time_elem.strip()
    return None

def extract_match_status_from_match_page(soup):
    def is_valid_status(text):
        if not text or len(text) > 60:
            return False
        bad = ['short ball', 'full toss', 'driven', 'pulled', 'cut', 'swept', 'over mid-wicket', 'long on', 'long off', 'covers', 'point', 'Schedule', 'Archives', 'Rankings', 'Videos', 'More']
        lower = text.lower()
        if any(p in lower for p in bad):
            return False
        keywords = ['won', 'live', 'stumps', 'innings', 'rain', 'abandoned', 'opt', 'target', 'need', 'required', 'break']
        return any(k in lower for k in keywords)

    live_badge = soup.find('span', class_=lambda c: c and 'cb-plus-live-tag' in c)
    if live_badge:
        return "Live"
    status_div = soup.find('div', class_=lambda c: c and 'cb-text-' in c)
    if status_div:
        candidate = status_div.get_text(strip=True)
        if is_valid_status(candidate):
            return candidate
    toss = soup.find('div', string=re.compile(r'opt to (bat|field)', re.I))
    if toss:
        candidate = toss.get_text(strip=True)
        if is_valid_status(candidate):
            return candidate
    result = soup.find('div', string=re.compile(r'won by \d+ (run|wicket)', re.I))
    if result:
        candidate = result.get_text(strip=True)
        if is_valid_status(candidate):
            return candidate
    for kw in ['innings break', 'stumps', 'rain', 'abandoned', 'lunch', 'tea']:
        elem = soup.find('div', string=re.compile(kw, re.I))
        if elem:
            candidate = elem.get_text(strip=True)
            if is_valid_status(candidate):
                return candidate
    preview = soup.find('div', class_=lambda c: c and 'cb-text-preview' in c)
    if preview:
        return "Preview"
    header = soup.find('div', class_=lambda c: c and 'cb-col-100' in c and 'cb-miniscroll' in c)
    if header:
        for elem in header.find_all(['div', 'span']):
            text = elem.get_text(strip=True)
            if is_valid_status(text):
                return text
    return None