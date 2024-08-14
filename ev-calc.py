import discord
from discord import app_commands
from discord.ext import commands
import os
from dotenv import load_dotenv
import re
import json
from typing import List, Dict, Union, Tuple
from datetime import datetime
import numpy as np
from scipy import stats
from enum import Enum

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='/', intents=intents)

EMBED_COLOR = 0x000000
PADDING = ' ' * 4
USER_DATA_FILE = 'user_data.json'

class KellyType(Enum):
    FK = 1
    HK = 0.5
    QK = 0.25
    EK = 0.125

class DevigMethod(Enum):
    wc = "worst-case (default)"
    power = "power"
    probit = "probit"
    tko = "tko"
    goto = "goto"

def american_to_decimal(odds: int) -> float:
    return (odds / 100) + 1 if odds > 0 else (100 / abs(odds)) + 1

def implied_probability(odds: int) -> float:
    return abs(odds) / (abs(odds) + 100) if odds < 0 else 100 / (odds + 100)

def decimal_to_american(decimal_odds: float) -> int:
    if decimal_odds == 1:
        return 0
    elif decimal_odds >= 2:
        return int((decimal_odds - 1) * 100)
    else:
        return int(-100 / (decimal_odds - 1))

def calculate_win_prob_from_fair_odds(fair_odds: int) -> float:
    return implied_probability(fair_odds)

def parse_two_way_odds(odds_str: str) -> Tuple[int, int]:
    odds = odds_str.split('/')
    if len(odds) != 2:
        raise ValueError("Invalid two-way odds format. Use 'odds1/odds2'")
    return int(odds[0]), int(odds[1])

def remove_vig_two_way(odds1: int, odds2: int) -> Tuple[float, float]:
    prob1 = implied_probability(odds1)
    prob2 = implied_probability(odds2)
    total_prob = prob1 + prob2
    fair_prob1 = prob1 / total_prob
    fair_prob2 = prob2 / total_prob
    return fair_prob1, fair_prob2

def create_devig_embed(market_odds1: int, market_odds2: int, fair_odds1: int, fair_odds2: int) -> discord.Embed:
    embed = discord.Embed(color=EMBED_COLOR)
    
    market_prob1 = implied_probability(market_odds1)
    market_prob2 = implied_probability(market_odds2)
    fair_prob1 = implied_probability(fair_odds1)
    fair_prob2 = implied_probability(fair_odds2)
    
    comparison = (
        f"Market Odds      Fair Odds\n"
        f"{market_prob1*100:05.2f}%: {format_odds(market_odds1):>5}    {fair_prob1*100:05.2f}%: {format_odds(fair_odds1):>5}{PADDING}\n"
        f"{market_prob2*100:05.2f}%: {format_odds(market_odds2):>5}    {fair_prob2*100:05.2f}%: {format_odds(fair_odds2):>5}{PADDING}\n"
    )
    embed.add_field(name="Comparison", value=f"```\n{comparison}\n```", inline=False)
    
    return embed

def create_multi_leg_devig_embed(results: List[Dict]) -> discord.Embed:
    embed = discord.Embed(color=EMBED_COLOR)
    
    for result in results:
        leg_number = result['leg']
        comparison = (
            f"Market Odds      Fair Odds\n"
            f"{result['market_prob1']*100:05.2f}%: {format_odds(result['market_odds1']):>5}    "
            f"{result['fair_prob1']*100:05.2f}%: {format_odds(result['fair_odds1']):>5}{PADDING}\n"
            f"{result['market_prob2']*100:05.2f}%: {format_odds(result['market_odds2']):>5}    "
            f"{result['fair_prob2']*100:05.2f}%: {format_odds(result['fair_odds2']):>5}{PADDING}\n"
        )
        embed.add_field(name=f"Leg #{leg_number}", value=f"```\n{comparison}\n```", inline=False)
    
    return embed

