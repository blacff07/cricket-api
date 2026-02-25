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
        
        title = re.sub(r'\s+', ' ', title).strip()
        title = title.replace('WATCH NOW', '').replace('T20I', '').strip()
        
        lower_title = title.lower()
        if 'live' in lower_title:
            status = "Live"
        elif any(word in lower_title for word in ['won', 'complete', 'stumps', 'drawn', 'rain']):
            status = "Completed"
        else:
            status = "Upcoming"
        
        teams = []
        vs_match = re.search(r'([A-Za-z\s]+?)\s+vs\s+([A-Za-z\s]+)', title, re.I)
        if vs_match:
            team1 = vs_match.group(1).strip()
            team2 = vs_match.group(2).strip()
            if team1 and team2:
                teams = [team1, team2]
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

# ----------------------------------------------------------------------
# Detailed match data extraction - SIMPLIFIED VERSION
# ----------------------------------------------------------------------
def extract_match_data(soup):
    """Extract detailed match data from a match scorecard page."""
    # Title
    title_tag = soup.find('h1')
    if title_tag:
        title = title_tag.get_text(strip=True)
        title = title.replace(', Commentary', '').replace(' - Scorecard', '').strip()
    else:
        title = None

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
    
    # Batting - SIMPLIFIED
    batting = extract_batting_simple(soup)
    
    # Bowling - SIMPLIFIED
    bowling = extract_bowling_simple(soup)
    
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
    # Look for the score block with team name
    score_blocks = soup.find_all('div', class_=lambda c: c and 'cb-col-100' in c and 'cb-col' in c)
    
    for block in score_blocks:
        # Look for a div with team name
        team_div = block.find('div', class_=lambda c: c and 'cb-col-40' in c)
        if not team_div:
            continue
            
        team = team_div.get_text(strip=True)
        if not team:
            continue
            
        # Look for score in the same block
        score_divs = block.find_all('div', class_=lambda c: c and 'cb-col-20' in c)
        if len(score_divs) >= 2:
            runs_wickets = score_divs[0].get_text(strip=True)
            overs = score_divs[1].get_text(strip=True).strip('()')
            
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
    
    return None

def extract_run_rate(soup):
    """Extract current run rate (CRR)."""
    crr_elem = soup.find(string=re.compile(r'CRR:', re.I))
    if crr_elem:
        # Get the parent and extract number
        parent = crr_elem.parent
        if parent:
            text = parent.get_text()
            match = re.search(r'CRR:\s*(\d+\.?\d*)', text, re.I)
            if match:
                try:
                    return float(match.group(1))
                except:
                    pass
    return None

def extract_batting_simple(soup):
    """Extract batting list - SIMPLIFIED version."""
    batting = []
    
    # Find all rows that might contain batting data
    # Look for divs with player profile links
    profile_links = soup.find_all('a', href=lambda h: h and '/profiles/' in h)
    
    for link in profile_links:
        # Get the parent row
        row = link.find_parent('div', class_=lambda c: c and 'cb-col' in c)
        if not row:
            continue
            
        # Get player name
        name = link.get_text(strip=True).replace(' *', '').replace('†', '')
        
        # Look for statistics in the row
        stats = []
        for stat_div in row.find_all('div', class_=lambda c: c and 'text-right' in c):
            stat_text = stat_div.get_text(strip=True)
            if stat_text and stat_text.replace('.', '').isdigit():
                stats.append(stat_text)
        
        # If we have at least 2 stats (runs and balls)
        if len(stats) >= 2:
            try:
                runs = int(stats[0]) if stats[0].isdigit() else 0
                balls = int(stats[1]) if len(stats) > 1 and stats[1].isdigit() else 0
                fours = int(stats[2]) if len(stats) > 2 and stats[2].isdigit() else 0
                sixes = int(stats[3]) if len(stats) > 3 and stats[3].isdigit() else 0
                
                # Calculate SR if not provided
                sr = (runs / balls * 100) if balls > 0 else 0.0
                
                if runs > 0 or balls > 0:
                    batting.append({
                        'name': name,
                        'runs': runs,
                        'balls': balls,
                        'fours': fours,
                        'sixes': sixes,
                        'sr': round(sr, 2)
                    })
            except (ValueError, IndexError):
                continue
    
    # Remove duplicates (same player might appear multiple times)
    unique_batting = []
    seen_names = set()
    for b in batting:
        if b['name'] not in seen_names:
            seen_names.add(b['name'])
            unique_batting.append(b)
    
    logger.debug(f"Extracted {len(unique_batting)} batsmen")
    return unique_batting

