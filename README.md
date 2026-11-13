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
- Fill a receipt from a photo, or an online order from a screenshot, email or invoice: automatically with your own Claude or Gemini API key, or by hand through any AI chat app. New products get category suggestions; you review everything before saving
- Send receipt photos from your phone over your Wi-Fi: a page opened by a QR code, no app to install. They wait in an inbox until you scan them
- Warns when a receipt with the same ID UNIC was already saved

## Reading receipts with AI automatically

1. Get an API key from [Anthropic](https://platform.claude.com/settings/keys) (Claude) or
   [Google AI Studio](https://aistudio.google.com/apikey) (Gemini). Each receipt costs a few
   cents, billed by them.
2. In **Data Manager → AI & Phone**, pick the provider, paste the key and click **Save Key**.
   It is tested straight away. The first model in the list is a good default (Claude
   Sonnet, Gemini Hydrogen).
3. On **New Transaction**, click **Scan with AI…** and pick the photos or screenshots of one
   receipt. Type anything the pictures don't show in the box next to it, such as the amount
   your bank charged.
4. The form fills in and the message under the items says whether they add up to the
   receipt total. Check it and press Save.

The key is kept in Windows Credential Manager (as "ExpensesHistory AI"), never in the
database or its backups. Photos are sent at the full resolution the model can read; a long
receipt is cut into overlapping strips so its small print stays legible. When a reading
goes wrong, the AI's answer is written to the log file.

## Sending receipts from your phone

1. In **Data Manager → AI & Phone**, tick **Receive receipts from my phone**. A QR code and
   an address appear.
2. The first time, Windows Firewall asks whether to allow the app: allow it on **private
   networks**, and make sure your Wi-Fi is set as a private network in Windows.
3. Scan the code with the phone's camera and bookmark the page. The phone must be on the
   same Wi-Fi.
4. On the page, take the photo (or several parts of a long receipt, top to bottom), or pick
   screenshots from the gallery, and press **Send**.
5. On **New Transaction**, **Inbox** shows how many receipts are waiting. Open it, pick one
   and scan it. It leaves the inbox once you save its transaction.

Receiving starts again by itself when the app opens. The address carries a secret part;
**New Link** replaces it if it was shared by mistake. If the phone can't connect, check the
firewall and the Wi-Fi network type, or try another port in the same tab. HEIC photos
can't be read: turn off "high efficiency" pictures in the camera settings.

## Filling a receipt or online order with any AI chat

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

This way needs no API key: the app only reads the pasted JSON.

## Running

```
uv sync
uv run python main.py
```

## Running the tests

```
uv run pytest
```

The tests use a throwaway database, settings, inbox and in-memory key store, never touch
yours, and never call the real Claude or Gemini APIs.

## Building a Windows executable

```
uv run pyinstaller ExpenseTracker.spec
```

The result lands in `dist/ExpenseTracker.exe`. It reads and writes
`expense_tracker.db` next to the executable, with `backups/`, `inbox/` and `logs/` beside it.
The spec also bundles the package metadata that the Claude and Gemini clients' HTTP
library reads at startup.

## Layout

```
main.py             entry point: logging, database init, main window
app_logging.py      rotating file log + excepthook so crashes are recorded
app_settings.py     remembered settings, API keys in Windows Credential Manager
units.py            unit normalisation and price-per-kg/l maths
receipt_import.py   AI scan prompt and the parser for the AI's JSON answer
receipt_images.py   photos turned upright and cut into full-resolution strips
receipt_ai.py       Claude and Gemini clients, with plain-language errors
receipt_inbox.py    receipts waiting to be read, one folder of photos each
phone_server.py     the phone page's server (phone_page.py holds the page)
database/
  models.py         SQLAlchemy models
  engine.py         engine, session factory, seed data
repositories/       all database access, one module per area
ui/
  main_window.py    tab shell; owns the phone page server
  phone_link.py     starts and stops the phone page, signals new receipts
  widgets.py        shared UI helpers
  views/            one module per tab or panel
tests/              pytest suite (money, units, scanning, AI, inbox, phone, repositories, backups)
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