def expected_value(win_probability: float, bet_odds: int) -> float:
    decimal_odds = american_to_decimal(bet_odds)
    return (win_probability * decimal_odds) - 1

def kelly_criterion(win_probability: float, bet_odds: int) -> float:
    decimal_odds = american_to_decimal(bet_odds)
    if decimal_odds == 1 or win_probability == 1:
        return 0
    return max(0, (win_probability * decimal_odds - 1) / (decimal_odds - 1))

def calculate_parlay_odds(odds_list: List[int]) -> int:
    decimal_odds = [american_to_decimal(odds) for odds in odds_list]
    parlay_decimal = 1
    for odds in decimal_odds:
        parlay_decimal *= odds
    return decimal_to_american(parlay_decimal)

def calculate_parlay_ev(win_probs: List[float], bet_odds: int) -> float:
    combined_prob = np.prod(win_probs)
    return expected_value(combined_prob, bet_odds)

def parse_odds(odds_str: str) -> Tuple[List[int], int]:
    parts = odds_str.split(':')
    if len(parts) == 2:
        bet_odds = int(parts[1])
        fair_odds = [int(x) for x in parts[0].split(',')]
    else:
        bet_odds = None
        fair_odds = [int(x) for x in parts[0].split(',')]
    return fair_odds, bet_odds

def worst_case_devig(odds: List[int]) -> List[float]:
    probs = [implied_probability(odd) for odd in odds]
    total_prob = sum(probs)
    return [prob / total_prob for prob in probs]

def power_devig(odds: List[int], iterations: int = 100) -> List[float]:
    probs = [implied_probability(odd) for odd in odds]
    k = 1
    for _ in range(iterations):
        new_probs = [p**k for p in probs]
        total = sum(new_probs)
        if abs(total - 1) < 1e-10:
            break
        k *= (1 / total) ** (1 / len(odds))
    return [p**k / sum(p**k for p in probs) for p in probs]

def probit_devig(odds: List[int]) -> List[float]:
    probs = [implied_probability(odd) for odd in odds]
    z_scores = stats.norm.ppf(probs)
    adjustment = np.mean(z_scores)
    adjusted_z_scores = z_scores - adjustment
    return stats.norm.cdf(adjusted_z_scores).tolist()

def tko_devig(odds: List[int]) -> List[float]:
    if len(odds) != 2:
        raise ValueError("TKO devigging method only works for two outcomes")
    p1, p2 = [implied_probability(odd) for odd in odds]
    q1, q2 = 1 - p1, 1 - p2
    b0 = np.log(p2 / q1) / np.log(p1 / q2)
    p = b0 / (1 + b0)
    return [p, 1 - p]

def goto_conversion(odds: List[Union[int, float]], total: float = 1, alpha: float = 1, beta: float = 1, eps: float = 1e-6) -> List[float]:
    decimal_odds = np.array([american_to_decimal(odd) if isinstance(odd, int) else odd for odd in odds])
    if len(decimal_odds) < 2:
        raise ValueError('len(odds) must be >= 2')
    if np.any(decimal_odds < 1):
        raise ValueError('All odds must be >= 1')
    probabilities = 1 / decimal_odds
    se = np.sqrt((probabilities - probabilities**2) / ((probabilities**alpha) / beta))
    step = (np.sum(probabilities) - total) / np.sum(se)
    output_probabilities = np.clip(probabilities - (se * step), eps, 1 - eps)
    return (output_probabilities / np.sum(output_probabilities)).tolist()

def devig(odds: List[int], method: DevigMethod = DevigMethod.wc) -> List[float]:
    devig_functions = {
        DevigMethod.wc: worst_case_devig,
        DevigMethod.power: power_devig,
        DevigMethod.probit: probit_devig,
        DevigMethod.tko: tko_devig,
        DevigMethod.goto: goto_conversion
    }
    try:
        result = devig_functions[method](odds)
        if abs(sum(result) - 1) > 1e-6:
            print(f"Warning: Devigged probabilities do not sum to 1 for method {method.name}. Sum: {sum(result)}")
        return result
    except Exception as e:
        print(f"Error in devigging with method {method.name}: {str(e)}")
        return worst_case_devig(odds)

