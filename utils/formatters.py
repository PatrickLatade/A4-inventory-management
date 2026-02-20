from datetime import datetime


def format_date(dt_str, show_time=False):
    """
    Converts a database datetime string to a human-readable format.

    Default (show_time=False): "Feb 05, 2025"
    With time  (show_time=True): "Feb 05, 2025 02:30 PM"

    Returns '-' if the value is None or empty.
    Safe to use across any service or route in the project.
    """
    if not dt_str or str(dt_str).strip() == '':
        return "-"
    try:
        dt = datetime.strptime(str(dt_str)[:19], "%Y-%m-%d %H:%M:%S")
    except ValueError:
        try:
            dt = datetime.strptime(str(dt_str)[:10], "%Y-%m-%d")
        except ValueError:
            return str(dt_str)  # fallback if format is unexpected
    if show_time:
        return dt.strftime("%b %d, %Y %I:%M %p")
    return dt.strftime("%b %d, %Y")
    
def norm_text(s: str) -> str:
    # trims + collapses internal whitespace
    return " ".join((s or "").strip().split())