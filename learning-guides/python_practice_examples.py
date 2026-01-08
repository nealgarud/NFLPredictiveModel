"""
Python Skills Practice Examples
Run these to see the patterns in action
"""

# ============================================================================
# 1. LIST/DICT COMPREHENSIONS
# ============================================================================

# Example data
games = [
    {'team': 'KC', 'wins': 12, 'losses': 5},
    {'team': 'BUF', 'wins': 11, 'losses': 6},
    {'team': 'GB', 'wins': 9, 'losses': 8},
    {'team': 'PIT', 'wins': 7, 'losses': 10},
]

# OLD WAY (verbose)
strong_teams_old = []
for game in games:
    if game['wins'] > 10:
        strong_teams_old.append(game['team'])

# NEW WAY (comprehension)
strong_teams_new = [game['team'] for game in games if game['wins'] > 10]
print("Strong teams:", strong_teams_new)

# Dict comprehension
team_wins = {game['team']: game['wins'] for game in games}
print("Team wins:", team_wins)

# Nested comprehension
all_teams = [f"{game['team']}: {game['wins']} wins" for game in games if game['wins'] > 8]
print("Teams with 8+ wins:", all_teams)

# ============================================================================
# 2. F-STRINGS
# ============================================================================

team = 'KC'
wins = 12
games = 17
win_rate = wins / games

# OLD WAY
message_old = "Team: " + team + " has " + str(wins) + " wins"
message_old2 = "Team: {} has {} wins".format(team, wins)

# NEW WAY (f-strings)
message_new = f"Team: {team} has {wins} wins"
message_formatted = f"Team: {team} has {wins} wins (rate: {win_rate:.2%})"
print(message_formatted)

# ============================================================================
# 3. SAFE DICT ACCESS (.get())
# ============================================================================

# Example API response
api_response = {
    'status': 'success',
    'data': {
        'team': 'KC',
        'wins': 12
    }
}

# UNSAFE (KeyError if missing)
# team = api_response['data']['team']  # Could crash!

# SAFE (returns None or default)
team = api_response.get('data', {}).get('team', 'Unknown')
print(f"Team from API: {team}")

# With default value
timeout = api_response.get('timeout', 30)  # Use 30 if not present
print(f"Timeout: {timeout}")

# ============================================================================
# 4. CONTEXT MANAGERS (with statements)
# ============================================================================

# File handling
try:
    with open('test_file.txt', 'w') as f:
        f.write("Hello, World!")
    # File automatically closed here, even if error occurs
except FileNotFoundError:
    print("File not found")

# Database example (conceptual)
# with conn.cursor() as cursor:
#     cursor.execute("SELECT * FROM games")
#     results = cursor.fetchall()
# # Cursor automatically closed

# ============================================================================
# 5. ENUMS
# ============================================================================

from enum import Enum

class GameType(str, Enum):
    REGULAR = 'REG'
    POSTSEASON = 'POST'
    PRESEASON = 'PRE'

# Usage
game_type = 'REG'
if game_type == GameType.REGULAR:
    print("Regular season game")

# Type-safe
def process_game(game_type: GameType):
    print(f"Processing {game_type.value}")

process_game(GameType.REGULAR)

# ============================================================================
# 6. DATACLASSES
# ============================================================================

from dataclasses import dataclass
from typing import Optional

@dataclass
class TeamStats:
    team: str
    wins: int
    losses: int
    
    @property
    def win_rate(self) -> float:
        total = self.wins + self.losses
        return self.wins / total if total > 0 else 0.0
    
    def is_strong(self) -> bool:
        return self.win_rate > 0.6

# Usage
stats = TeamStats(team='KC', wins=12, losses=5)
print(f"{stats.team}: {stats.win_rate:.2%}")
print(f"Is strong: {stats.is_strong()}")

# ============================================================================
# 7. ERROR HANDLING PATTERNS
# ============================================================================

# Custom exceptions
class PredictionError(Exception):
    """Base exception for predictions"""
    pass

class InvalidTeamError(PredictionError):
    """Team is invalid"""
    pass

