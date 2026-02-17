import re
import random
import requests
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
        return BeautifulSoup(resp.content, 'lxml')
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to fetch {url}: {e}")
        return None

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
        status = "Live" if "live" in title.lower() else "Upcoming"
        matches.append({
            'id': match_id,
            'title': title,
            'status': status,
            'link': href
        })
    # Remove duplicates by ID
    unique = {}
    for m in matches:
        if m['id'] not in unique:
            unique[m['id']] = m
    return list(unique.values())

def extract_match_data(soup):
    """Extract detailed match data from a match page."""
    # Title
    title_tag = soup.find('h1')
    title = title_tag.text.strip().replace(', Commentary', '') if title_tag else None

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

    # Live score
    livescore = None
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

    # CRR
    crr_label = soup.find('span', string=re.compile(r'CRR', re.I))
    if crr_label:
        value_span = crr_label.find_next_sibling('span')
        if value_span:
            runrate = value_span.text.strip()
        else:
            parent = crr_label.parent
            values = parent.find_all('span')
            if len(values) > 1:
                runrate = values[-1].text.strip()
    if not runrate:
        crr_div = soup.find('div', string=re.compile(r'CRR', re.I))
        if crr_div:
            runrate = crr_div.get_text(strip=True).replace('CRR', '').strip()
    if runrate:
        runrate = f"CRR: {runrate}"

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
            batsmen.append({
                'name': name,
                'runs': stat_divs[0].text.strip(),
                'balls': stat_divs[1].text.strip(),
                'sr': stat_divs[4].text.strip()
            })

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
                bowlers.append({
                    'name': name,
                    'overs': stat_divs[0].text.strip(),
                    'runs': stat_divs[2].text.strip(),
                    'wickets': stat_divs[3].text.strip(),
                    'econ': stat_divs[4].text.strip()
                })

    return {
        'title': title,
        'status': status,
        'livescore': livescore,
        'runrate': runrate,
        'batsmen': batsmen,
        'bowlers': bowlers
    }