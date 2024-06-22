import os
from dotenv import load_dotenv
import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='/', intents=intents)

# Function to convert American odds to decimal odds
def american_to_decimal(odds):
    if odds > 0:
        return (odds / 100) + 1
    else:
        return (100 / abs(odds)) + 1

# Function to convert decimal odds to American odds
def decimal_to_american(decimal_odds):
    if decimal_odds >= 2:
        return int((decimal_odds - 1) * 100)
    else:
        return int(-100 / (decimal_odds - 1))

# Function to calculate implied probability from American odds
def implied_probability(odds):
    if odds < 0:
        return abs(odds) / (abs(odds) + 100)
    else:
        return 100 / (odds + 100)

# Function to calculate expected value
def expected_value(win_probability, bet_odds):
    decimal_odds = american_to_decimal(bet_odds)
    return (win_probability * decimal_odds) - 1

# Function to calculate the Kelly Criterion
def kelly_criterion(win_probability, bet_odds):
    decimal_odds = american_to_decimal(bet_odds)
    return (win_probability * decimal_odds - 1) / (decimal_odds - 1)

# Function to handle messages
@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    try:
        await bot.tree.sync()
        print("Command tree synced successfully")
    except Exception as e:
        print(f"Failed to sync command tree: {e}")

# Discord Bot Commands

@bot.tree.command(name='ev')
@app_commands.describe(market_odds='Market odds', fair_odds='Fair value')
async def ev(interaction: discord.Interaction, market_odds: int, fair_odds: int):
    try:
        market_prob = implied_probability(market_odds)
        true_prob = implied_probability(fair_odds)
        ev_value = expected_value(true_prob, market_odds)
        kelly = kelly_criterion(true_prob, market_odds)
        qk = kelly / 4

        embed = discord.Embed(color=0x000000)

        # Padding to ensure wider embed
        padding = ' ' * 9

        # Odds field
        embed.add_field(name="Odds", value=f"```\n{market_odds}\n```", inline=False)
        
        # EV, QK, FV, WIN field
        ev_qk_fv_win = (
            f"EV: {ev_value:.2%}    QK: {qk:.2%}\n"
            f"FV: {fair_odds}    WIN: {true_prob:.2%}"
        )
        embed.add_field(name="Results", value=f"```\n{ev_qk_fv_win}\n```", inline=False)
        
        # Function to format odds with correct sign
        def format_odds(odds):
            return f"{odds:+d}" if odds > 0 else f"{odds}"

        # Combined Market Odds and Fair Odds field
        combined_odds = (
            f"Market Odds      Fair Odds{padding}\n"
            f"{market_prob*100:.2f}%: {format_odds(market_odds):>5}    {true_prob*100:.2f}%: {format_odds(fair_odds):>5}\n"
            f"{(1-market_prob)*100:.2f}%: {format_odds(decimal_to_american(1/(1-market_prob))):>5}    "
            f"{(1-true_prob)*100:.2f}%: {format_odds(decimal_to_american(1/(1-true_prob))):>5}"
        )
        embed.add_field(name="Comparison", value=f"```\n{combined_odds}\n```", inline=False)

        current_time = datetime.now().strftime("%I:%M %p")
        embed.set_footer(text=f"calculator™     •     {current_time}")
        
        await interaction.response.send_message(embed=embed)
    except ValueError:
        await interaction.response.send_message('Please enter valid odds.')

if __name__ == "__main__":
    bot.run(os.getenv('DISCORD_BOT_TOKEN'))