import re
import random
import requests
import logging
import json
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
        return None, f"http_{e.response.status_code}"
    except Exception as e:
        logger.error(f"Unexpected error fetching {url}: {e}")
        return None, "unknown"

# ----------------------------------------------------------------------
# Match list extraction from CORRECT source
# ----------------------------------------------------------------------
def extract_live_matches(soup):
    """Extract live matches from Cricbuzz live scores page."""
    matches = []
    
    # Find all match blocks
    match_blocks = soup.find_all('div', class_='cb-lv-main')
    
    for block in match_blocks:
        # Extract match link to get ID
        link = block.find('a', href=True)
        if not link:
            continue
            
        href = link['href']
        # Extract ID from scorecard link (not commentary)
        match = re.search(r'/live-cricket-scorecard/(\d+)', href)
        if not match:
            # Try alternate pattern
            match = re.search(r'/(\d+)/', href)
        if not match:
            continue
            
        match_id = int(match.group(1))
        
        # Extract title from header
        title_elem = block.find('h3', class_='cb-lv-scr-mtch-hdr')
        title = title_elem.get_text(strip=True) if title_elem else ''
        
        # Extract teams from title
        teams = []
        if ' vs ' in title:
            parts = title.split(' vs ')
            teams = [parts[0].strip(), parts[1].split(',')[0].strip()]
        
        # Determine status
        status = "Upcoming"
        status_elem = block.find('div', class_='cb-text-live')
        if status_elem:
            status = "Live"
        else:
            complete_elem = block.find('div', class_='cb-text-complete')
            if complete_elem:
                status = "Completed"
        
        # Extract start time/venue
        start_time = None
        time_elem = block.find('div', class_='cb-font-12')
        if time_elem:
            time_text = time_elem.get_text(strip=True)
            # Extract time portion
            time_match = re.search(r'\d{1,2}:\d{2}\s*(AM|PM)', time_text, re.I)
            if time_match:
                start_time = time_match.group(0)
            else:
                start_time = time_text
        
        matches.append({
            'id': match_id,
            'teams': teams,
            'title': title,
            'status': status,
            'start_time': start_time
        })
    
    # Remove duplicates
    unique = {}
    for m in matches:
        if m['id'] not in unique:
            unique[m['id']] = m
    
    logger.info(f"Extracted {len(unique)} unique matches")
    return list(unique.values())

# ----------------------------------------------------------------------
# Scorecard data extraction from CORRECT source
# ----------------------------------------------------------------------
def extract_match_data(soup):
    """Extract detailed match data from scorecard page."""
    
    # Extract title from header
    title_elem = soup.find('h1', class_='cb-nav-hdr')
    title = title_elem.get_text(strip=True) if title_elem else None
    
    # Extract teams from title
    teams = []
    if title and ' vs ' in title:
        parts = title.split(' vs ')
        teams = [parts[0].strip(), parts[1].split(',')[0].strip()]
    
    # Extract status
    status = extract_status(soup)
    
    # Extract current score
    current_score = extract_current_score(soup)
    
    # Extract run rate
    run_rate = extract_run_rate(soup)
    
    # Extract batting
    batting = extract_batting(soup)
    
    # Extract bowling
    bowling = extract_bowling(soup)
    
    # Extract start time
    start_time = extract_start_time(soup)
    
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

def extract_status(soup):
    """Extract match status from scorecard."""
    # Check for complete status
    complete_div = soup.find('div', class_='cb-text-complete')
    if complete_div:
        return complete_div.get_text(strip=True)
    
    # Check for live status
    live_div = soup.find('div', class_='cb-text-live')
    if live_div:
        return live_div.get_text(strip=True)
    
    # Check for preview
    preview_div = soup.find('div', class_='cb-text-preview')
    if preview_div:
        return preview_div.get_text(strip=True)
    
    return "Match Stats will Update Soon..."

def extract_current_score(soup):
    """Extract current score from innings header."""
    # Find innings header row
    header = soup.find('div', class_='cb-scrd-hdr-rw')
    if not header:
        return None
    
    # Extract score text (e.g., "SL 145-3 (17.2)")
    score_text = header.get_text(strip=True)
    
    # Parse using regex
    match = re.search(r'([A-Z]+)\s+(\d+)-(\d+)\s*\((\d+\.?\d*)\)', score_text)
    if match:
        return {
            'team': match.group(1),
            'runs': int(match.group(2)),
            'wickets': int(match.group(3)),
            'overs': float(match.group(4))
        }
    
    return None

