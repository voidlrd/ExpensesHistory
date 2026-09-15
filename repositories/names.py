import unicodedata

def fold_text(text):
    """Casefold and drop accents, so 'paine' matches 'Pâine'."""
    decomposed = unicodedata.normalize("NFKD", text or "")
    return "".join(c for c in decomposed if not unicodedata.combining(c)).casefold()

def find_by_name(rows, name, attr="name"):
    """First row whose attr equals name, ignoring case; None for an empty name."""
    if not name:
        return None
    folded = name.casefold()
    return next((row for row in rows if (getattr(row, attr) or "").casefold() == folded), None)
