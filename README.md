# ExpensesHistory

A desktop expense and income tracker for personal finances, built with PyQt6 and
SQLAlchemy on top of a local SQLite database.

## Features

- Record receipts line by line, with per-item amount, price, discount and refund flags
- Per-product units (pcs / kg / l) with an optional package size, so prices compare per kg or litre
- Track income alongside expenses, in multiple currencies, with a duplicate warning and the last few records in view
- Edit or delete any saved transaction or income record
- History: period presets, live filters, search by store, receipt ID or product, and totals for what's shown
- Dashboard: show a month, 3 or 6 months, or a year (the current year runs up to this month), step through periods, compare income and expenses with the period before, see the last 12 months with the shown period highlighted, and open any store or category to see what you bought
- Brands per product: "Lapte" keeps its own list of brands the way a store keeps locations, so names stay clean. A brand is optional on every purchase, blank when you don't know it, and renaming one fixes every past purchase
- Price tracker: searchable product list, effective unit price history per currency with a chart, a brand filter, and the average price per store and per brand
- Stores & People tab: search, see receipts, spending and income per store, merge duplicates, rename locations, hide or delete
- Products tab: search and filter by category, brand and unit; manage each product's brands; set categories in bulk, hide, merge duplicates, and delete products that were never bought
- Backups tab: every backup listed, one-click backup and restore, plus an automatic backup at startup (the 5 most recent are kept)
- Fill a receipt from a photo, or an online order from a screenshot, email or invoice, using any AI chat app (Claude, Gemini, ...), with category suggestions for new products, then review and save
- Warns when a receipt with the same ID UNIC was already saved

## Filling a receipt or online order with AI

1. On **New Transaction**, click **1. Copy Prompt**. The prompt includes your known
   stores, payment types and products, so the AI reuses your names.
2. In Claude, Gemini or another AI chat, attach the receipt photo (several photos for a
   long receipt), or for an online order a screenshot, the confirmation email or the
   invoice. Paste the prompt; it ends with a line for extra details, so type anything
   the attachment doesn't show (the amount your bank charged, the payment type, what an
   item is) and send it. For something like a subscription you can skip the attachment
   and write the details alone.
3. Copy the whole reply, click **2. Paste AI Result** and then **Fill Form**.
4. Check the message under the items: it confirms the items add up to the receipt
   total, or shows the difference, and lists new products and anything the AI was
   unsure about. Nothing is saved until you press Save.

The scan also reads the brand off each line when the receipt prints one, and leaves
it blank otherwise. For online orders it uses the order number as the receipt ID,
names subscriptions without dates so every renewal lands on the same product, and
keeps shipping and fees as their own lines.

The app never contacts an AI service itself; it only reads the pasted JSON.

## Running

```
uv sync
uv run python main.py
```

## Running the tests

```
uv run pytest
```

The tests use a throwaway database and never touch yours.

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
tests/              pytest suite (money, units, scanning, repositories, backups)
```

## Notes

- The database lives at `expense_tracker.db` in the project root (or next to the
  packaged executable) and is not tracked by git. Set `EXPENSES_DB` to work against
  another file, such as a copy of the real one.
- Restoring a backup writes a `before_restore_...` copy first, so a restore can be undone.
- There is no migration system. `init_db()` only creates missing tables. After
  changing a model, recreate a development database; for a database you want to
  keep, back it up and apply the additive `ALTER TABLE` by hand.
- Runtime errors are written to `logs/expense_tracker.log`.