def calculate_ev(win_prob: float, odds: int) -> float:
    return (win_prob * american_to_decimal(odds)) - 1

def format_odds(odds: Union[int, float]) -> str:
    return f"+{odds}" if odds > 0 else f"{odds}"

def format_ev(ev: float) -> str:
    return f"{ev:05.2f}%" if ev >= 0 else f"{ev:06.2f}%"

def create_embed(results: List[Dict[str, Union[int, float]]], ev: float, kelly: float, kelly_type: KellyType, wager_amount: float, combined_fair_odds: int, combined_win_prob: float, devig_method: DevigMethod, user_bankroll: float = None, is_parlay: bool = False, bet_odds: int = None) -> discord.Embed:
    embed = discord.Embed(color=EMBED_COLOR)
    
    display_odds = bet_odds if bet_odds is not None else results[0]['market_odds']
    embed.add_field(name="Bet Odds", value=f"```\n{format_odds(display_odds)}{PADDING}\n```", inline=False)
    
    if wager_amount is not None:
        embed.add_field(name=f"Wager Amount ({kelly_type.name})", value=f"```\n${wager_amount:.2f}{PADDING}\n```", inline=False)
    
    if ev is not None and kelly is not None:
        result_text = (
            f"EV: {format_ev(ev*100)}    {kelly_type.name}: {kelly:.2%}\n"
            f"FV: {format_odds(combined_fair_odds)}      WIN: {combined_win_prob:.2%}"
        )
        embed.add_field(name=f"Results", value=f"```\n{result_text}\n```", inline=False)

    for i, result in enumerate(results):
        title = f"Leg {i+1}" if is_parlay else "Comparison"

        market_prob = implied_probability(result['market_odds'])
        true_prob = result['win']
        combined_odds = (
            f"Market Odds      Fair Odds\n"
            f"{market_prob*100:05.2f}%: {format_odds(result['market_odds']):>5}    {true_prob*100:05.2f}%: {format_odds(result['fair_odds']):>5}{PADDING}\n"
            f"{(1-market_prob)*100:05.2f}%: {format_odds(decimal_to_american(1/(1-market_prob))):>5}    "
            f"{(1-true_prob)*100:05.2f}%: {format_odds(decimal_to_american(1/(1-true_prob))):>5}{PADDING}\n"
        )
        embed.add_field(name=title, value=f"```\n{combined_odds}\n```", inline=False)
    
    return embed

