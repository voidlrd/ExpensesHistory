# ExpensesHistory

A desktop expense and income tracker for personal finances, built with PyQt6 and
SQLAlchemy on top of a local SQLite database.

## Features

- Record receipts line by line, with per-item amount, price, discount and refund flags
- Track income alongside expenses, in multiple currencies
- Edit or delete any saved transaction or income record
- Per-month dashboard: income, expenses, net balance, and breakdowns by store and category
- Price tracker: effective unit price history per product, per currency, with a chart
- Manage stores, their locations, and the product catalogue
- One-click database backup

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
- There is no migration system. `init_db()` only creates missing tables, so after
  changing a model, delete `expense_tracker.db` and let it be recreated.
- Runtime errors are written to `logs/expense_tracker.log`.
