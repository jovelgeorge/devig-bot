import os
import re
from dotenv import load_dotenv
import discord
from discord import app_commands
from discord.ext import commands
import json
from typing import List, Dict, Union, Tuple
from datetime import datetime

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='/', intents=intents)

EMBED_COLOR = 0x000000
PADDING = ' ' * 4
USER_DATA_FILE = 'user_data.json'

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

def calculate_parlay_odds(odds_list: List[int]) -> int:
    decimal_odds = [american_to_decimal(odds) for odds in odds_list]
    parlay_decimal = 1
    for odds in decimal_odds:
        parlay_decimal *= odds
    return decimal_to_american(parlay_decimal)

def expected_value(win_probability: float, bet_odds: int) -> float:
    decimal_odds = american_to_decimal(bet_odds)
    return (win_probability * decimal_odds) - 1

def kelly_criterion(win_probability: float, bet_odds: int) -> float:
    decimal_odds = american_to_decimal(bet_odds)
    if decimal_odds == 1 or win_probability == 1:
        return 0
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
    except Exception as e:
        print(f"Failed to sync command tree: {e}")

@bot.tree.command(name='ev', description="EV Calculator & Devigger")
@app_commands.describe(
    market_odds='Enter the market odds (use comma for multiple legs)',
    fair_odds='Enter the fair value odds (optional)',
    bet_odds='Enter the bet odds (optional)'
)
async def ev(interaction: discord.Interaction, market_odds: str, fair_odds: int = None, bet_odds: int = None):
    try:
        market_odds = re.sub(r'avg\([^)]+\)', lambda m: str(int(sum(float(x.strip()) for x in m.group()[4:-1].split(',')) / len(m.group()[4:-1].split(',')))), market_odds)
        
        parsed_odds = [parse_odds(leg.strip()) for leg in market_odds.split(',')]

        user_id = str(interaction.user.id)
        user_settings = user_data.get(user_id, {})
        user_bankroll = user_settings.get("bankroll") if user_settings.get("bankroll_enabled", True) else None

        results = []
        fair_odds_list = []

        for i, leg in enumerate(parsed_odds):
            market_bet_odds = leg[0][0]
            if fair_odds is not None and i == 0:
                fair_american = fair_odds
                win_prob = implied_probability(fair_american)
            elif len(leg[0]) > 1:
                win_prob = devig(leg[0])[0]
                fair_american = decimal_to_american(1 / win_prob)
            else:
                win_prob = implied_probability(market_bet_odds)
                fair_american = market_bet_odds
            
            fair_odds_list.append(fair_american)
            results.append({
                'market_odds': market_bet_odds,
                'fair_odds': fair_american,
                'win': win_prob,
            })

        combined_fair_odds = calculate_parlay_odds(fair_odds_list)
        combined_win_prob = implied_probability(combined_fair_odds)

        if fair_odds is not None:
            ev = calculate_ev(combined_win_prob, int(market_odds))
            qk = kelly_criterion(combined_win_prob, int(market_odds)) / 4
            wager_amount = qk * user_bankroll if user_bankroll else None
        elif bet_odds is not None:
            ev = calculate_ev(combined_win_prob, bet_odds)
            qk = kelly_criterion(combined_win_prob, bet_odds) / 4
            wager_amount = qk * user_bankroll if user_bankroll else None
        else:
            ev = None
            qk = None
            wager_amount = None

        embed = create_embed(results, ev, qk, wager_amount, combined_fair_odds, combined_win_prob, user_bankroll)
        await interaction.response.send_message(embed=embed)

    except Exception as e:
        error_message = f'An unexpected error occurred: {str(e)}'
        if interaction.response.is_done():
            await interaction.followup.send(error_message)
        else:
            await interaction.response.send_message(error_message)
        print(f"Unexpected error in ev command: {str(e)}")

def create_embed(results: List[Dict[str, Union[int, float]]], ev: float, qk: float, wager_amount: float, combined_fair_odds: int, combined_win_prob: float, user_bankroll: float = None) -> discord.Embed:
    embed = discord.Embed(color=EMBED_COLOR)
    
    if wager_amount is not None:
        embed.add_field(name="Wager Amount (QK)", value=f"```\n${wager_amount:.2f}{PADDING}\n```", inline=False)
    
    if ev is not None and qk is not None:
        result_text = (
            f"EV: {ev:.2%}    QK: {qk:.2%}\n"
            f"FV: {format_odds(combined_fair_odds)}    WIN: {combined_win_prob:.2%}"
        )
        embed.add_field(name="Results", value=f"```\n{result_text}\n```", inline=False)

    for i, result in enumerate(results):
        if len(results) > 1:
            title = f"Leg #{i+1}"
        else:
            title = "Comparison"

        market_prob = implied_probability(result['market_odds'])
        true_prob = result['win']
        combined_odds = (
            f"OG Odds          Fair Odds\n"
            f"{market_prob*100:.2f}%: {format_odds(result['market_odds']):>5}    {true_prob*100:.2f}%: {format_odds(result['fair_odds']):>5}{PADDING}\n"
            f"{(1-market_prob)*100:.2f}%: {format_odds(decimal_to_american(1/(1-market_prob))):>5}    "
            f"{(1-true_prob)*100:.2f}%: {format_odds(decimal_to_american(1/(1-true_prob))):>5}{PADDING}\n"
        )
        embed.add_field(name=title, value=f"```\n{combined_odds}\n```", inline=False)

    current_time = datetime.now().strftime("%I:%M %p")
    embed.set_footer(text=f"calculator™     •     {current_time}")
    
    return embed

@bot.tree.command(name='settings', description="Manage your calculator settings")
@app_commands.describe(
    bankroll='Set your bankroll amount',
    enable_bankroll='Enable or disable bankroll calculations'
)
async def settings(interaction: discord.Interaction, bankroll: float = None, enable_bankroll: bool = None):
    user_id = str(interaction.user.id)
    user_settings = user_data.get(user_id, {})

    if bankroll is not None:
        user_settings["bankroll"] = bankroll
    
    if enable_bankroll is not None:
        user_settings["bankroll_enabled"] = enable_bankroll

    user_data[user_id] = user_settings
    save_user_data(user_data)

    response = "Settings updated:\n"
    if bankroll is not None:
        response += f"Bankroll set to ${bankroll:,.2f}\n"
    if enable_bankroll is not None:
        response += f"Bankroll calculations {'enabled' if enable_bankroll else 'disabled'}"

    await interaction.response.send_message(response)

if __name__ == "__main__":
    bot.run(os.getenv('DISCORD_BOT_TOKEN'))