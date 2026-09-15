# ExpensesHistory

A desktop expense and income tracker for personal finances, built with PyQt6 and
SQLAlchemy on top of a local SQLite database.

## Features

- Record receipts line by line, with per-item amount, price, discount and refund flags
- Per-product units (pcs / kg / l) with an optional package size, so prices compare per kg or litre
- Track income alongside expenses, in multiple currencies
- Edit or delete any saved transaction or income record
- Per-month dashboard: income, expenses, net balance, and breakdowns by store and category
- Price tracker: effective unit price history per product, per currency, with a chart
- Manage stores, their locations, and the product catalogue
- One-click database backup
- Fill a receipt from a photo using any AI chat app (Claude, Gemini, ...), then review and save

## Scanning a receipt with AI

1. On **New Transaction**, click **1. Copy Prompt**. The prompt includes your known
   stores, payment types and products, so the AI reuses your names.
2. In Claude, Gemini or another AI chat, attach the receipt photo (several photos for a
   long receipt), paste the prompt and send it.
3. Copy the whole reply, click **2. Paste AI Result** and then **Fill Form**.
4. Check the message under the items: it confirms the items add up to the receipt
   total, or shows the difference, and lists new products and anything the AI was
   unsure about. Nothing is saved until you press Save.

The app never contacts an AI service itself; it only reads the pasted JSON.

## Running

```
uv sync
uv run python main.py
```

## Building a Windows executable

```
uv run pyinstaller ExpenseTracker.spec
```

The result lands in `dist/ExpenseTracker.exe`. It reads and writes
`expense_tracker.db` next to the executable.

## Layout

```
main.py             entry point: logging, database init, main window
app_logging.py      rotating file log + excepthook so crashes are recorded
units.py            unit normalisation and price-per-kg/l maths
receipt_import.py   AI scan prompt and the parser for the pasted result
database/
  models.py         SQLAlchemy models
  engine.py         engine, session factory, seed data
repositories/       all database access, one module per area
ui/
  main_window.py    tab shell
  widgets.py        shared UI helpers
  views/            one module per tab
```

## Notes

- The database lives at `expense_tracker.db` in the project root (or next to the
  packaged executable) and is not tracked by git.
- There is no migration system. `init_db()` only creates missing tables. After
  changing a model, recreate a development database; for a database you want to
  keep, back it up and apply the additive `ALTER TABLE` by hand.
- Runtime errors are written to `logs/expense_tracker.log`.
