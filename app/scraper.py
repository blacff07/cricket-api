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

# ----------------------------------------------------------------------
# Live matches list extraction (from homepage)
# ----------------------------------------------------------------------
def extract_live_matches(soup):
    """
    Extract all matches from the Cricbuzz homepage with proper parsing.
    Returns a list of dicts: id, teams, title, status, start_time.
    """
    matches = []
    # Find all links that point to live cricket scores
    for link in soup.find_all('a', href=re.compile(r'/live-cricket-scores/\d+')):
        href = link['href']
        match_id = int(re.search(r'/live-cricket-scores/(\d+)', href).group(1))
        
        # Get the raw title
        title_span = link.find('span', class_='text-hvr-underline')
        if title_span:
            raw_title = title_span.get_text(strip=True)
        else:
            raw_title = link.get_text(strip=True)
        
        # Parse teams and clean title
        teams = []
        clean_title = raw_title
        if ' vs ' in raw_title:
            # Split on ' vs ' and take first two parts
            parts = raw_title.split(' vs ')
            if len(parts) >= 2:
                # First team: before first comma if any
                team1 = parts[0].split(',')[0].strip()
                # Second team: before first comma, and also remove trailing suffixes like "2nd Semi Final"
                team2_part = parts[1]
                # Remove common suffixes (match type, result, etc.)
                team2 = re.sub(r'(\d+(st|nd|rd|th)\s+(Semi\s+)?Final|Eliminator|Match|Preview|won).*$', '', team2_part, flags=re.I).strip()
                teams = [team1, team2]
                # Clean title: remove any extra text after the second team
                clean_title = f"{team1} vs {team2}"
        
        # Find the parent container for status and start time
        parent = link.find_parent(['div', 'li'], class_=lambda c: c and ('cb-mtch-blk' in c or 'cb-col' in c))
        status = "Upcoming"
        start_time = None
        
        if parent:
            # Status detection
            if parent.find('span', class_=lambda c: c and 'cb-plus-live-tag' in c):
                status = "Live"
            elif parent.find('div', class_=lambda c: c and 'cb-text-complete' in c):
                status = "Completed"
            elif parent.find('div', string=re.compile(r'won by|win by|complete', re.I)):
                status = "Completed"
            
            # Start time detection
            time_elem = parent.find('span', class_='sch-date')
            if time_elem:
                start_time = time_elem.get_text(strip=True)
            else:
                # Look for any element with date/time pattern
                time_pattern = re.compile(r'\d{1,2}:\d{2}\s*(AM|PM)|Today|Tomorrow', re.I)
                time_elem = parent.find(string=time_pattern)
                if time_elem:
                    start_time = time_elem.strip()
        
        matches.append({
            'id': match_id,
            'teams': teams,
            'title': clean_title,
            'status': status,
            'start_time': start_time
        })
    
    # Remove duplicates
    unique = {}
    for m in matches:
        if m['id'] not in unique:
            unique[m['id']] = m
    return list(unique.values())

# ----------------------------------------------------------------------
# Detailed match data extraction (robust version)
# ----------------------------------------------------------------------
def extract_match_data(soup):
    """Extract detailed match data from a match scorecard page."""
    # Title
    title_tag = soup.find('h1')
    title = title_tag.get_text(strip=True) if title_tag else None
    if title:
        title = title.replace(', Commentary', '').replace(' - Scorecard', '').strip()

    # Teams from title
    teams = []
    if title and ' vs ' in title:
        parts = title.split(' vs ')
        if len(parts) >= 2:
            teams = [parts[0].split(',')[0].strip(), parts[1].split(',')[0].strip()]

    # Status
    status = extract_match_status_from_match_page(soup) or 'Match Stats will Update Soon...'

    # Current score
    current_score = extract_current_score(soup)

    # Run rate
    run_rate = extract_run_rate(soup)

    # Batting and bowling
    batting = extract_batting(soup)
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
    """Extract current score using multiple possible selectors."""
    # 1️⃣ Look for the common score block (Cricbuzz often uses this structure)
    score_block = soup.find('div', class_=lambda c: c and all(x in c for x in ['font-bold', 'text-xl', 'flex']))
    if score_block:
        team_div = score_block.find('div', class_='mr-2')
        team = team_div.get_text(strip=True) if team_div else ''
        spans = score_block.find_all('span', class_='mr-2')
        if len(spans) >= 2:
            runs_wickets = spans[0].get_text(strip=True)
            overs = spans[1].get_text(strip=True).strip('()')
            runs, wickets = 0, 0
            if '-' in runs_wickets:
                parts = runs_wickets.split('-')
                runs = int(parts[0]) if parts[0].isdigit() else 0
                wickets = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
            elif runs_wickets.isdigit():
                runs = int(runs_wickets)
            overs_float = float(overs) if overs.replace('.', '').isdigit() else 0.0
            return {'team': team, 'runs': runs, 'wickets': wickets, 'overs': overs_float}

    # 2️⃣ Look for score in a div with class containing "cb-score"
    score_elem = soup.find('div', class_=lambda c: c and 'cb-score' in c)
    if score_elem:
        text = score_elem.get_text(strip=True)
        # Pattern: "IND 180/5 (20)"
        match = re.match(r'([A-Za-z]+)\s*(\d+)[/-](\d+)\s*\((\d+\.?\d*)\)', text)
        if match:
            return {
                'team': match.group(1),
                'runs': int(match.group(2)),
                'wickets': int(match.group(3)),
                'overs': float(match.group(4))
            }

    # 3️⃣ Look for any element with a score-like pattern
    for elem in soup.find_all(['div', 'span'], string=re.compile(r'\w+\s+\d+[/-]\d+\s*\(\d+\.?\d*\)')):
        text = elem.get_text(strip=True)
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
    """Extract current run rate (CRR)."""
    # Look for CRR text
    crr_elem = soup.find('span', string=re.compile(r'CRR', re.I))
    if crr_elem:
        parent = crr_elem.parent
        if parent:
            numbers = re.findall(r'\d+\.?\d*', parent.get_text())
            if numbers:
                try:
                    return float(numbers[0])
                except:
                    pass

    # Sometimes CRR is in a separate span
    crr_span = soup.find('span', string=re.compile(r'CRR:\s*\d+\.?\d*', re.I))
    if crr_span:
        numbers = re.findall(r'\d+\.?\d*', crr_span.get_text())
        if numbers:
            try:
                return float(numbers[0])
            except:
                pass

    return None

