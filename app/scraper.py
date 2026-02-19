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
 ----------------------------------------------------------------------
# Live matches list extraction (from homepage)
# ----------------------------------------------------------------------
def extract_live_matches(soup):
    """
    Extract minimal match information from the Cricbuzz homepage.
    Returns a list of dicts with keys: id, teams, title, status, start_time.
    """
    matches = []
    match_blocks = soup.find_all('div', class_='cb-mtch-blk')
    if not match_blocks:
        match_blocks = soup.find_all('div', class_=lambda c: c and 'cb-col-100' in c and 'cb-col' in c)

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
        if title_tag:
            title = title_tag.get_text(strip=True)
        else:
            title = link.get_text(strip=True)

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
        else:
            time_pattern = re.compile(r'\d{1,2}:\d{2}\s*(AM|PM)|Today|Tomorrow', re.I)
            time_elem = block.find(string=time_pattern)
            if time_elem:
                start_time = time_elem.strip()

        matches.append({
            'id': match_id,
            'teams': teams,
            'title': title,
            'status': status,
            'start_time': start_time
        })

    unique = {}
    for m in matches:
        if m['id'] not in unique:
            unique[m['id']] = m
    return list(unique.values())

# ----------------------------------------------------------------------
# Detailed match data extraction (from match scorecard page)
# ----------------------------------------------------------------------
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
    """Extract current score block: team, runs, wickets, overs."""
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

    runs, wickets = 0, 0
    if '-' in runs_wickets:
        parts = runs_wickets.split('-')
        runs = int(parts[0]) if parts[0].isdigit() else 0
        wickets = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
    elif runs_wickets.isdigit():
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
    """Extract current run rate (CRR)."""
    crr_elem = soup.find('span', string=re.compile(r'CRR', re.I))
    if crr_elem and crr_elem.parent:
        numbers = re.findall(r'\d+\.?\d*', crr_elem.parent.get_text())
        if numbers:
            try:
                return float(numbers[0])
            except:
                pass
    return None

def extract_batting(soup):
    """Extract batting list (up to 11)."""
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
        except (ValueError, IndexError) as e:
            logger.debug(f"Error parsing batsman {name}: {e}")
            continue
    return batting

def extract_bowling(soup):
    """Extract bowling list (up to 11)."""
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
        except (ValueError, IndexError) as e:
            logger.debug(f"Error parsing bowler {name}: {e}")
            continue
    return bowling

def extract_start_time_from_match_page(soup):
    """Extract start time from the match facts section."""
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
    """
    Extract the true match status from a match page.
    Returns a short string like 'Live', 'Innings Break', 'Team won by X runs', etc.
    """
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