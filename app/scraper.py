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
        return None, f"http_{e.response.status_code}"
    except Exception as e:
        logger.error(f"Unexpected error fetching {url}: {e}")
        return None, "unknown"

# ----------------------------------------------------------------------
# Live matches extraction (WORKING VERSION)
# ----------------------------------------------------------------------
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
        
        # Get title
        title_attr = a.get('title', '')
        if title_attr:
            title = title_attr
        else:
            title = a.get_text(strip=True)
        if not title:
            continue
        
        # Clean title - remove extra whitespace
        title = re.sub(r'\s+', ' ', title).strip()
        
        # Determine status
        lower_title = title.lower()
        if 'live' in lower_title:
            status = "Live"
        elif any(word in lower_title for word in ['won', 'complete', 'stumps', 'drawn', 'rain']):
            status = "Completed"
        else:
            status = "Upcoming"
        
        # Extract teams - IMPROVED PARSING
        teams = []
        
        # Method 1: Look for "Team vs Team" pattern
        vs_match = re.search(r'([A-Za-z\s]+?)\s+vs\s+([A-Za-z\s]+)', title, re.I)
        if vs_match:
            teams = [vs_match.group(1).strip(), vs_match.group(2).strip()]
        else:
            # Method 2: Look for country names in the title
            # Common cricket playing nations
            countries = [
                'Afghanistan', 'Australia', 'Bangladesh', 'England', 'India',
                'Ireland', 'New Zealand', 'Pakistan', 'South Africa', 'Sri Lanka',
                'West Indies', 'Zimbabwe', 'Afg', 'Aus', 'Ban', 'Eng', 'Ind',
                'Ire', 'NZ', 'Pak', 'SA', 'SL', 'WI', 'Zim'
            ]
            found = []
            for country in countries:
                if country.lower() in title.lower():
                    found.append(country)
            if len(found) >= 2:
                teams = found[:2]
        
        # Try to get start time from nearby elements
        start_time = None
        parent = a.find_parent()
        if parent:
            # Look for time pattern in parent
            time_pattern = re.compile(r'\d{1,2}:\d{2}\s*(?:AM|PM)|Today|Tomorrow', re.I)
            time_elem = parent.find(string=time_pattern)
            if time_elem:
                start_time = time_elem.strip()
        
        matches.append({
            'id': match_id,
            'teams': teams,
            'title': title,
            'status': status,
            'start_time': start_time  # May be None initially
        })
    
    # Remove duplicates
    unique = {m['id']: m for m in matches}
    result = list(unique.values())
    logger.info(f"Extracted {len(result)} unique matches")
    return result

# ----------------------------------------------------------------------
# Start time extraction from match page (for enrichment)
# ----------------------------------------------------------------------
def extract_start_time_from_match_page(soup):
    """Extract start time from the match scorecard page."""
    start_time = None
    
    # Method 1: Look for Date & Time in the info section
    info_items = soup.find_all('div', class_='cb-col')
    for item in info_items:
        text = item.get_text()
        if 'Date & Time' in text or 'Start Time' in text:
            # Extract the time part
            time_match = re.search(r'(\d{1,2}:\d{2}\s*(?:AM|PM).*?LOCAL)', text, re.I)
            if time_match:
                return time_match.group(1)
    
    # Method 2: Look for time in any element
    time_pattern = re.compile(r'\d{1,2}:\d{2}\s*(?:AM|PM).*?LOCAL', re.I)
    time_elem = soup.find(string=time_pattern)
    if time_elem:
        return time_elem.strip()
    
    # Method 3: Look for time in meta tags or structured data
    meta_time = soup.find('meta', {'property': 'og:updated_time'}) or soup.find('meta', {'name': 'published_time'})
    if meta_time and meta_time.get('content'):
        return meta_time['content']
    
    return start_time

# ----------------------------------------------------------------------
# Scorecard data extraction (unchanged, working)
# ----------------------------------------------------------------------
def extract_match_data(soup):
    """Extract detailed match data from scorecard page."""
    title_elem = soup.find('h1', class_='cb-nav-hdr')
    title = title_elem.get_text(strip=True) if title_elem else None
    
    teams = []
    if title and ' vs ' in title:
        parts = title.split(' vs ')
        teams = [parts[0].strip(), parts[1].split(',')[0].strip()]
    
    status = extract_status(soup)
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

def extract_status(soup):
    """Extract match status from scorecard."""
    complete_div = soup.find('div', class_='cb-text-complete')
    if complete_div:
        return complete_div.get_text(strip=True)
    
    live_div = soup.find('div', class_='cb-text-live')
    if live_div:
        return live_div.get_text(strip=True)
    
    preview_div = soup.find('div', class_='cb-text-preview')
    if preview_div:
        return preview_div.get_text(strip=True)
    
    return "Match Stats will Update Soon..."

def extract_current_score(soup):
    """Extract current score from innings header."""
    header = soup.find('div', class_='cb-scrd-hdr-rw')
    if not header:
        return None
    
    score_text = header.get_text(strip=True)
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
    rr_text = soup.find(string=re.compile(r'RR:\s*(\d+\.?\d*)'))
    if rr_text:
        match = re.search(r'RR:\s*(\d+\.?\d*)', rr_text)
        if match:
            return float(match.group(1))
    return None

def extract_batting(soup):
    """Extract batting stats from scorecard."""
    batting = []
    batting_rows = soup.find_all('div', class_='cb-scrd-itms')
    
    for row in batting_rows:
        if row.find(string=re.compile(r'Overs|Maidens|Runs|Wkts|Econ')):
            continue
            
        cells = row.find_all('div', class_=lambda c: c and 'cb-col' in c)
        if len(cells) < 6:
            continue
        
        name_link = cells[0].find('a')
        name = name_link.get_text(strip=True) if name_link else cells[0].get_text(strip=True)
        name = name.replace(' *', '').replace('†', '').strip()
        
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
    
    # Remove duplicates
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
    all_rows = soup.find_all('div', class_='cb-scrd-itms')
    
    for row in all_rows:
        cells = row.find_all('div', class_=lambda c: c and 'cb-col' in c)
        if len(cells) < 6:
            continue
        
        name_link = cells[0].find('a', href=lambda h: h and '/profiles/' in h)
        if not name_link:
            continue
            
        name = name_link.get_text(strip=True)
        
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