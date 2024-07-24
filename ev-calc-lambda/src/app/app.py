import os
import json
from flask import Flask, request, jsonify
from discord_interactions import verify_key_decorator
from discord_interactions.flask_ext import Interactions

from utils.math_operations import (
    decimal_to_american, american_to_decimal, implied_probability,
    calculate_parlay_odds, expected_value, kelly_criterion, parse_odds,
    devig, calculate_ev, format_odds
)
from utils.dynamodb_operations import get_user_data, save_user_data
from commands.ev_command import handle_ev_command
from commands.settings_command import handle_settings_command

app = Flask(__name__)
interactions = Interactions(app)

PUBLIC_KEY = os.environ['DISCORD_PUBLIC_KEY']

@app.route('/interactions', methods=['POST'])
@verify_key_decorator(PUBLIC_KEY)
def interactions_route():
    return interactions.handle(request)

@interactions.command()
def ev(ctx, market_odds: str, fair_odds: int = None, bet_odds: int = None):
    return handle_ev_command(ctx, market_odds, fair_odds, bet_odds)

@interactions.command()
def settings(ctx, bankroll: float = None, toggle_bankroll: bool = None, kelly: str = None):
    return handle_settings_command(ctx, bankroll, toggle_bankroll, kelly)

if __name__ == '__main__':
    app.run(debug=True)