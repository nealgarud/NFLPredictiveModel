# Python Skills Guide for Your NFL Project

## What You Already Know ✅
- Basic Python syntax
- Classes and OOP
- Type hints (`Dict`, `Optional`, `List`)
- Error handling (`try/except`)
- Lambda deployment
- S3 integration (`boto3`)
- API Gateway responses
- Logging
- Environment variables (`os.environ`)

---

## Critical Skills You Need (Priority Order)

### 1. **List/Dict Comprehensions** ⚠️ HIGH PRIORITY
**Why:** Cleaner, faster code. You're probably doing this manually.

**Current way (verbose):**
```python
results = []
for game in games:
    if game['wins'] > 10:
        results.append(game['team'])
```

**Better way (comprehension):**
```python
# List comprehension
strong_teams = [game['team'] for game in games if game['wins'] > 10]

# Dict comprehension
team_wins = {game['team']: game['wins'] for game in games if game['wins'] > 10}

# Nested comprehension
all_teams = [team for season in seasons for team in season['teams']]
```

**When to use:**
- Filtering lists
- Creating dictionaries from data
- Transforming data structures

**Your project example:**
```python
# Instead of:
team_stats = {}
for row in data:
    team_stats[row[0]] = row[1]

# Use:
team_stats = {row[0]: row[1] for row in data}
```

---

### 2. **Context Managers (`with` statements)** ⚠️ HIGH PRIORITY
**Why:** Proper resource cleanup (files, connections). Prevents leaks.

**Current way (risky):**
```python
file = open('data.txt', 'r')
content = file.read()
file.close()  # What if error happens before this?
```

**Better way (context manager):**
```python
# Files
with open('data.txt', 'r') as file:
    content = file.read()
# File automatically closed, even if error occurs

# Database connections (if using psycopg2)
with conn.cursor() as cursor:
    cursor.execute("SELECT * FROM games")
    results = cursor.fetchall()
# Cursor automatically closed

# Custom context manager
from contextlib import contextmanager

@contextmanager
def database_transaction(conn):
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise

# Usage
with database_transaction(conn):
    conn.run("INSERT INTO games ...")
```

**Your project:** You're using singleton for DB connection, but consider context managers for transactions.

---

### 3. **Default Values & `.get()` for Dictionaries** ⚠️ MEDIUM PRIORITY
**Why:** Prevents KeyError exceptions. You're already using this in lambda_handler!

**You're doing this correctly:**
```python
team_a = body.get('team_a', '').upper()  # ✅ Good!
spread = float(body.get('spread', 0))    # ✅ Good!
```

**But also use:**
```python
# Default dict values
config = {
    'timeout': 30,
    'retries': 3
}
timeout = config.get('timeout', 60)  # Use 60 if not in config

# Nested dict access (safe)
team_name = response.get('data', {}).get('team', {}).get('name', 'Unknown')

# Or use defaultdict
from collections import defaultdict
team_stats = defaultdict(int)  # Default value is 0
team_stats['KC'] += 1  # No KeyError if doesn't exist
```

---

### 4. **F-Strings (Formatted Strings)** ⚠️ MEDIUM PRIORITY
**Why:** Cleaner string formatting. You might be using `.format()` or `%`.

**Old way:**
```python
message = "Team: " + team + " has " + str(wins) + " wins"
message = "Team: {} has {} wins".format(team, wins)
```

**Better way (f-strings):**
```python
message = f"Team: {team} has {wins} wins"
message = f"Team: {team} has {wins} wins (rate: {wins/games:.2%})"  # Formatting
```

**Your project:**
```python
logger.info(f"Processing {team} for season {season}")
return response(200, {"message": f"Prediction for {team_a} vs {team_b}"})
```

---

### 5. **Enums for Constants** ⚠️ MEDIUM PRIORITY
**Why:** Type-safe constants. Better than magic strings.

**Current way:**
```python
if game_type == 'REG':
    # ...
elif game_type == 'POST':
    # ...
```

**Better way (Enum):**
```python
from enum import Enum

class GameType(Enum):
    REGULAR = 'REG'
    POSTSEASON = 'POST'
    PRESEASON = 'PRE'

# Usage
if game_type == GameType.REGULAR.value:
    # ...

# Or even better:
class GameType(str, Enum):  # Inherits from str
    REGULAR = 'REG'
    POSTSEASON = 'POST'
    PRESEASON = 'PRE'

if game_type == GameType.REGULAR:  # Direct comparison
    # ...
```