def load_user_data():
    if os.path.exists(USER_DATA_FILE):
        with open(USER_DATA_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_user_data(data):
    with open(USER_DATA_FILE, 'w') as f:
        json.dump(data, f)

user_data = load_user_data()

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    try:
        await bot.tree.sync()
        print("Command tree synced successfully")
        custom_activity = discord.Activity(name="powered by JOVEL", type=discord.ActivityType.custom)
        await bot.change_presence(activity=custom_activity)
    except Exception as e:
        print(f"Failed to sync command tree: {e}")

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    parts = [part.strip() for part in message.content.split(':')]

    if len(parts) == 2:
        bet_odds_str, fair_odds_str = parts

        def is_valid_odds(odds_str):
            try:
                odds = int(odds_str)
                return odds <= -100 or odds >= 100
            except ValueError:
                return False

        if is_valid_odds(bet_odds_str) and all(is_valid_odds(odd) for odd in fair_odds_str.split(',')):
            bet_odds = int(bet_odds_str)
            fair_odds = [int(x) for x in fair_odds_str.split(',')]

            user_id = str(message.author.id)
            user_settings = user_data.get(user_id, {})
            devig_method = DevigMethod(user_settings.get("devig_method", DevigMethod.wc.value))
            kelly_type = KellyType[user_settings.get("kelly", "QK")]
            user_bankroll = user_settings.get("bankroll") if user_settings.get("bankroll_enabled", True) else None

            results = []
            win_probs = []

            for fair_odd in fair_odds:
                win_prob = implied_probability(fair_odd)
                win_probs.append(win_prob)
                results.append({
                    'market_odds': bet_odds,
                    'fair_odds': fair_odd,
                    'win': win_prob,
                })

            combined_fair_odds = calculate_parlay_odds(fair_odds)
            combined_win_prob = np.prod(win_probs)

            ev = calculate_ev(combined_win_prob, bet_odds)
            kelly = kelly_criterion(combined_win_prob, bet_odds) * kelly_type.value
            wager_amount = kelly * user_bankroll if user_bankroll else None

            is_parlay = len(results) > 1
            embed = create_embed(results, ev, kelly, kelly_type, wager_amount, combined_fair_odds, combined_win_prob, devig_method, user_bankroll, is_parlay, bet_odds)

            await message.channel.send(embed=embed)

    await bot.process_commands(message)


@bot.tree.command(name='ev', description="EV Calculator & Devigger")
@app_commands.describe(
    odds='Enter the fair odds (use comma for multiple legs) or two-way market odds (use slash)',
    bet_odds='Enter the bet odds (optional)',
    kelly='Set Kelly Criterion type (FK, HK, QK, EK)',
    devig_method='Set devig method (wc, power, probit, tko, or goto)'
)
async def ev(interaction: discord.Interaction, odds: str, bet_odds: int = None, kelly: str = None, devig_method: str = None):
    try:
        # Check if the input contains two-way market odds
        if '/' in odds:
            legs = odds.split(',')
            results = []
            for i, leg in enumerate(legs, 1):
                leg = leg.strip()
                if '/' in leg:
                    market_odds1, market_odds2 = parse_two_way_odds(leg)
                    fair_prob1, fair_prob2 = remove_vig_two_way(market_odds1, market_odds2)
                    fair_odds1 = decimal_to_american(1 / fair_prob1)
                    fair_odds2 = decimal_to_american(1 / fair_prob2)
                    results.append({
                        'leg': i,
                        'market_odds1': market_odds1,
                        'market_odds2': market_odds2,
                        'fair_odds1': fair_odds1,
                        'fair_odds2': fair_odds2,
                        'market_prob1': implied_probability(market_odds1),
                        'market_prob2': implied_probability(market_odds2),
                        'fair_prob1': fair_prob1,
                        'fair_prob2': fair_prob2
                    })
                else:
                    raise ValueError(f"Invalid format for leg {i}: {leg}")
            
            embed = create_multi_leg_devig_embed(results)
            await interaction.response.send_message(embed=embed)
            return

        # Handle multi-leg odds
        odds = re.sub(r'avg\([^)]+\)', lambda m: str(int(sum(float(x.strip()) for x in m.group()[4:-1].split(',')) / len(m.group()[4:-1].split(',')))), odds)
        
        fair_odds, parsed_bet_odds = parse_odds(odds)
        bet_odds = bet_odds or parsed_bet_odds

        user_id = str(interaction.user.id)
        user_settings = user_data.get(user_id, {})
        
        if devig_method:
            if devig_method not in DevigMethod.__members__:
                await interaction.response.send_message(f"Invalid devig method: {devig_method}. Valid options are: {', '.join(DevigMethod.__members__.keys())}", ephemeral=True)
                return
            devig_method = DevigMethod[devig_method]
        else:
            devig_method = DevigMethod(user_settings.get("devig_method", DevigMethod.wc.value))
        
        if kelly:
            if kelly not in KellyType.__members__:
                await interaction.response.send_message(f"Invalid Kelly type: {kelly}. Valid options are: {', '.join(KellyType.__members__.keys())}", ephemeral=True)
                return
            kelly_type = KellyType[kelly]
        else:
            kelly_type = KellyType[user_settings.get("kelly", "QK")]
        
        user_bankroll = user_settings.get("bankroll") if user_settings.get("bankroll_enabled", True) else None

        results = []
        win_probs = []

        for fair_odd in fair_odds:
            win_prob = implied_probability(fair_odd)
            win_probs.append(win_prob)
            results.append({
                'market_odds': bet_odds or fair_odd,
                'fair_odds': fair_odd,
                'win': win_prob,
            })

        combined_fair_odds = calculate_parlay_odds(fair_odds)
        combined_win_prob = np.prod(win_probs)

        if bet_odds is None:
            bet_odds = fair_odds[0] if len(fair_odds) == 1 else calculate_parlay_odds(fair_odds)

        ev = calculate_ev(combined_win_prob, bet_odds)
        kelly = kelly_criterion(combined_win_prob, bet_odds) * kelly_type.value
        wager_amount = kelly * user_bankroll if user_bankroll else None

        is_parlay = len(results) > 1
        embed = create_embed(results, ev, kelly, kelly_type, wager_amount, combined_fair_odds, combined_win_prob, devig_method, user_bankroll, is_parlay, bet_odds)
        
        await interaction.response.send_message(embed=embed)

    except Exception as e:
        error_message = f'An unexpected error occurred: {str(e)}'
        if interaction.response.is_done():
            await interaction.followup.send(error_message)
        else:
            await interaction.response.send_message(error_message)
        print(f"Unexpected error in ev command: {str(e)}")

@bot.tree.command(name='settings', description="Manage your calculator settings")
@app_commands.describe(
    bankroll='Set your bankroll amount',
    toggle_bankroll='Enable or disable bankroll calculations',
    kelly='Set Kelly Criterion type (FK, HK, QK, EK)',
    devig_method='Set devig method (wc, power, probit, tko, or goto)'
)
async def settings(interaction: discord.Interaction, bankroll: float = None, toggle_bankroll: bool = None, kelly: str = None, devig_method: str = None):
    await interaction.response.defer(ephemeral=True)
    
    try:
        user_id = str(interaction.user.id)
        user_settings = user_data.get(user_id, {})

        if bankroll is not None:
            user_settings["bankroll"] = bankroll
        
        if toggle_bankroll is not None:
            user_settings["bankroll_enabled"] = toggle_bankroll

        if kelly is not None:
            if kelly in KellyType.__members__:
                user_settings["kelly"] = kelly
            else:
                await interaction.followup.send(f"Invalid Kelly type: {kelly}. Valid options are: {', '.join(KellyType.__members__.keys())}", ephemeral=True)
                return

        if devig_method is not None:
            if devig_method in DevigMethod.__members__:
                user_settings["devig_method"] = devig_method
            else:
                await interaction.followup.send(f"Invalid devig method: {devig_method}. Valid options are: {', '.join(DevigMethod.__members__.keys())}", ephemeral=True)
                return

        user_data[user_id] = user_settings
        save_user_data(user_data)

        response = "Settings updated:\n"
        if bankroll is not None:
            response += f"Bankroll set to ${bankroll:,.2f}\n"
        if toggle_bankroll is not None:
            response += f"Bankroll calculations {'enabled' if toggle_bankroll else 'disabled'}\n"
        if kelly is not None:
            response += f"Kelly Criterion type set to {kelly}\n"
        if devig_method is not None:
            response += f"Devigging method set to {devig_method}"

        await interaction.followup.send(response, ephemeral=True)

    except Exception as e:
        print(f"Error in settings command: {str(e)}")
        await interaction.followup.send(f"An error occurred while updating settings: {str(e)}", ephemeral=True)

if __name__ == "__main__":
    bot.run(os.getenv('DISCORD_BOT_TOKEN'))