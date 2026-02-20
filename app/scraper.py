import re
import json
import random
import requests
import logging
from datetime import datetime
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
# JSON extraction from <script id="__NEXT_DATA__">
# ----------------------------------------------------------------------
def extract_json_data(soup):
    script = soup.find('script', id='__NEXT_DATA__')
    if script and script.string:
        try:
            return json.loads(script.string)
        except json.JSONDecodeError:
            logger.error("Failed to parse __NEXT_DATA__ JSON")
    return None

def parse_scorecard_from_json(json_data):
    """
    Parse the JSON structure from Cricbuzz scorecard page.
    Returns a dict with keys: title, teams, status, current_score, run_rate, batting, bowling, start_time.
    """
    try:
        props = json_data['props']['pageProps']
        if 'matchScorecard' not in props:
            return None
        match = props['matchScorecard']
        header = match['matchHeader']

        title = header.get('matchDescription', '')
        teams = [
            header.get('team1', {}).get('name', ''),
            header.get('team2', {}).get('name', '')
        ]
        status = header.get('status', '')

        # Extract start time from JSON (milliseconds timestamp)
        start_time = None
        if 'matchDetails' in header and 'match' in header['matchDetails']:
            match_info = header['matchDetails']['match']
            if 'startDate' in match_info:
                ts = match_info['startDate']
                if ts:
                    try:
                        dt = datetime.fromtimestamp(int(ts) / 1000)
                        start_time = dt.strftime('%a, %b %d, %I:%M %p').replace(' 0', ' ')
                    except:
                        pass

        batting = []
        bowling = []
        current_score = None
        run_rate = None

        # Process all innings to collect batting and bowling
        for innings in match.get('scorecard', []):
            # Batting
            batsmen = innings.get('batTeamDetails', {}).get('batsmanData', [])
            for b in batsmen:
                batting.append({
                    'name': b.get('batName', ''),
                    'runs': int(b.get('runs', 0)),
                    'balls': int(b.get('balls', 0)),
                    'fours': int(b.get('fours', 0)),
                    'sixes': int(b.get('sixes', 0)),
                    'sr': float(b.get('strikeRate', 0))
                })
            # Bowling
            bowlers = innings.get('bowlTeamDetails', {}).get('bowlerData', [])
            for b in bowlers:
                bowling.append({
                    'name': b.get('bowlName', ''),
                    'overs': float(b.get('overs', 0)),
                    'maidens': int(b.get('maidens', 0)),
                    'runs': int(b.get('runs', 0)),
                    'wickets': int(b.get('wickets', 0)),
                    'econ': float(b.get('economy', 0))
                })

        # Set current_score from the first innings (most prominent on the page)
        if match.get('scorecard') and len(match['scorecard']) > 0:
            first_innings = match['scorecard'][0]
            score_details = first_innings.get('batTeamDetails', {}).get('scoreDetails', {})
            if score_details:
                current_score = {
                    'team': first_innings['batTeamDetails'].get('teamName', ''),
                    'runs': score_details.get('runs', 0),
                    'wickets': score_details.get('wickets', 0),
                    'overs': float(score_details.get('overs', 0))
                }
                if current_score['overs'] > 0:
                    run_rate = round(current_score['runs'] / current_score['overs'], 2)

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
    except (KeyError, TypeError, ValueError) as e:
        logger.error(f"Error parsing JSON scorecard: {e}")
        return None

