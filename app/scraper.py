import re
import random
import requests
import logging
from bs4 import BeautifulSoup
from .config import Config

logger = logging.getLogger(__name__)

def get_random_agent():
    """Return a random user agent from the configuration list."""
    return random.choice(Config.USER_AGENTS)

def fetch_page(url):
    """Fetch a page from Cricbuzz and return a BeautifulSoup object."""
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

# ----------------------------------------------------------------------
# Live matches list extraction (from homepage)
# ----------------------------------------------------------------------
def extract_live_matches(soup):
    """
    Extract minimal match information from the Cricbuzz homepage.
    Returns a list of dicts with keys: id, teams, title, status, start_time.
    """
    matches = []
    # Find all match blocks – adjust container class as needed
    match_blocks = soup.find_all('div', class_='cb-mtch-blk')
    if not match_blocks:
        # Fallback: look for any match links in case the structure changed
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

        # Title – often inside link with class 'text-hvr-underline' or simply link text
        title_tag = link.find('span', class_=lambda c: c and 'text-hvr-underline' in c)
        if title_tag:
            title = title_tag.get_text(strip=True)
        else:
            title = link.get_text(strip=True)

        # Teams – parse from title (fallback)
        teams = []
        if ' vs ' in title:
            parts = title.split(' vs ')
            if len(parts) >= 2:
                teams = [parts[0].split(',')[0].strip(), parts[1].split(',')[0].strip()]

        # Status – look for live/completed indicators
        status = "Upcoming"
        if block.find('span', class_=lambda c: c and 'cb-plus-live-tag' in c):
            status = "Live"
        elif block.find('div', class_=lambda c: c and 'cb-text-complete' in c):
            status = "Completed"
        elif block.find('div', string=re.compile(r'won by|win by', re.I)):
            status = "Completed"

        # Start time – look for span with class 'sch-date' or similar
        start_time = None
        time_elem = block.find('span', class_='sch-date')
        if time_elem:
            start_time = time_elem.get_text(strip=True)
        else:
            # Try to find any element containing a time pattern
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

    # Remove duplicates by ID (in case of multiple links to same match)
    unique = {}
    for m in matches:
        if m['id'] not in unique:
            unique[m['id']] = m
    return list(unique.values())

# ----------------------------------------------------------------------
# Detailed match data extraction (from match scorecard page)
# ----------------------------------------------------------------------
def extract_match_data(soup):
    """
    Extract detailed match data from a match scorecard page.
    Returns a dict with keys:
        title, teams, status, start_time, current_score, run_rate, batting, bowling
    """
    # Title
    title_tag = soup.find('h1')
    if title_tag:
        title = title_tag.get_text(strip=True)
        # Remove common suffixes
        title = title.replace(', Commentary', '').replace(' - Scorecard', '').strip()
    else:
        title = None

    # Teams from title
    teams = []
    if title and ' vs ' in title:
        parts = title.split(' vs ')
        if len(parts) >= 2:
            teams = [parts[0].split(',')[0].strip(), parts[1].split(',')[0].strip()]

    # Status – use dedicated robust function
    status = extract_match_status_from_match_page(soup) or 'Match Stats will Update Soon...'

    # Current score
    current_score = extract_current_score(soup)

    # Run rate
    run_rate = extract_run_rate(soup)

    # Batting
    batting = extract_batting(soup)

    # Bowling
    bowling = extract_bowling(soup)

    # Start time
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
    # Look for the score block with classes font-bold, text-xl, flex
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

    # Parse runs and wickets
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
        # Fallback: maybe just runs (e.g., in test matches)
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
    """Extract current run rate (CRR)."""
    crr_elem = soup.find('span', string=re.compile(r'CRR', re.I))
    if crr_elem:
        # Try to get the next sibling containing the number
        parent = crr_elem.parent
        if parent:
            # Look for a span that holds the value
            value_span = crr_elem.find_next_sibling('span')
            if value_span:
                try:
                    return float(value_span.get_text(strip=True))
                except:
                    pass
            # Fallback: extract any number from parent text
            numbers = re.findall(r'\d+\.?\d*', parent.get_text())
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
    # Look for the Date & Time label
    date_time_span = soup.find('span', string=re.compile(r'Date & Time:', re.I))
    if date_time_span:
        parent = date_time_span.find_parent()
        if parent:
            full_text = parent.get_text(strip=True)
            return full_text.replace('Date & Time:', '').strip()
    # Fallback: look for any element containing a time pattern
    time_pattern = re.compile(r'\d{1,2}:\d{2}\s*(AM|PM)', re.I)
    time_elem = soup.find(string=time_pattern)
    if time_elem:
        return time_elem.strip()
    return None