def extract_batting(soup):
    """Extract batting statistics using multiple strategies."""
    batting = []

    # Strategy 1: Find the batting table (most reliable)
    # Look for a table with headers containing "Batter", "R", "B", "4s", "6s", "SR"
    tables = soup.find_all('table')
    for table in tables:
        header = table.find('tr')
        if header and any('Batter' in th.get_text() for th in header.find_all(['th', 'td'])):
            rows = table.find_all('tr')[1:]  # skip header
            for row in rows:
                cells = row.find_all(['td', 'th'])
                if len(cells) >= 7:
                    name_link = row.find('a', href=lambda h: h and '/profiles/' in h)
                    if not name_link:
                        continue
                    name = name_link.get_text(strip=True).replace(' *', '').replace('†', '')
                    try:
                        runs = int(cells[2].get_text(strip=True)) if cells[2].get_text(strip=True).isdigit() else 0
                        balls = int(cells[3].get_text(strip=True)) if cells[3].get_text(strip=True).isdigit() else 0
                        fours = int(cells[4].get_text(strip=True)) if cells[4].get_text(strip=True).isdigit() else 0
                        sixes = int(cells[5].get_text(strip=True)) if cells[5].get_text(strip=True).isdigit() else 0
                        sr_text = cells[6].get_text(strip=True) if len(cells) > 6 else '0'
                        sr = float(sr_text) if sr_text.replace('.', '').isdigit() else 0.0
                        batting.append({'name': name, 'runs': runs, 'balls': balls, 'fours': fours, 'sixes': sixes, 'sr': sr})
                    except (ValueError, IndexError):
                        continue
            if batting:
                return batting

    # Strategy 2: Look for divs with scorecard grid classes
    rows = soup.find_all('div', class_=lambda c: c and 'scorecard-bat-grid' in c)
    for row in rows:
        name_link = row.find('a', href=lambda h: h and '/profiles/' in h)
        if not name_link:
            continue
        name = name_link.get_text(strip=True).replace(' *', '').replace('†', '')
        stat_divs = row.find_all('div', class_=lambda c: c and 'flex justify-center items-center' in c)
        if len(stat_divs) >= 5:
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
    """Extract bowling statistics using multiple strategies."""
    bowling = []

    # Strategy 1: Find the bowling table
    tables = soup.find_all('table')
    for table in tables:
        header = table.find('tr')
        if header and any('Bowler' in th.get_text() for th in header.find_all(['th', 'td'])):
            rows = table.find_all('tr')[1:]  # skip header
            for row in rows:
                cells = row.find_all(['td', 'th'])
                if len(cells) >= 7:
                    name_link = row.find('a', href=lambda h: h and '/profiles/' in h)
                    if not name_link:
                        continue
                    name = name_link.get_text(strip=True)
                    try:
                        overs_text = cells[2].get_text(strip=True)
                        overs = float(overs_text) if overs_text.replace('.', '').isdigit() else 0.0
                        maidens = int(cells[3].get_text(strip=True)) if cells[3].get_text(strip=True).isdigit() else 0
                        runs = int(cells[4].get_text(strip=True)) if cells[4].get_text(strip=True).isdigit() else 0
                        wickets = int(cells[5].get_text(strip=True)) if cells[5].get_text(strip=True).isdigit() else 0
                        econ_text = cells[6].get_text(strip=True) if len(cells) > 6 else '0'
                        econ = float(econ_text) if econ_text.replace('.', '').isdigit() else 0.0
                        bowling.append({'name': name, 'overs': overs, 'maidens': maidens, 'runs': runs, 'wickets': wickets, 'econ': econ})
                    except (ValueError, IndexError):
                        continue
            if bowling:
                return bowling

    # Strategy 2: Look for divs with scorecard grid classes
    rows = soup.find_all('div', class_=lambda c: c and 'scorecard-bowl-grid' in c)
    for row in rows:
        name_link = row.find('a', href=lambda h: h and '/profiles/' in h)
        if not name_link:
            continue
        name = name_link.get_text(strip=True)
        stat_divs = row.find_all('div', class_=lambda c: c and 'flex justify-center items-center' in c)
        if len(stat_divs) >= 5:
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
    """Extract start time from match facts."""
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
    """Extract the match status (Live, Completed, Innings Break, etc.)."""
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