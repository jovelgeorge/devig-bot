from flask import jsonify
from utils.math_operations import (
    KellyType, parse_odds, implied_probability, decimal_to_american,
    calculate_parlay_odds, calculate_ev, kelly_criterion
)
from utils.dynamodb_operations import get_user_data

def create_embed(results: list, ev: float, kelly: float, kelly_type: KellyType, wager_amount: float, combined_fair_odds: int, combined_win_prob: float, user_bankroll: float = None) -> dict:
    embed = {
        "type": "rich",
        "color": 0x000000,
        "fields": [
            {
                "name": "Odds",
                "value": f"```\n{format_odds(results[0]['market_odds'])}    \n```",
                "inline": False
            }
        ]
    }
    
    if wager_amount is not None:
        embed["fields"].append({
            "name": "Wager Amount",
            "value": f"```\n{kelly_type.name}: ${wager_amount:.2f}    \n```",
            "inline": False
        })
    
    if ev is not None and kelly is not None:
        result_text = (
            f"EV: {ev:.2%}    {kelly_type.name}: {kelly:.2%}\n"
            f"FV: {format_odds(combined_fair_odds)}    WIN: {combined_win_prob:.2%}"
        )
        embed["fields"].append({
            "name": "Results",
            "value": f"```\n{result_text}\n```",
            "inline": False
        })

    for result in results:
        market_prob = implied_probability(result['market_odds'])
        true_prob = result['win']
        combined_odds = (
            f"Market Odds      Fair Odds\n"
            f"{market_prob*100:.2f}%: {format_odds(result['market_odds']):>5}    {true_prob*100:.2f}%: {format_odds(result['fair_odds']):>5}    \n"
            f"{(1-market_prob)*100:.2f}%: {format_odds(decimal_to_american(1/(1-market_prob))):>5}    "
            f"{(1-true_prob)*100:.2f}%: {format_odds(decimal_to_american(1/(1-true_prob))):>5}    \n"
        )
        embed["fields"].append({
            "name": "Comparison",
            "value": f"```\n{combined_odds}\n```",
            "inline": False
        })

    return embed

def handle_ev_command(ctx, market_odds: str, fair_odds: int = None, bet_odds: int = None):
    try:
        parsed_odds = [parse_odds(leg.strip()) for leg in market_odds.split(',')]

        user_id = ctx.author.id
        user_settings = get_user_data(user_id)
        kelly_type = KellyType[user_settings.get("kelly", "QK")]
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
            kelly = kelly_criterion(combined_win_prob, int(market_odds)) * kelly_type.value
            wager_amount = kelly * user_bankroll if user_bankroll else None
        elif bet_odds is not None:
            ev = calculate_ev(combined_win_prob, bet_odds)
            kelly = kelly_criterion(combined_win_prob, bet_odds) * kelly_type.value
            wager_amount = kelly * user_bankroll if user_bankroll else None
        else:
            ev = None
            kelly = None
            wager_amount = None

        embed = create_embed(results, ev, kelly, kelly_type, wager_amount, combined_fair_odds, combined_win_prob, user_bankroll)
        return jsonify({
            "type": 4,
            "data": {
                "embeds": [embed]
            }
        })

    except Exception as e:
        print(f"Unexpected error in ev command: {str(e)}")
        return jsonify({
            "type": 4,
            "data": {
                "content": f"An unexpected error occurred: {str(e)}"
            }
        })