# ----------------------------------------------------------------------
# Status extraction (robust, multi‑method)
# ----------------------------------------------------------------------
def extract_match_status_from_match_page(soup):
    """
    Extract the true match status from a match page.
    Returns a short string like 'Live', 'Innings Break', 'Team won by X runs', etc.
    """
    # ----- Helper to reject invalid status strings -----
    def is_valid_status(text):
        if not text or len(text) > 60:
            return False
        # Reject anything that looks like commentary or nav menu
        bad_patterns = [
            'short ball', 'full toss', 'driven', 'pulled', 'cut', 'swept',
            'over mid-wicket', 'long on', 'long off', 'covers', 'point',
            'Schedule', 'Archives', 'Rankings', 'Videos', 'More'
        ]
        lower_text = text.lower()
        for pattern in bad_patterns:
            if pattern in lower_text:
                return False
        # Must contain at least one status-like word
        status_keywords = ['won', 'live', 'stumps', 'innings', 'rain',
                          'abandoned', 'opt', 'target', 'need', 'required', 'break']
        return any(kw in lower_text for kw in status_keywords)

    # 1️⃣ Most reliable: the live badge
    live_badge = soup.find('span', class_=lambda c: c and 'cb-plus-live-tag' in c)
    if live_badge:
        return "Live"

    # 2️⃣ Look for the main status div (often has 'cb-text-' class)
    status_div = soup.find('div', class_=lambda c: c and 'cb-text-' in c)
    if status_div:
        candidate = status_div.get_text(strip=True)
        if is_valid_status(candidate):
            return candidate

    # 3️⃣ Look for toss/opt text
    toss_elem = soup.find('div', string=re.compile(r'opt to (bat|field)', re.I))
    if toss_elem:
        candidate = toss_elem.get_text(strip=True)
        if is_valid_status(candidate):
            return candidate

    # 4️⃣ Look for result text
    result_elem = soup.find('div', string=re.compile(r'won by \d+ (run|wicket)', re.I))
    if result_elem:
        candidate = result_elem.get_text(strip=True)
        if is_valid_status(candidate):
            return candidate

    # 5️⃣ Look for innings break / stumps / rain
    status_keywords = ['innings break', 'stumps', 'rain', 'abandoned', 'lunch', 'tea']
    for kw in status_keywords:
        elem = soup.find('div', string=re.compile(kw, re.I))
        if elem:
            candidate = elem.get_text(strip=True)
            if is_valid_status(candidate):
                return candidate

    # 6️⃣ Preview (match not started)
    preview_div = soup.find('div', class_=lambda c: c and 'cb-text-preview' in c)
    if preview_div:
        return "Preview"

    # 7️⃣ Fallback – scan only elements in the match header area
    header = soup.find('div', class_=lambda c: c and 'cb-col-100' in c and 'cb-miniscroll' in c)
    if header:
        for elem in header.find_all(['div', 'span']):
            text = elem.get_text(strip=True)
            if is_valid_status(text):
                return text

    return None

# (Optional: keep detect_match_state if needed elsewhere, but not used by bot)
def detect_match_state(soup):
    """Detect the current state of the match (e.g., 'completed', 'innings_break')."""
    if extract_match_status_from_match_page(soup) == "Live":
        return "live"
    if soup.find('div', string=re.compile(r'Innings Break', re.I)):
        return "innings_break"
    if soup.find('div', string=re.compile(r'won by|win by', re.I)):
        return "completed"
    if soup.find('div', class_=lambda c: c and 'cb-text-preview' in c):
        return "not_started"
    return "unknown"