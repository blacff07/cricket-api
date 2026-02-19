# app/scraper.py
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

def extract_live_matches(soup):
    """Extract live matches from the Cricbuzz homepage."""
    matches = []
    for a in soup.find_all('a', href=True):
        href = a['href']
        if '/live-cricket-scores/' not in href:
            continue
        match = re.search(r'/live-cricket-scores/(\d+)', href)
        if not match:
            continue
        match_id = match.group(1)
        title_attr = a.get('title', '')
        if title_attr:
            title = title_attr
        else:
            title = a.get_text(strip=True)
        
        # Determine status (improved)
        lower_title = title.lower()
        if 'live' in lower_title:
            status = "Live"
        elif any(word in lower_title for word in ['won', 'complete', 'stumps', 'drawn', 'rain']):
            status = "Completed"
        else:
            status = "Upcoming"
        
        # Parse teams (with fallback)
        teams = []
        if ' vs ' in title:
            teams_part = title.split(' vs ')[0]
            teams = [teams_part.split(',')[0].strip()]
            second_part = title.split(' vs ')[1]
            teams.append(second_part.split(',')[0].strip())
        else:
            # Fallback: try to extract two-letter team codes from title
            codes = re.findall(r'\b[A-Z]{2,4}\b', title)
            if len(codes) >= 2:
                teams = codes[:2]
        
        # Parse series
        series = "Unknown Series"
        if ',' in title:
            parts = title.split(',')
            if len(parts) > 1:
                series = parts[1].strip()
        elif teams and len(teams) >= 2:
            # Try to extract series from the remainder after team names
            remainder = title.replace(teams[0], '').replace(teams[1], '').strip()
            if remainder:
                series = remainder.strip('- ').strip()
        
        matches.append({
            'id': int(match_id),
            'teams': teams,
            'title': title,
            'series': series,
            'status': status,
            'link': href
        })
    
    # Remove duplicates by ID
    unique = {}
    for m in matches:
        if m['id'] not in unique:
            unique[m['id']] = m
    return list(unique.values())

def detect_match_state(soup):
    """Detect the current state of the match."""
    # Check for completion message
    complete_div = soup.find('div', class_=lambda c: c and 'cb-text-complete' in c)
    if complete_div:
        return "completed"
    
    # Check for match result indicators (team won)
    result_text = soup.find(string=re.compile(r'won by|win by', re.I))
    if result_text:
        return "completed"
    
    # Check for innings break
    innings_div = soup.find('div', string=re.compile(r'Innings Break', re.I))
    if innings_div:
        return "innings_break"
    
    # Check for live status
    live_tag = soup.find('span', class_=lambda c: c and 'cb-plus-live-tag' in c)
    if live_tag:
        return "live"
    
    # Check if match hasn't started
    preview_div = soup.find('div', class_=lambda c: c and 'cb-text-preview' in c)
    if preview_div:
        return "not_started"
    
    return "unknown"