**Your project:**
```python
class Team(str, Enum):
    KC = 'KC'
    BUF = 'BUF'
    GB = 'GB'
    # ... all teams

# Type-safe team validation
def validate_team(team: str) -> bool:
    return team in [t.value for t in Team]
```

---

### 6. **Dataclasses** ⚠️ MEDIUM PRIORITY
**Why:** Cleaner data structures. Less boilerplate than classes.

**Current way:**
```python
class Prediction:
    def __init__(self, team: str, probability: float, confidence: float):
        self.team = team
        self.probability = probability
        self.confidence = confidence
    
    def __repr__(self):
        return f"Prediction(team={self.team}, prob={self.probability})"
```

**Better way (dataclass):**
```python
from dataclasses import dataclass

@dataclass
class Prediction:
    team: str
    probability: float
    confidence: float
    
    def is_confident(self) -> bool:
        return self.confidence > 0.7

# Usage
pred = Prediction(team='KC', probability=0.65, confidence=0.8)
print(pred)  # Auto-generated __repr__
```

**Your project:**
```python
@dataclass
class GamePrediction:
    team_a: str
    team_b: str
    spread: float
    favored_prob: float
    underdog_prob: float
    
    def to_dict(self) -> Dict:
        return {
            'team_a': self.team_a,
            'team_b': self.team_b,
            'spread': self.spread,
            'favored_prob': self.favored_prob,
            'underdog_prob': self.underdog_prob
        }
```

---

### 7. **Type Hints - Advanced** ⚠️ LOW PRIORITY
**Why:** Better IDE support, catch errors early.

**You know:**
```python
def predict(team: str, spread: float) -> Dict:
    ...
```

**Learn:**
```python
from typing import Union, Literal, TypedDict, Optional

# Union types
def process(value: Union[int, str]) -> str:
    return str(value)

# Literal (specific values)
def set_status(status: Literal['active', 'inactive', 'pending']) -> None:
    ...

# TypedDict (structured dict)
class PredictionResponse(TypedDict):
    success: bool
    data: Optional[Dict[str, float]]
    error: Optional[str]

def create_response() -> PredictionResponse:
    return {
        'success': True,
        'data': {'prob': 0.65},
        'error': None
    }
```

---

### 8. **Error Handling Patterns** ⚠️ MEDIUM PRIORITY
**Why:** Better error messages, graceful degradation.

**You know basic try/except. Learn:**

```python
# Specific exceptions
try:
    result = conn.run(query)
except (ConnectionError, TimeoutError) as e:
    logger.error(f"Connection issue: {e}")
    raise
except Exception as e:
    logger.error(f"Unexpected error: {e}")
    raise

# Custom exceptions
class PredictionError(Exception):
    """Base exception for prediction errors"""
    pass

class InvalidTeamError(PredictionError):
    """Team abbreviation is invalid"""
    pass

class DatabaseError(PredictionError):
    """Database operation failed"""
    pass

# Usage
def validate_team(team: str):
    if team not in VALID_TEAMS:
        raise InvalidTeamError(f"Invalid team: {team}")

# Error handling with context
try:
    prediction = predictor.predict(...)
except InvalidTeamError as e:
    return response(400, {"error": str(e)})
except DatabaseError as e:
    logger.error(f"DB error: {e}")
    return response(503, {"error": "Service temporarily unavailable"})
except Exception as e:
    logger.exception("Unexpected error")  # Logs full traceback
    return response(500, {"error": "Internal server error"})
```

---

### 9. **Validation & Pydantic** ⚠️ LOW PRIORITY (Nice to have)
**Why:** Automatic validation, type checking.

**Current way:**
```python
def handle_predict(body: Dict):
    team_a = body.get('team_a', '').upper()
    if not team_a:
        return response(400, {"error": "team_a required"})
    # ...
```

**Better way (Pydantic):**
```python
from pydantic import BaseModel, validator

class PredictionRequest(BaseModel):
    team_a: str
    team_b: str
    spread: float
    team_a_home: bool = False
    seasons: list[int] = [2024, 2025]
    
    @validator('team_a', 'team_b')
    def validate_team(cls, v):
        if v.upper() not in VALID_TEAMS:
            raise ValueError(f"Invalid team: {v}")
        return v.upper()
    
    @validator('spread')
    def validate_spread(cls, v):
        if abs(v) > 20:
            raise ValueError("Spread too large")
        return v

# Usage
def handle_predict(body: Dict):
    try:
        request = PredictionRequest(**body)  # Auto-validates!
        prediction = predictor.predict(
            team_a=request.team_a,
            team_b=request.team_b,
            spread=request.spread,
            team_a_home=request.team_a_home,
            seasons=request.seasons
        )
        return response(200, {"data": prediction})
    except ValidationError as e:
        return response(400, {"error": str(e)})
```

