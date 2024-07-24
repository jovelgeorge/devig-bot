import math
from enum import Enum

class KellyType(Enum):
    HK = 0.5
    QK = 0.25
    EK = 0.125

def decimal_to_american(decimal_odds: float) -> int:
    if decimal_odds == 1:
        return 0
    elif decimal_odds >= 2:
        return int((decimal_odds - 1) * 100)
    else:
        return int(-100 / (decimal_odds - 1))

def american_to_decimal(odds: int) -> float:
    return (odds / 100) + 1 if odds > 0 else (100 / abs(odds)) + 1

def implied_probability(odds: int) -> float:
    return abs(odds) / (abs(odds) + 100) if odds < 0 else 100 / (odds + 100)

def calculate_parlay_odds(odds_list: list) -> int:
    decimal_odds = [american_to_decimal(odds) for odds in odds_list]
    parlay_decimal = math.prod(decimal_odds)
    return decimal_to_american(parlay_decimal)

def expected_value(win_probability: float, bet_odds: int) -> float:
    decimal_odds = american_to_decimal(bet_odds)
    return (win_probability * decimal_odds) - 1

def kelly_criterion(win_probability: float, bet_odds: int) -> float:
    decimal_odds = american_to_decimal(bet_odds)
    if decimal_odds == 1 or win_probability == 1:
        return 0
    return max(0, (win_probability * decimal_odds - 1) / (decimal_odds - 1))

def parse_odds(odds_str: str) -> list:
    def process_avg(avg_str: str) -> int:
        avg_odds = [float(x.strip()) for x in avg_str[4:-1].split(',')]
        return int(sum(avg_odds) / len(avg_odds))

    legs = odds_str.split(',')
    parsed_legs = []
    for leg in legs:
        sides = leg.strip().split('/')
        parsed_sides = []
        for side in sides:
            if side.startswith('avg(') and side.endswith(')'):
                parsed_sides.append(process_avg(side))
            else:
                parsed_sides.append(int(side))
        parsed_legs.append(parsed_sides)
    return parsed_legs

def devig(odds: list) -> list:
    probs = [implied_probability(odd) for odd in odds]
    total_prob = sum(probs)
    return [prob / total_prob for prob in probs]

def calculate_ev(win_prob: float, odds: int) -> float:
    return (win_prob * american_to_decimal(odds)) - 1

def format_odds(odds: int) -> str:
    return f"+{odds}" if odds > 0 else f"{odds}"