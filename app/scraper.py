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
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Cache-Control': 'no-cache'
    }
    try:
        resp = requests.get(url, headers=headers, timeout=Config.REQUEST_TIMEOUT)
        resp.raise_for_status()
        logger.debug(f"Fetched {url}, status {resp.status_code}")
        return BeautifulSoup(resp.content, 'lxml'), None
    except requests.exceptions.Timeout:
        logger.error(f"Timeout fetching {url}")
        return None, "timeout"
    except requests.exceptions.ConnectionError:
        logger.error(f"Connection error fetching {url}")
        return None, "connection_error"
    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP error {e.response.status_code} fetching {url}")
        if e.response:
            logger.error(f"Response snippet: {e.response.text[:200]}")
        return None, f"http_{e.response.status_code}"
    except Exception as e:
        logger.error(f"Unexpected error fetching {url}: {e}")
        return None, "unknown"

def extract_live_matches(soup):
    """Extract live matches from the Cricbuzz homepage using anchor tags."""
    matches = []
    all_links = soup.find_all('a', href=True)
    logger.debug(f"Found {len(all_links)} total links on the page")
    
    for a in all_links:
        href = a['href']
        if '/live-cricket-scores/' not in href:
            continue
        match = re.search(r'/live-cricket-scores/(\d+)', href)
        if not match:
            continue
        match_id = int(match.group(1))
        
        title_attr = a.get('title', '')
        if title_attr:
            title = title_attr
        else:
            title = a.get_text(strip=True)
        if not title:
            continue
        
        lower_title = title.lower()
        if 'live' in lower_title:
            status = "Live"
        elif any(word in lower_title for word in ['won', 'complete', 'stumps', 'drawn', 'rain']):
            status = "Completed"
        else:
            status = "Upcoming"
        
        teams = []
        if ' vs ' in title:
            teams_part = title.split(' vs ')[0]
            teams = [teams_part.split(',')[0].strip()]
            second_part = title.split(' vs ')[1]
            teams.append(second_part.split(',')[0].strip())
        else:
            codes = re.findall(r'\b[A-Z]{2,4}\b', title)
            if len(codes) >= 2:
                teams = codes[:2]
        
        matches.append({
            'id': match_id,
            'teams': teams,
            'title': title,
            'status': status,
            'link': href
        })
    
    unique = {m['id']: m for m in matches}
    result = list(unique.values())
    logger.info(f"Extracted {len(result)} unique matches")
    return result

def extract_match_data(soup):
    """Extract detailed match data from a match scorecard page."""
    title_tag = soup.find('h1')
    if title_tag:
        title = title_tag.get_text(strip=True)
        title = title.replace(', Commentary', '').replace(' - Scorecard', '').strip()
    else:
        title = None

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
    score_block = soup.find('div', class_=lambda c: c and 'font-bold' in c and 'text-xl' in c and 'flex' in c)
    if not score_block:
        return None

    team_div = score_block.find('div', class_='mr-2')
    team = team_div.get_text(strip=True) if team_div else ''

    spans = score_block.find_all('span', class_='mr-2')
    if len(spans) < 2:
        return None

    runs_wickets = spans[0].get_text(strip=True)
    overs = spans[1].get_text(strip=True).strip('()')

    runs = 0
    wickets = 0
    if '-' in runs_wickets:
        parts = runs_wickets.split('-')
        try:
            runs = int(parts[0]) if parts[0].isdigit() else 0
        except:
            runs = 0
        try:
            wickets = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
        except:
            wickets = 0
    else:
        if runs_wickets.isdigit():
            runs = int(runs_wickets)

    overs_float = 0.0
    try:
        overs_float = float(overs) if overs.replace('.', '').isdigit() else 0.0
    except:
        pass

    return {
        'team': team,
        'runs': runs,
        'wickets': wickets,
        'overs': overs_float
    }

def extract_run_rate(soup):
    crr_elem = soup.find('span', string=re.compile(r'CRR', re.I))
    if crr_elem:
        parent = crr_elem.parent
        if parent:
            value_span = crr_elem.find_next_sibling('span')
            if value_span:
                try:
                    return float(value_span.get_text(strip=True))
                except:
                    pass
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
    for row in rows:
        name_link = row.find('a', href=lambda h: h and '/profiles/' in h)
        if not name_link:
            continue
        name = name_link.get_text(strip=True).replace(' *', '').replace('†', '')
        stat_divs = row.find_all('div', class_=lambda c: c and 'flex justify-center items-center' in c)
        if len(stat_divs) < 5:
            continue
        try:
            runs = int(stat_divs[0].get_text(strip=True)) if stat_divs[0].get_text(strip=True).isdigit() else 0
            balls = int(stat_divs[1].get_text(strip=True)) if stat_divs[1].get_text(strip=True).isdigit() else 0
            fours = int(stat_divs[2].get_text(strip=True)) if stat_divs[2].get_text(strip=True).isdigit() else 0
            sixes = int(stat_divs[3].get_text(strip=True)) if stat_divs[3].get_text(strip=True).isdigit() else 0
            sr_text = stat_divs[4].get_text(strip=True)
            sr = float(sr_text) if sr_text.replace('.', '').isdigit() else 0.0
            batting.append({
                'name': name,
                'runs': runs,
                'balls': balls,
                'fours': fours,
                'sixes': sixes,
                'sr': sr
            })
        except (ValueError, IndexError):
            continue
    return batting

