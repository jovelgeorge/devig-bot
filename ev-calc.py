import os
from dotenv import load_dotenv
import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime
import re
from typing import List, Dict, Union, Tuple

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='/', intents=intents)

# Constants
EMBED_COLOR = 0x000000
PADDING = ' ' * 4
NO_EDGE_MESSAGE = "No edge, so no bet"

def american_to_decimal(odds: int) -> float:
    return (odds / 100) + 1 if odds > 0 else (100 / abs(odds)) + 1

def decimal_to_american(decimal_odds: float) -> int:
    if decimal_odds == 1:
        return 0
    elif decimal_odds >= 2:
        return int((decimal_odds - 1) * 100)
    else:
        return int(-100 / (decimal_odds - 1))

def implied_probability(odds: int) -> float:
    return abs(odds) / (abs(odds) + 100) if odds < 0 else 100 / (odds + 100)

def expected_value(win_probability: float, bet_odds: int) -> float:
    decimal_odds = american_to_decimal(bet_odds)
    return (win_probability * decimal_odds) - 1

def kelly_criterion(win_probability: float, bet_odds: int) -> float:
    decimal_odds = american_to_decimal(bet_odds)
    if decimal_odds == 1 or win_probability == 1:
        return 0  # No edge, so no bet
    return max(0, (win_probability * decimal_odds - 1) / (decimal_odds - 1))

def parse_odds(odds_str: str) -> List[List[int]]:
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

def devig(odds: List[int]) -> List[float]:
    probs = [implied_probability(odd) for odd in odds]
    total_prob = sum(probs)
    return [prob / total_prob for prob in probs]

def calculate_ev(win_prob: float, odds: int) -> float:
    return (win_prob * american_to_decimal(odds)) - 1

def format_odds(odds: Union[int, str]) -> str:
    try:
        return f"+{odds}" if int(odds) > 0 else f"{odds}"
    except ValueError:
        return str(odds)

def create_embed(market_odds: str, results: List[Dict[str, Union[int, float]]]) -> discord.Embed:
    embed = discord.Embed(color=EMBED_COLOR)
    
    formatted_market_odds = '/'.join(format_odds(odd) for odd in market_odds.split('/'))
    embed.add_field(name="Odds", value=f"```\n{formatted_market_odds}{PADDING}\n```", inline=False)
    
    if results:
        result = results[0]
        ev_qk_fv_win = (
            f"EV: {result['ev']:.2%}    QK: {result['qk']:.2%}\n"
            f"FV: {format_odds(result['fair_odds'])}    WIN: {result['win']:.2%}"
        )
        embed.add_field(name="Results", value=f"```\n{ev_qk_fv_win}\n```", inline=False)

        market_prob = implied_probability(result['market_odds'])
        true_prob = result['win']
        combined_odds = (
            f"Market Odds      Fair Odds\n"
            f"{market_prob*100:.2f}%: {format_odds(result['market_odds']):>5}    {true_prob*100:.2f}%: {format_odds(result['fair_odds']):>5}{PADDING}\n"
            f"{(1-market_prob)*100:.2f}%: {format_odds(decimal_to_american(1/(1-market_prob))):>5}    "
            f"{(1-true_prob)*100:.2f}%: {format_odds(decimal_to_american(1/(1-true_prob))):>5}{PADDING}\n"
        )
        embed.add_field(name="Comparison", value=f"```\n{combined_odds}\n```", inline=False)

    current_time = datetime.now().strftime("%I:%M %p")
    embed.set_footer(text=f"calculator™     •     {current_time}")
    
    return embed

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    try:
        await bot.tree.sync()
        print("Command tree synced successfully")
    except Exception as e:
        print(f"Failed to sync command tree: {e}")

@bot.tree.command(name='ev', description="Devig/Fair Value Calculator")
@app_commands.describe(
    market_odds='Enter the market odds',
    fair_odds='Enter the fair value odds',
    bet_odds='Enter the bet odds'
)
async def ev(interaction: discord.Interaction, market_odds: str, fair_odds: int = None, bet_odds: int = None):
    try:
        market_odds = re.sub(r'avg\([^)]+\)', lambda m: str(int(sum(float(x.strip()) for x in m.group()[4:-1].split(',')) / len(m.group()[4:-1].split(',')))), market_odds)
        
        parsed_odds = parse_odds(market_odds)
        results = []

        for leg in parsed_odds:
            market_bet_odds = leg[0]
            if fair_odds is not None:
                fair_american, win_prob, comparison_odds = int(fair_odds), implied_probability(int(fair_odds)), market_bet_odds
            elif bet_odds is not None:
                if len(leg) < 2:
                    raise ValueError("Market odds must be provided as a two-way line when using bet_odds")
                win_prob = devig(leg)[0]
                fair_american, comparison_odds = decimal_to_american(1 / win_prob), bet_odds
            elif len(leg) > 1:
                win_prob = devig(leg)[0]
                fair_american, comparison_odds = decimal_to_american(1 / win_prob), market_bet_odds
            else:
                raise ValueError("Fair odds or bet odds must be provided for single-sided markets")
            
            results.append({
                'market_odds': market_bet_odds,
                'comparison_odds': comparison_odds,
                'fair_odds': fair_american,
                'ev': calculate_ev(win_prob, comparison_odds),
                'win': win_prob,
                'qk': kelly_criterion(win_prob, comparison_odds) / 4
            })

        embed = create_embed(market_odds, results)
        await interaction.response.send_message(embed=embed)

    except ValueError as e:
        await interaction.response.send_message(f'Error: Invalid input - {str(e)}')
    except ZeroDivisionError:
        await interaction.response.send_message('Error: Cannot process odds that result in 100% probability.')
    except TypeError as e:
        await interaction.response.send_message(f'Error: Invalid input type - {str(e)}')
    except Exception as e:
        await interaction.response.send_message(f'An unexpected error occurred: {str(e)}')
        print(f"Unexpected error in ev command: {str(e)}")

if __name__ == "__main__":
    bot.run(os.getenv('DISCORD_BOT_TOKEN'))