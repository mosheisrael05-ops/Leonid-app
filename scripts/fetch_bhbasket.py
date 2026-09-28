#!/usr/bin/env python3
"""Fetch basketball games from bhbasket.co.il"""

import json
import sys
import re
from datetime import datetime
from pathlib import Path

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print('Error: requests and beautifulsoup4 are required', file=sys.stderr)
    sys.exit(0)

# Output file path
OUTPUT_FILE = Path(__file__).parent.parent / 'data' / 'bhbasket-games.json'

def fetch_games():
    """Fetch games from bhbasket.co.il"""
    try:
        # Use a normal browser User-Agent header
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        
        url = 'https://bhbasket.co.il/games.asp'
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        games = []
        
        # Find all game links (game-zone.asp?GameId=...)
        game_links = soup.find_all('a', href=lambda x: x and 'game-zone.asp' in x and 'GameId=' in x)
        
        for link in game_links:
            try:
                # Extract GameId from href
                href = link.get('href', '')
                if 'GameId=' not in href:
                    continue
                
                game_id = href.split('GameId=')[-1].split('&')[0]
                if not game_id:
                    continue
                
                # Navigate up to find the game row/container
                row = link
                for _ in range(5):  # Go up max 5 levels
                    row = row.parent
                    if row and row.name in ['tr', 'div']:
                        break
                
                if not row:
                    continue
                
                # Initialize game info
                game_info = {
                    'GameId': game_id,
                    'date_text': '',
                    'time': '',
                    'competition': '',
                    'home_label': '',
                    'home_team': '',
                    'away_team': '',
                    'score': '',
                    'broadcast': ''
                }
                
                # Extract teams from link text
                link_text = link.get_text(strip=True)
                
                # Try multiple parsing strategies
                teams_found = False
                
                # Strategy 1: "Team1 vs Team2" or similar
                if ' vs ' in link_text.lower():
                    parts = re.split(r'\s+vs\s+', link_text, flags=re.IGNORECASE)
                    if len(parts) >= 2:
                        game_info['home_team'] = parts[0].strip()
                        game_info['away_team'] = parts[1].strip()
                        teams_found = True
                
                # Strategy 2: "Team1-Team2" format
                if not teams_found and '-' in link_text:
                    parts = link_text.split('-')
                    if len(parts) >= 2:
                        # Filter out parts that are just numbers (likely score)
                        filtered = [p.strip() for p in parts if p.strip() and not re.match(r'^\d+$', p.strip())]
                        if len(filtered) >= 2:
                            game_info['home_team'] = filtered[0]
                            game_info['away_team'] = filtered[-1]
                            teams_found = True
                
                # Extract score if present
                score_match = re.search(r'(\d+)\s*[-:]?\s*(\d+)', link_text)
                if score_match:
                    game_info['score'] = f"{score_match.group(1)}:{score_match.group(2)}"
                
                # Extract date/time from surrounding elements
                if row.name == 'tr':
                    cells = row.find_all(['td', 'th'])
                    if len(cells) >= 1:
                        game_info['date_text'] = cells[0].get_text(strip=True)
                    if len(cells) >= 2:
                        game_info['time'] = cells[1].get_text(strip=True)
                    if len(cells) >= 3:
                        game_info['competition'] = cells[2].get_text(strip=True)
                else:
                    # For div-based layouts, look for siblings or nearby elements
                    prev_td = link.find_previous(['td', 'div'])
                    if prev_td:
                        game_info['date_text'] = prev_td.get_text(strip=True)
                    
                    next_td = link.find_next(['td', 'div'])
                    if next_td and next_td != link:
                        game_info['time'] = next_td.get_text(strip=True)
                
                # Look for broadcast/live info
                row_text = row.get_text(separator=' ', strip=True).lower()
                broadcast_keywords = ['live', 'שידור', 'אולם', 'hall', 'youtube']
                for keyword in broadcast_keywords:
                    if keyword in row_text:
                        game_info['broadcast'] = keyword
                        break
                
                # Only add if we have at least GameId and some team info
                if game_info['GameId'] and (game_info['home_team'] or game_info['away_team']):
                    games.append(game_info)
            
            except Exception as e:
                print(f'Warning: Failed to parse game: {e}', file=sys.stderr)
                continue
        
        return games if len(games) > 0 else None
    
    except Exception as e:
        print(f'Error fetching games: {e}', file=sys.stderr)
        return None

def main():
    """Main entry point"""
    games = fetch_games()
    
    # Exit with code 0 if request failed or zero games parsed (without modifying file)
    if games is None or len(games) == 0:
        print('No games fetched or parsing failed, not updating file')
        sys.exit(0)
    
    # Create output directory if it doesn't exist
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    # Prepare data
    data = {
        'updated': datetime.utcnow().isoformat() + 'Z',
        'games': games
    }
    
    # Write to file
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f'Successfully fetched {len(games)} games and wrote to {OUTPUT_FILE}')
    sys.exit(0)

if __name__ == '__main__':
    main()