def extract_match_data(soup):
    """Extract detailed match data from a match page."""
    # Title
    title_tag = soup.find('h1')
    title = title_tag.text.strip().replace(', Commentary', '') if title_tag else None

    # Series
    series = "Unknown Series"
    if title and ',' in title:
        parts = title.split(',')
        if len(parts) > 1:
            series = parts[1].strip()

    # Teams
    teams = []
    if title and ' vs ' in title:
        teams_part = title.split(' vs ')[0]
        teams = [teams_part.split(',')[0].strip()]
        second_part = title.split(' vs ')[1]
        teams.append(second_part.split(',')[0].strip())

    # Status (update) - FIXED VERSION
    status = 'Match Stats will Update Soon...'
    
    # Method 1: Look for the match status in the main header or score area
    status_elements = soup.find_all(['div', 'span'], string=re.compile(r'(won|live|stumps|innings break|rain|abandoned|opt to bat|opt to field|target|need|required|overnight)', re.I))
    for elem in status_elements:
        if elem.text and len(elem.text.strip()) < 50:  # Avoid long paragraphs
            possible_status = elem.text.strip()
            # Make sure it's not part of a larger title
            if any(keyword in possible_status.lower() for keyword in ['won', 'live', 'stumps', 'innings', 'rain', 'abandoned', 'opt', 'target', 'need', 'required', 'overnight']):
                status = possible_status
                break
    
    # Method 2: If not found, try the match bar (more specific targeting)
    if status == 'Match Stats will Update Soon...':
        match_bar = soup.find('div', class_=lambda c: c and 'bg-[#4a4a4a]' in c)
        if match_bar:
            # Find the specific match link in the bar - it's usually the first one
            match_links = match_bar.find_all('a', title=True)
            for link in match_links[:3]:  # Only check first few links
                title_attr = link.get('title', '')
                if ' vs ' in title_attr:
                    parts = title_attr.split('-')
                    if len(parts) > 1:
                        candidate = parts[-1].strip()
                        # Verify this looks like a valid status (not a team name from another match)
                        if not any(team in candidate for team in ['IND', 'PAK', 'AUS', 'ENG', 'NZ', 'SA', 'SL', 'WI', 'AFG', 'BAN', 'ZIM']):
                            status = candidate
                            break
    
    # Method 3: Look for cb-text-* class (Cricbuzz's status indicator)
    if status == 'Match Stats will Update Soon...':
        status_div = soup.find('div', class_=lambda c: c and 'cb-text-' in c)
        if status_div:
            candidate = status_div.text.strip()
            # Filter out team names masquerading as status
            if not any(team in candidate for team in ['IND', 'PAK', 'AUS', 'ENG', 'NZ', 'SA', 'SL', 'WI', 'AFG', 'BAN', 'ZIM']):
                status = candidate

    # Match state
    match_state = detect_match_state(soup)

    # Live score
    livescore = None
    current_score = None
    runrate = None
    
    score_block = soup.find('div', class_=lambda c: c and 'font-bold' in c and 'text-xl' in c and 'flex' in c)
    if score_block:
        team_div = score_block.find('div', class_='mr-2')
        team = team_div.text.strip() if team_div else ''
        spans = score_block.find_all('span', class_='mr-2')
        if len(spans) >= 2:
            runs_wickets = spans[0].get_text(strip=True)
            overs = spans[1].get_text(strip=True).strip('()')
            livescore = f"{team} {runs_wickets} ({overs})"
            
            # Parse runs and wickets
            runs = 0
            wickets = 0
            if '-' in runs_wickets:
                parts = runs_wickets.split('-')
                try:
                    runs = int(parts[0]) if parts[0].isdigit() else 0
                except (ValueError, IndexError):
                    runs = 0
                try:
                    wickets = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
                except (ValueError, IndexError):
                    wickets = 0
            
            overs_float = 0
            try:
                overs_float = float(overs) if overs else 0
            except ValueError:
                overs_float = 0
                
            current_score = {
                'team': team,
                'runs': runs,
                'wickets': wickets,
                'overs': overs_float
            }

    # CRR
    crr_label = soup.find('span', string=re.compile(r'CRR', re.I))
    if crr_label:
        value_span = crr_label.find_next_sibling('span')
        if value_span:
            try:
                runrate = float(value_span.text.strip())
            except ValueError:
                runrate = None
        else:
            parent = crr_label.parent
            values = parent.find_all('span')
            if len(values) > 1:
                try:
                    runrate = float(values[-1].text.strip())
                except ValueError:
                    runrate = None
    
    if not runrate:
        crr_div = soup.find('div', string=re.compile(r'CRR', re.I))
        if crr_div:
            crr_text = crr_div.get_text(strip=True).replace('CRR', '').strip()
            try:
                runrate = float(crr_text)
            except ValueError:
                runrate = None

    # Batsmen
    batsmen = []
    rows = soup.find_all('div', class_=lambda c: c and 'scorecard-bat-grid' in c and 'grid' in c)
    for row in rows:
        name_link = row.find('a', href=lambda h: h and '/profiles/' in h)
        if not name_link:
            continue
        name = name_link.text.strip().replace(' *', '').replace('†', '')
        stat_divs = row.find_all('div', class_=lambda c: c and 'flex justify-center items-center' in c)
        if len(stat_divs) >= 5:
            try:
                # Parse runs
                runs = 0
                if stat_divs[0].text.strip().isdigit():
                    runs = int(stat_divs[0].text.strip())
                
                # Parse balls
                balls = 0
                if stat_divs[1].text.strip().isdigit():
                    balls = int(stat_divs[1].text.strip())
                
                # Parse fours
                fours = 0
                if stat_divs[2].text.strip().isdigit():
                    fours = int(stat_divs[2].text.strip())
                
                # Parse sixes
                sixes = 0
                if stat_divs[3].text.strip().isdigit():
                    sixes = int(stat_divs[3].text.strip())
                
                # Parse strike rate
                sr = 0.0
                sr_text = stat_divs[4].text.strip()
                if sr_text and sr_text.replace('.', '').isdigit():
                    sr = float(sr_text)
                
                batsmen.append({
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

    # Bowlers
    bowlers = []
    bowler_header = soup.find('div', string='Bowler')
    if bowler_header:
        parent = bowler_header.find_parent()
        bowler_rows = parent.find_all_next('div', class_=lambda c: c and 'scorecard-bat-grid' in c and 'grid' in c)
        for row in bowler_rows[:5]:
            name_link = row.find('a', href=lambda h: h and '/profiles/' in h)
            if not name_link:
                continue
            name = name_link.text.strip()
            stat_divs = row.find_all('div', class_=lambda c: c and 'flex justify-center items-center' in c)
            if len(stat_divs) >= 5:
                try:
                    # Parse overs
                    overs = 0.0
                    overs_text = stat_divs[0].text.strip()
                    if overs_text and overs_text.replace('.', '').isdigit():
                        overs = float(overs_text)
                    
                    # Parse maidens
                    maidens = 0
                    if stat_divs[1].text.strip().isdigit():
                        maidens = int(stat_divs[1].text.strip())
                    
                    # Parse runs
                    runs = 0
                    if stat_divs[2].text.strip().isdigit():
                        runs = int(stat_divs[2].text.strip())
                    
                    # Parse wickets
                    wickets = 0
                    if stat_divs[3].text.strip().isdigit():
                        wickets = int(stat_divs[3].text.strip())
                    
                    # Parse economy
                    econ = 0.0
                    econ_text = stat_divs[4].text.strip()
                    if econ_text and econ_text.replace('.', '').isdigit():
                        econ = float(econ_text)
                    
                    bowlers.append({
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

    # Start time
    start_time = None
    # Look for the Date & Time label
    date_time_span = soup.find('span', string=re.compile(r'Date & Time:', re.I))
    if date_time_span:
        parent = date_time_span.find_parent()
        if parent:
            full_text = parent.get_text(strip=True)
            start_time = full_text.replace('Date & Time:', '').strip()
    else:
        # Fallback: look for any element containing a time pattern
        time_elem = soup.find(string=re.compile(r'\d{1,2}:\d{2}\s*(AM|PM)', re.I))
        if time_elem:
            start_time = time_elem.strip()

    return {
        'title': title,
        'series': series,
        'teams': teams,
        'status': status,
        'match_state': match_state,
        'start_time': start_time,
        'current_score': current_score,
        'livescore': livescore,
        'run_rate': runrate,
        'batting': batsmen,
        'bowling': bowlers
    }

def extract_match_status_from_match_page(soup):
    """Extract the true match status from a match page."""

    # 1️⃣ Most reliable: the live badge (returns "Live")
    live_badge = soup.find('span', class_=lambda c: c and 'cb-plus-live-tag' in c)
    if live_badge:
        return "Live"

    # 2️⃣ Look for the main status div (often contains 'cb-text-' class)
    status_div = soup.find('div', class_=lambda c: c and 'cb-text-' in c)
    if status_div:
        candidate = status_div.text.strip()
        if candidate and len(candidate) < 50:
            return candidate

    # 3️⃣ Look for toss/opt text
    toss_elem = soup.find('div', string=re.compile(r'opt to (bat|field)', re.I))
    if toss_elem:
        return toss_elem.text.strip()

    # 4️⃣ Look for result text (e.g., "Team won by X runs")
    result = soup.find('div', string=re.compile(r'won by \d+ (run|wicket)', re.I))
    if result:
        return result.text.strip()

    # 5️⃣ Look for innings break / stumps / rain
    status_keywords = ['innings break', 'stumps', 'rain', 'abandoned', 'lunch', 'tea']
    for kw in status_keywords:
        elem = soup.find('div', string=re.compile(kw, re.I))
        if elem:
            return elem.text.strip()

    # 6️⃣ Preview
    preview = soup.find('div', class_=lambda c: c and 'cb-text-preview' in c)
    if preview:
        return "Preview"

    # 7️⃣ Fallback – look for ANY small div/span with status-like text
    # But EXCLUDE script tags and large blocks
    for elem in soup.find_all(['div', 'span']):
        if elem.name == 'script':
            continue  # Skip script tags entirely
        text = elem.get_text(strip=True)
        if not text or len(text) > 100:
            continue  # Skip empty or very long text
        if any(kw in text.lower() for kw in ['won', 'live', 'stumps', 'innings', 'rain', 'abandoned', 'opt', 'target']):
            return text

    return None

def extract_start_time_from_match_page(soup):
    """Extract only the start time from a match page (lighter version)."""
    start_time = None
    # Look for the Date & Time label
    date_time_span = soup.find('span', string=re.compile(r'Date & Time:', re.I))
    if date_time_span:
        parent = date_time_span.find_parent()
        if parent:
            full_text = parent.get_text(strip=True)
            start_time = full_text.replace('Date & Time:', '').strip()
    if not start_time:
        # Fallback: look for any element containing a time pattern
        time_elem = soup.find(string=re.compile(r'\d{1,2}:\d{2}\s*(AM|PM)', re.I))
        if time_elem:
            start_time = time_elem.strip()
    return start_time