# ----------------------------------------------------------------------
# Live matches list extraction (from homepage /live-scores)
# ----------------------------------------------------------------------
def extract_live_matches(soup):
    matches = []
    # Find ALL links that point to a live cricket score page
    all_links = soup.find_all('a', href=re.compile(r'/live-cricket-scores/\d+'))
    
    for link in all_links:
        href = link.get('href', '')
        match = re.search(r'/live-cricket-scores/(\d+)', href)
        if not match:
            continue
        match_id = int(match.group(1))

        # The link itself is the match container in current Cricbuzz design
        container = link

        # Extract title from 'title' attribute (clean and full)
        title = container.get('title', '').strip()
        if not title:
            title = container.get_text(strip=True)

        # Extract teams – try span-based first, then fallback to title parsing
        teams = []
        # Look for full team name spans (hidden on mobile but present)
        full_team_spans = container.find_all('span', class_=lambda c: c and 'hidden wb:block' in c)
        for span in full_team_spans:
            name = span.get_text(strip=True)
            if name:
                teams.append(name)
        # If not found, use short codes
        if not teams:
            short_spans = container.find_all('span', class_=lambda c: c and 'block wb:hidden' in c)
            for span in short_spans:
                name = span.get_text(strip=True)
                if name:
                    teams.append(name)
        # If still no teams, parse from title (most reliable fallback)
        if not teams and ' vs ' in title:
            # Remove any suffix after " - " to get a cleaner title
            clean_title = re.sub(r'\s+-\s+.*$', '', title)
            if ' vs ' in clean_title:
                parts = clean_title.split(' vs ')
                if len(parts) >= 2:
                    team1 = parts[0].split(',')[0].strip()
                    team2 = parts[1].split(',')[0].strip()
                    teams = [team1, team2]

        # Determine status
        status = "Upcoming"
        # Check for live tag
        if container.find('span', class_='cbPlusLiveTag'):
            status = "Live"
        else:
            # Check for result span
            result_span = container.find('span', class_=lambda c: c and 'text-cbComplete' in c)
            if result_span:
                result_text = result_span.get_text(strip=True).lower()
                if any(word in result_text for word in ['won', 'win', 'complete']):
                    status = "Completed"
                else:
                    status = result_span.get_text(strip=True)  # e.g., "Innings Break"
            else:
                # Fallback to title keywords
                lower_title = title.lower()
                if any(word in lower_title for word in ['won', 'complete', 'match drawn', 'abandoned']):
                    status = "Completed"
                elif any(word in lower_title for word in ['opt to', 'toss', 'stumps', 'lunch', 'tea', 'day', 'innings break', 'need', 'require', 'trail', 'lead']):
                    status = "Live"

        # Extract start time if present
        start_time = None
        time_elem = container.find('span', class_='sch-date')
        if time_elem:
            start_time = time_elem.get_text(strip=True)
        else:
            time_pattern = re.compile(r'\d{1,2}:\d{2}\s*(AM|PM)|Today|Tomorrow', re.I)
            time_elem = container.find(string=time_pattern)
            if time_elem:
                start_time = time_elem.strip()

        matches.append({
            'id': match_id,
            'teams': teams,
            'title': title,
            'status': status,
            'start_time': start_time
        })

    # Remove duplicates (some matches may have multiple links)
    unique = {}
    for m in matches:
        if m['id'] not in unique:
            unique[m['id']] = m
    return list(unique.values())

# ----------------------------------------------------------------------
# Detailed match data extraction (from match scorecard page)
# ----------------------------------------------------------------------
def extract_match_data(soup):
    """Extract detailed match data, trying JSON first, then HTML."""
    # First try JSON
    json_data = extract_json_data(soup)
    if json_data:
        data = parse_scorecard_from_json(json_data)
        if data:
            return data

    logger.warning("JSON extraction failed, falling back to HTML parsing")
    # Fallback: HTML parsing
    title_tag = soup.find('h1')
    title = title_tag.get_text(strip=True) if title_tag else None
    if title:
        title = title.replace(', Commentary', '').replace(' - Scorecard', '').strip()

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
    """Extract current score using multiple possible selectors."""
    # Look for score in a div with class containing "cb-score"
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
    # Alternative: look for a div with font-bold text-xl flex
    score_block = soup.find('div', class_=lambda c: c and 'font-bold' in c and 'text-xl' in c and 'flex' in c)
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
    return None

def extract_run_rate(soup):
    """Extract current run rate (CRR)."""
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
    """Extract start time from match facts (HTML fallback)."""
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
    """Extract the match status (Live, Completed, Innings Break, etc.) from HTML."""
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