class DatabaseError(PredictionError):
    """Database operation failed"""
    pass

# Usage
def validate_team(team: str):
    valid_teams = ['KC', 'BUF', 'GB', 'PIT']
    if team not in valid_teams:
        raise InvalidTeamError(f"Invalid team: {team}")
    return team

# Try/except with specific errors
try:
    team = validate_team('KC')
    print(f"Valid team: {team}")
except InvalidTeamError as e:
    print(f"Invalid team error: {e}")
except PredictionError as e:
    print(f"Prediction error: {e}")
except Exception as e:
    print(f"Unexpected error: {e}")

# ============================================================================
# 8. COLLECTIONS UTILITIES
# ============================================================================

from collections import defaultdict, Counter

# defaultdict - no KeyError
team_wins = defaultdict(int)
team_wins['KC'] += 1
team_wins['BUF'] += 1
team_wins['KC'] += 1
print("Team wins (defaultdict):", dict(team_wins))

# Counter - count occurrences
teams = ['KC', 'BUF', 'KC', 'GB', 'KC', 'BUF']
team_counts = Counter(teams)
print("Team counts:", team_counts)
print("Most common:", team_counts.most_common(2))

# ============================================================================
# 9. TYPE HINTS - ADVANCED
# ============================================================================

from typing import Union, Optional, Literal, Dict, List

# Union types
def process_value(value: Union[int, str]) -> str:
    return str(value)

# Literal (specific values)
def set_status(status: Literal['active', 'inactive']) -> None:
    print(f"Status: {status}")

set_status('active')  # Type-checked!

# Optional (Union with None)
def get_team_stats(team: str) -> Optional[Dict]:
    if team == 'KC':
        return {'wins': 12, 'losses': 5}
    return None

# ============================================================================
# 10. PRACTICAL EXAMPLE: API Handler Pattern
# ============================================================================

from typing import Dict, Any

def handle_request(body: Dict[str, Any]) -> Dict:
    """Example of good error handling pattern"""
    try:
        # Safe access with defaults
        team_a = body.get('team_a', '').upper()
        team_b = body.get('team_b', '').upper()
        spread = float(body.get('spread', 0))
        
        # Validation
        if not team_a or not team_b:
            return {
                'statusCode': 400,
                'body': {'error': 'team_a and team_b required'}
            }
        
        if abs(spread) > 20:
            return {
                'statusCode': 400,
                'body': {'error': 'Spread too large'}
            }
        
        # Process (simulated)
        result = {
            'team_a': team_a,
            'team_b': team_b,
            'spread': spread,
            'prediction': 0.65
        }
        
        return {
            'statusCode': 200,
            'body': {'success': True, 'data': result}
        }
        
    except ValueError as e:
        return {
            'statusCode': 400,
            'body': {'error': f'Invalid value: {e}'}
        }
    except Exception as e:
        return {
            'statusCode': 500,
            'body': {'error': 'Internal server error'}
        }

# Test
test_body = {
    'team_a': 'KC',
    'team_b': 'BUF',
    'spread': -3.5
}
response = handle_request(test_body)
print("\nAPI Response:", response)

# ============================================================================
# RUN ALL EXAMPLES
# ============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Python Skills Practice Examples")
    print("=" * 60)
    print("\n1. List/Dict Comprehensions:")
    # Already printed above
    
    print("\n2. F-Strings:")
    # Already printed above
    
    print("\n3. Safe Dict Access:")
    # Already printed above
    
    print("\n4. Context Managers:")
    print("(See code comments)")
    
    print("\n5. Enums:")
    # Already printed above
    
    print("\n6. Dataclasses:")
    # Already printed above
    
    print("\n7. Error Handling:")
    # Already printed above
    
    print("\n8. Collections:")
    # Already printed above
    
    print("\n9. Type Hints:")
    print("(See function signatures)")
    
    print("\n10. API Handler Pattern:")
    # Already printed above
    
    print("\n" + "=" * 60)
    print("Practice complete! Modify these examples to learn more.")
    print("=" * 60)

