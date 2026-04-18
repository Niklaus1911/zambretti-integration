import logging

_LOGGER = logging.getLogger(__name__)


def safe_float(value, default=0.0):
    """Safely converts a value to a float, returning a default if conversion fails."""
    try:
        return float(value)
    except (ValueError, TypeError):
        return default  # Return default if conversion fails


def alert_desc(alert_level):
    """Get right description with the alert"""

    t_alert_level = safe_float(alert_level)

    messages = {
        0: "🟦 Giornata serena.",
        1: "🟩 Nessuna preoccupazione.",
        2: "🟩 Giornata mite.",
        2.1: "🟩 Giornata mite. Il vento aumenta leggermente, possibile fino a 25kn.",
        2.2: "🟩 Giornata mite. Il vento aumenta, possibile fino a 30kn.",
        3: "🟨 Attenzione. Condizioni instabili, vento moderato, possibili groppi.",
        3.1: "🟨 Attenzione. Vento in aumento, possibile fino a 40kn, possibili groppi.",
        4: "🟧 Allerta! Venti forti, mare mosso, rischio tempesta in aumento.",
        4.1: "🟧 Allerta! Mare mosso, rischio tempesta, vento forte possibile fino a 50kn.",
        5: "🟥 Allarme! Forte tempesta, vento da burrasca, condizioni pericolose per la navigazione.",
        5.1: "🟥 Allarme! Forte tempesta, vento da burrasca possibile oltre 50kn.",
    }

    return messages.get(t_alert_level, "")