**Note:** Pydantic adds dependency. Only use if you want strict validation.

---

### 10. **Collections Utilities** ⚠️ LOW PRIORITY
**Why:** Useful data structures.

```python
from collections import defaultdict, Counter, namedtuple

# defaultdict - no KeyError
team_wins = defaultdict(int)
team_wins['KC'] += 1  # Works even if 'KC' doesn't exist

# Counter - count occurrences
teams = ['KC', 'BUF', 'KC', 'GB', 'KC']
team_counts = Counter(teams)
print(team_counts.most_common(2))  # [('KC', 3), ('BUF', 1)]

# namedtuple - lightweight data structure
from collections import namedtuple
Game = namedtuple('Game', ['home_team', 'away_team', 'score'])
game = Game('KC', 'BUF', 24-17)
print(game.home_team)  # 'KC'
```

---

## Skills You DON'T Need (For Now)

### ❌ Async/Await
- Lambda is synchronous
- Only needed for async frameworks (FastAPI async endpoints)

### ❌ Generators
- Useful for large datasets, but pandas handles this
- Learn later if processing huge files

### ❌ Decorators (Advanced)
- You don't need custom decorators yet
- `@dataclass`, `@contextmanager` are enough

### ❌ Metaclasses
- Too advanced, not needed

### ❌ Threading/Multiprocessing
- Lambda handles concurrency
- Not needed for your use case

---

## Quick Reference: Common Patterns

### Pattern 1: Safe Dict Access
```python
# Instead of: value = data['key']  # KeyError if missing
value = data.get('key', default_value)
nested = data.get('level1', {}).get('level2', {})
```

### Pattern 2: List Filtering
```python
# Instead of:
results = []
for item in items:
    if item['wins'] > 10:
        results.append(item)

# Use:
results = [item for item in items if item['wins'] > 10]
```

### Pattern 3: Error Handling
```python
try:
    result = risky_operation()
except SpecificError as e:
    logger.error(f"Specific error: {e}")
    handle_error()
except Exception as e:
    logger.exception("Unexpected error")  # Logs traceback
    raise
```

### Pattern 4: Type-Safe Constants
```python
from enum import Enum

class Status(Enum):
    ACTIVE = 'active'
    INACTIVE = 'inactive'

if status == Status.ACTIVE:  # Type-safe
    ...
```

---

## Learning Path

### Week 1: Essentials
- [ ] List/Dict comprehensions
- [ ] F-strings
- [ ] `.get()` for safe dict access

### Week 2: Error Handling
- [ ] Specific exception types
- [ ] Custom exceptions
- [ ] Context managers (`with`)

### Week 3: Data Structures
- [ ] Dataclasses
- [ ] Enums
- [ ] Collections utilities

### Week 4: Advanced (Optional)
- [ ] Advanced type hints
- [ ] Pydantic validation
- [ ] More patterns

---

## Practice Exercises

### Exercise 1: Convert to Comprehension
```python
# Convert this to list comprehension:
strong_teams = []
for game in games:
    if game['wins'] > 10:
        strong_teams.append(game['team'])
```

### Exercise 2: Use Context Manager
```python
# Rewrite this with context manager:
file = open('data.txt', 'r')
content = file.read()
file.close()
```

### Exercise 3: Create Dataclass
```python
# Convert this class to dataclass:
class TeamStats:
    def __init__(self, team: str, wins: int, losses: int):
        self.team = team
        self.wins = wins
        self.losses = losses
```

---

## Resources

- **Real Python**: https://realpython.com/ (Best Python tutorials)
- **Python Docs**: https://docs.python.org/3/
- **Type Hints**: https://docs.python.org/3/library/typing.html
- **Dataclasses**: https://docs.python.org/3/library/dataclasses.html

---

## Bottom Line

**Must Learn (This Month):**
1. List/Dict comprehensions
2. Context managers (`with`)
3. F-strings
4. Better error handling

**Nice to Have:**
5. Dataclasses
6. Enums
7. Advanced type hints

**Skip for Now:**
- Async/await
- Generators
- Advanced decorators
- Metaclasses

You're already 80% there! Focus on comprehensions and context managers first.

