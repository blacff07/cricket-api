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
        
        # Determine status
        status = "Live" if "live" in title.lower() else "Upcoming"
        
        # Parse teams
        teams = []
        if ' vs ' in title:
            teams_part = title.split(' vs ')[0]
            teams = [teams_part.split(',')[0].strip()]
            second_part = title.split(' vs ')[1]
            teams.append(second_part.split(',')[0].strip())
        
        # Parse series
        series = "Unknown Series"
        if ',' in title:
            parts = title.split(',')
            if len(parts) > 1:
                series = parts[1].strip()
        
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

    # Status (update)
    status = 'Match Stats will Update Soon...'
    match_bar = soup.find('div', class_=lambda c: c and 'bg-[#4a4a4a]' in c)
    if match_bar:
        links = match_bar.find_all('a', title=True)
        for link in links:
            if ' vs ' in link.get('title', ''):
                title_attr = link['title']
                parts = title_attr.split('-')
                if len(parts) > 1:
                    status = parts[-1].strip()
                    break
    if status == 'Match Stats will Update Soon...':
        status_div = soup.find('div', class_=lambda c: c and 'cb-text-' in c)
        if status_div:
            status = status_div.text.strip()

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
            current_score = {
                'team': team,
                'runs': int(runs_wickets.split('-')[0]) if '-' in runs_wickets else 0,
                'wickets': int(runs_wickets.split('-')[1]) if '-' in runs_wickets and len(runs_wickets.split('-')) > 1 else 0,
                'overs': float(overs) if overs else 0
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
                batsmen.append({
                    'name': name,
                    'runs': int(stat_divs[0].text.strip()) if stat_divs[0].text.strip().isdigit() else 0,
                    'balls': int(stat_divs[1].text.strip()) if stat_divs[1].text.strip().isdigit() else 0,
                    'fours': int(stat_divs[2].text.strip()) if stat_divs[2].text.strip().isdigit() else 0,
                    'sixes': int(stat_divs[3].text.strip()) if stat_divs[3].text.strip().isdigit() else 0,
                    'sr': float(stat_divs[4].text.strip()) if stat_divs[4].text.strip().replace('.', '').isdigit() else 0
                })
            except (ValueError, IndexError):
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
                    bowlers.append({
                        'name': name,
                        'overs': float(stat_divs[0].text.strip()) if stat_divs[0].text.strip().replace('.', '').isdigit() else 0,
                        'maidens': int(stat_divs[1].text.strip()) if stat_divs[1].text.strip().isdigit() else 0,
                        'runs': int(stat_divs[2].text.strip()) if stat_divs[2].text.strip().isdigit() else 0,
                        'wickets': int(stat_divs[3].text.strip()) if stat_divs[3].text.strip().isdigit() else 0,
                        'econ': float(stat_divs[4].text.strip()) if stat_divs[4].text.strip().replace('.', '').isdigit() else 0
                    })
                except (ValueError, IndexError):
                    continue

    return {
        'title': title,
        'series': series,
        'teams': teams,
        'status': status,
        'match_state': match_state,
        'current_score': current_score,
        'livescore': livescore,
        'run_rate': runrate,
        'batting': batsmen,
        'bowling': bowlers
    }