def extract_run_rate(soup):
    """Extract run rate from scorecard."""
    # Look for RR text
    rr_text = soup.find(string=re.compile(r'RR:\s*(\d+\.?\d*)'))
    if rr_text:
        match = re.search(r'RR:\s*(\d+\.?\d*)', rr_text)
        if match:
            return float(match.group(1))
    return None

def extract_batting(soup):
    """Extract batting stats from scorecard."""
    batting = []
    
    # Find all batting rows
    batting_rows = soup.find_all('div', class_='cb-scrd-itms')
    
    for row in batting_rows:
        # Skip if this is a bowler row (has bowler stats)
        if row.find(string=re.compile(r'Overs|Maidens|Runs|Wkts|Econ')):
            continue
            
        # Get all cells
        cells = row.find_all('div', class_=lambda c: c and 'cb-col' in c)
        if len(cells) < 6:
            continue
        
        # Extract name (first cell)
        name_link = cells[0].find('a')
        name = name_link.get_text(strip=True) if name_link else cells[0].get_text(strip=True)
        name = name.replace(' *', '').replace('†', '').strip()
        
        # Extract stats
        try:
            runs = int(cells[1].get_text(strip=True)) if cells[1].get_text(strip=True).isdigit() else 0
            balls = int(cells[2].get_text(strip=True)) if cells[2].get_text(strip=True).isdigit() else 0
            fours = int(cells[3].get_text(strip=True)) if cells[3].get_text(strip=True).isdigit() else 0
            sixes = int(cells[4].get_text(strip=True)) if cells[4].get_text(strip=True).isdigit() else 0
            sr_text = cells[5].get_text(strip=True)
            sr = float(sr_text) if sr_text.replace('.', '').isdigit() else 0.0
            
            if runs > 0 or balls > 0:
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
    
    # Remove duplicates and return first 11
    unique = []
    seen = set()
    for b in batting:
        if b['name'] not in seen:
            seen.add(b['name'])
            unique.append(b)
    
    return unique

def extract_bowling(soup):
    """Extract bowling stats from scorecard."""
    bowling = []
    
    # Find bowling section (usually after batting)
    # Look for rows that contain bowling stats
    all_rows = soup.find_all('div', class_='cb-scrd-itms')
    
    for row in all_rows:
        # Check if this is a bowling row (contains overs)
        cells = row.find_all('div', class_=lambda c: c and 'cb-col' in c)
        if len(cells) < 6:
            continue
        
        # Check if first cell has a bowler name
        name_link = cells[0].find('a', href=lambda h: h and '/profiles/' in h)
        if not name_link:
            continue
            
        name = name_link.get_text(strip=True)
        
        # Verify this is a bowling row by checking stats format
        try:
            overs_text = cells[1].get_text(strip=True)
            if not overs_text.replace('.', '').isdigit():
                continue
                
            overs = float(overs_text)
            maidens = int(cells[2].get_text(strip=True)) if cells[2].get_text(strip=True).isdigit() else 0
            runs = int(cells[3].get_text(strip=True)) if cells[3].get_text(strip=True).isdigit() else 0
            wickets = int(cells[4].get_text(strip=True)) if cells[4].get_text(strip=True).isdigit() else 0
            econ_text = cells[5].get_text(strip=True)
            econ = float(econ_text) if econ_text.replace('.', '').isdigit() else 0.0
            
            if overs > 0 or wickets > 0:
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

def extract_start_time(soup):
    """Extract start time from match info section."""
    # Look for time in info section
    info_items = soup.find_all('div', class_='cb-col')
    
    for item in info_items:
        text = item.get_text()
        if 'Time' in text or 'LOCAL' in text:
            # Extract time pattern
            match = re.search(r'(\d{1,2}:\d{2}\s*(?:AM|PM).*?LOCAL)', text, re.I)
            if match:
                return match.group(1)
    
    return None

# ----------------------------------------------------------------------
# Start time extraction (for live matches enrichment)
# ----------------------------------------------------------------------
def extract_start_time_from_match_page(soup):
    """Alias for extract_start_time to maintain compatibility."""
    return extract_start_time(soup)