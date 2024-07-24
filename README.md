# devig & EV calculator

This bot calculates expected value (EV) for sports betting odds.

## setup

1. Clone the repository
2. Create a virtual environment: `python3 -m venv env`
3. Activate the virtual environment: `source env/bin/activate`
4. Install requirements: `pip install -r requirements.txt`
5. Create a `.env` file and add your Discord bot token:
   
```
DISCORD_BOT_TOKEN=your_token_here
```

6. Run the bot: `ev-calc.py`

## commands

Type `/ev` and it will show you a list of parameters 

*market_odds* — Enter the market odds
- For two-way markets: `-130/110`
- For multiple legs: `-130/110, -125/115`
- For market averages: `avg(-130, -145)/avg(110,115)`
*bet_odds* — The odds for the bet
*fair_odds* — For when you already have the fair value

Type `/settings` and it will show you a list of personal settings

*toggle_bankroll* — Enable or disable bankroll calculations.
*bankroll* — Set bankroll amount
*kelly* — Set Kelly Criterion type: `HK`, `QK`, `EK`
*devig_type* — Set devig method: `wc` (default), `pb` (probit)

The calculator can also be toggled without the command tree for quick calculations. ex: `bet_odds:fair_odds`