def extract_bowling_simple(soup):
    """Extract bowling list - SIMPLIFIED version."""
    bowling = []
    
    # Look for bowling tables - they often have "Bowler" header
    bowler_headers = soup.find_all(string=re.compile(r'Bowler', re.I))
    
    for header in bowler_headers:
        # Get the table container
        container = header.find_parent('div', class_=lambda c: c and 'cb-col' in c)
        if not container:
            continue
            
        # Find all rows with bowling data
        rows = container.find_all('div', class_=lambda c: c and 'cb-col' in c)
        
        for row in rows:
            # Look for player profile link
            link = row.find('a', href=lambda h: h and '/profiles/' in h)
            if not link:
                continue
                
            name = link.get_text(strip=True)
            
            # Look for statistics
            stats = []
            for stat_div in row.find_all('div', class_=lambda c: c and 'text-right' in c):
                stat_text = stat_div.get_text(strip=True)
                if stat_text and (stat_text.isdigit() or stat_text.replace('.', '').isdigit()):
                    stats.append(stat_text)
            
            # Bowling stats: overs, maidens, runs, wickets, econ
            if len(stats) >= 5:
                try:
                    overs = float(stats[0]) if stats[0].replace('.', '').isdigit() else 0.0
                    maidens = int(stats[1]) if stats[1].isdigit() else 0
                    runs = int(stats[2]) if stats[2].isdigit() else 0
                    wickets = int(stats[3]) if stats[3].isdigit() else 0
                    econ = float(stats[4]) if stats[4].replace('.', '').isdigit() else 0.0
                    
                    if overs > 0 or wickets > 0 or runs > 0:
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
    
    # Remove duplicates
    unique_bowling = []
    seen_names = set()
    for b in bowling:
        if b['name'] not in seen_names:
            seen_names.add(b['name'])
            unique_bowling.append(b)
    
    logger.debug(f"Extracted {len(unique_bowling)} bowlers")
    return unique_bowling

def extract_start_time_from_match_page(soup):
    """Extract start time from the match facts section."""
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
    """Extract the true match status from a match page."""
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

    # 1️⃣ Live badge
    live_badge = soup.find('span', class_=lambda c: c and 'cb-plus-live-tag' in c)
    if live_badge:
        return "Live"

    # 2️⃣ Look for status in the top bar
    top_bar = soup.find('div', class_=lambda c: c and 'cb-nav-bar' in c)
    if top_bar:
        for a in top_bar.find_all('a'):
            text = a.get_text(strip=True)
            if is_valid_status(text):
                return text

    # 3️⃣ Look for result text
    result_elem = soup.find('div', string=re.compile(r'won by \d+ (run|wicket)', re.I))
    if result_elem:
        candidate = result_elem.get_text(strip=True)
        if is_valid_status(candidate):
            return candidate

    # 4️⃣ Toss text
    toss_elem = soup.find('div', string=re.compile(r'opt to (bat|field)', re.I))
    if toss_elem:
        candidate = toss_elem.get_text(strip=True)
        if is_valid_status(candidate):
            return candidate

    # 5️⃣ Innings break / stumps / rain
    status_keywords = ['innings break', 'stumps', 'rain', 'abandoned', 'lunch', 'tea']
    for kw in status_keywords:
        elem = soup.find('div', string=re.compile(kw, re.I))
        if elem:
            candidate = elem.get_text(strip=True)
            if is_valid_status(candidate):
                return candidate

    # 6️⃣ Preview
    preview_div = soup.find('div', class_=lambda c: c and 'cb-text-preview' in c)
    if preview_div:
        return "Preview"

    return None