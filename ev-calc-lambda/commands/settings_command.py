from flask import jsonify
from utils.math_operations import KellyType
from utils.dynamodb_operations import get_user_data, save_user_data

def handle_settings_command(ctx, bankroll: float = None, toggle_bankroll: bool = None, kelly: str = None):
    user_id = ctx.author.id
    user_settings = get_user_data(user_id)

    if bankroll is not None:
        user_settings["bankroll"] = bankroll
    
    if toggle_bankroll is not None:
        user_settings["bankroll_enabled"] = toggle_bankroll

    if kelly is not None:
        if kelly in [k.name for k in KellyType]:
            user_settings["kelly"] = kelly
        else:
            return jsonify({
                "type": 4,
                "data": {
                    "content": "Invalid Kelly type. Please choose from HK, QK, or EK."
                }
            })

    save_user_data(user_id, user_settings)

    response = "Settings updated:\n"
    if bankroll is not None:
        response += f"Bankroll set to ${bankroll:,.2f}\n"
    if toggle_bankroll is not None:
        response += f"Bankroll calculations {'enabled' if toggle_bankroll else 'disabled'}\n"
    if kelly is not None:
        response += f"Kelly Criterion type set to {kelly}"

    return jsonify({
        "type": 4,
        "data": {
            "content": response,
            "flags": 64  # Ephemeral flag
        }
    })