def extract_bowling(soup):
    bowling = []
    rows = soup.find_all('div', class_=lambda c: c and 'scorecard-bowl-grid' in c)
    for row in rows:
        name_link = row.find('a', href=lambda h: h and '/profiles/' in h)
        if not name_link:
            continue
        name = name_link.get_text(strip=True)
        stat_divs = row.find_all('div', class_=lambda c: c and 'flex justify-center items-center' in c)
        if len(stat_divs) < 5:
            continue
        try:
            overs_text = stat_divs[0].get_text(strip=True)
            overs = float(overs_text) if overs_text.replace('.', '').isdigit() else 0.0
            maidens = int(stat_divs[1].get_text(strip=True)) if stat_divs[1].get_text(strip=True).isdigit() else 0
            runs = int(stat_divs[2].get_text(strip=True)) if stat_divs[2].get_text(strip=True).isdigit() else 0
            wickets = int(stat_divs[3].get_text(strip=True)) if stat_divs[3].get_text(strip=True).isdigit() else 0
            econ_text = stat_divs[4].get_text(strip=True)
            econ = float(econ_text) if econ_text.replace('.', '').isdigit() else 0.0
            bowling.append({
                'name': name,
                'overs': overs,
                'maidens': maidens,
                'runs': runs,
                'wickets': wickets,
                'econ': econ
            })
        except (ValueError, IndexError):
            continue
    return bowling

def extract_start_time_from_match_page(soup):
    start_time = None
    date_time_span = soup.find('span', string=re.compile(r'Date & Time:', re.I))
    if date_time_span:
        parent = date_time_span.find_parent()
        if parent:
            full_text = parent.get_text(strip=True)
            start_time = full_text.replace('Date & Time:', '').strip()
    if not start_time:
        time_elem = soup.find(string=re.compile(r'\d{1,2}:\d{2}\s*(AM|PM)', re.I))
        if time_elem:
            start_time = time_elem.strip()
    return start_time

def extract_match_status_from_match_page(soup):
    def is_valid_status(text):
        if not text or len(text) > 60:
            return False
        bad_patterns = [
            'short ball', 'full toss', 'driven', 'pulled', 'cut', 'swept',
            'over mid-wicket', 'long on', 'long off', 'covers', 'point',
            'Schedule', 'Archives', 'Rankings', 'Videos', 'More'
        ]
        lower_text = text.lower()
        for pattern in bad_patterns:
            if pattern in lower_text:
                return False
        status_keywords = ['won', 'live', 'stumps', 'innings', 'rain',
                          'abandoned', 'opt', 'target', 'need', 'required', 'break']
        return any(kw in lower_text for kw in status_keywords)

    live_badge = soup.find('span', class_=lambda c: c and 'cb-plus-live-tag' in c)
    if live_badge:
        return "Live"

    status_div = soup.find('div', class_=lambda c: c and 'cb-text-' in c)
    if status_div:
        candidate = status_div.get_text(strip=True)
        if is_valid_status(candidate):
            return candidate

    toss_elem = soup.find('div', string=re.compile(r'opt to (bat|field)', re.I))
    if toss_elem:
        candidate = toss_elem.get_text(strip=True)
        if is_valid_status(candidate):
            return candidate

    result_elem = soup.find('div', string=re.compile(r'won by \d+ (run|wicket)', re.I))
    if result_elem:
        candidate = result_elem.get_text(strip=True)
        if is_valid_status(candidate):
            return candidate

    status_keywords = ['innings break', 'stumps', 'rain', 'abandoned', 'lunch', 'tea']
    for kw in status_keywords:
        elem = soup.find('div', string=re.compile(kw, re.I))
        if elem:
            candidate = elem.get_text(strip=True)
            if is_valid_status(candidate):
                return candidate

    preview_div = soup.find('div', class_=lambda c: c and 'cb-text-preview' in c)
    if preview_div:
        return "Preview"

    header = soup.find('div', class_=lambda c: c and 'cb-col-100' in c and 'cb-miniscroll' in c)
    if header:
        for elem in header.find_all(['div', 'span']):
            text = elem.get_text(strip=True)
            if is_valid_status(text):
                return text

    return None