PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Send receipts</title>
<style>
  :root { color-scheme: light dark; --blue: #2196F3; --green: #4CAF50; --red: #F44336; }
  body { font: 17px/1.4 system-ui, sans-serif; margin: 0; padding: 20px 16px 40px; max-width: 480px; margin-inline: auto; }
  h1 { font-size: 22px; margin: 0 0 6px; }
  p.hint { margin: 0 0 14px; opacity: .75; }
  button, label.button { display: block; width: 100%; box-sizing: border-box; padding: 16px; margin: 10px 0;
    border: 0; border-radius: 12px; font: 600 18px system-ui, sans-serif; text-align: center; cursor: pointer; }
  .primary { background: var(--blue); color: white; }
  .send { background: var(--green); color: white; }
  button.plain, label.button.plain { background: transparent; color: inherit; border: 1px solid #8888;
    font-weight: 400; padding: 12px; }
  button:disabled, label.disabled { opacity: .5; pointer-events: none; }
  .receipt { border: 1px solid #8886; border-radius: 12px; padding: 10px; margin: 10px 0; }
  .receipt.current { border: 2px solid var(--blue); }
  .receipt header { display: flex; justify-content: space-between; align-items: center; font-weight: 600; }
  .receipt header button { width: auto; margin: 0; padding: 4px 12px; background: transparent; color: inherit;
    border: 1px solid #8888; font-weight: 400; font-size: 15px; }
  .parts { display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px; margin-top: 8px; }
  .parts figure { margin: 0; position: relative; }
  .parts img { width: 100%; aspect-ratio: 3 / 4; object-fit: cover; border-radius: 6px; display: block; }
  .parts figcaption { position: absolute; top: 3px; left: 3px; background: #000a; color: white;
    border-radius: 5px; padding: 0 5px; font-size: 13px; }
  #status { margin-top: 14px; font-weight: 600; min-height: 1.4em; }
  .ok { color: var(--green); } .error { color: var(--red); }
  [hidden] { display: none !important; }
</style>
</head>
<body>
<h1>Send receipts</h1>
<p class="hint">Photograph each receipt; for a long one, add parts from top to bottom that overlap a little.
Press <b>Next receipt</b> before the next one, then send them all at once.</p>

<div id="receipts"></div>
<label class="button primary" id="take" for="camera">Take photo</label>
<input id="camera" type="file" accept="image/*" capture="environment" hidden>
<button class="plain" id="next" hidden>Next receipt</button>
<button class="send" id="send" hidden>Send all</button>
<label class="button plain" id="pick" for="gallery">Choose from gallery or screenshots</label>
<input id="gallery" type="file" accept="image/*" multiple hidden>
<button class="plain" id="restart" hidden>Start over</button>
<div id="status"></div>

<script>
// receipts[i] is the list of photos of one receipt; the last one is the receipt being photographed
let receipts = [[]];
let sending = false;
const $ = id => document.getElementById(id);
const plural = (n, word) => `${n} ${word}${n === 1 ? "" : "s"}`;
const filled = () => receipts.filter(parts => parts.length);

// kept in the browser too, so a page reload while the camera is open loses nothing
const store = {
  open() {
    return this.db ??= new Promise((resolve, reject) => {
      const request = indexedDB.open("send-receipts", 1);
      request.onupgradeneeded = () => request.result.createObjectStore("batch");
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
  },
  async run(mode, action) {
    const db = await this.open();
    return new Promise((resolve, reject) => {
      const request = action(db.transaction("batch", mode).objectStore("batch"));
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
  },
};

async function save() {
  try { await store.run("readwrite", batch => batch.put(receipts, "receipts")); } catch (e) { /* memory only */ }
}

async function restore() {
  try {
    const saved = await store.run("readonly", batch => batch.get("receipts"));
    if (Array.isArray(saved) && saved.some(parts => parts.length)) receipts = saved;
  } catch (e) { /* memory only */ }
  render();
}

function say(text, kind) {
  $("status").textContent = text;
  $("status").className = kind || "";
}

function render() {
  const current = receipts.length - 1;
  $("receipts").replaceChildren(...receipts.flatMap((parts, i) => {
    if (!parts.length) return [];
    const card = document.createElement("section");
    card.className = "receipt" + (i === current ? " current" : "");
    const header = document.createElement("header");
    const title = document.createElement("span");
    title.textContent = `Receipt ${i + 1} · ${plural(parts.length, "photo")}`;
    const remove = document.createElement("button");
    remove.textContent = "Remove";
    remove.disabled = sending;
    remove.addEventListener("click", () => removeReceipt(i));
    header.append(title, remove);
    const grid = document.createElement("div");
    grid.className = "parts";
    grid.append(...parts.map((file, p) => {
      const figure = document.createElement("figure");
      const img = document.createElement("img");
      img.src = URL.createObjectURL(file);
      img.onload = () => URL.revokeObjectURL(img.src);
      const caption = document.createElement("figcaption");
      caption.textContent = p + 1;
      figure.append(img, caption);
      return figure;
    }));
    card.append(header, grid);
    return [card];
  }));

  const building = receipts[current].length;
  const count = filled().length;
  $("take").textContent = building ? `Add a part to receipt ${current + 1}` : (count ? `Take photo of receipt ${current + 1}` : "Take photo");
  $("next").hidden = !building;
  $("send").hidden = $("restart").hidden = !count;
  $("send").textContent = `Send all (${plural(count, "receipt")})`;
  for (const id of ["next", "send", "restart"]) $(id).disabled = sending;
  for (const id of ["take", "pick"]) $(id).classList.toggle("disabled", sending);
}

function addFiles(files) {
  receipts[receipts.length - 1].push(...files);
  say("");
  render();
  save();
}

function nextReceipt() {
  if (receipts[receipts.length - 1].length) receipts.push([]);
  render();
  save();
}

function removeReceipt(index) {
  if (!confirm(`Remove receipt ${index + 1} and its photos?`)) return;
  receipts.splice(index, 1);
  if (!receipts.length || receipts[receipts.length - 1].length) receipts.push([]);
  render();
  save();
}

async function upload(parts) {
  // each photo goes as a 4-byte length followed by its bytes
  const pieces = [];
  for (const file of parts) {
    const size = new Uint8Array(4);
    new DataView(size.buffer).setUint32(0, file.size);
    pieces.push(size, file);
  }
  let response;
  try {
    response = await fetch(location.pathname.replace(/\\/$/, "") + "/receipt", {
      method: "POST", headers: { "Content-Type": "application/octet-stream" }, body: new Blob(pieces),
    });
  } catch (e) {
    throw new Error("Couldn't reach your computer. Is the app open, and is this phone on the same Wi-Fi?");
  }
  const answer = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(answer.error || `The computer answered with error ${response.status}.`);
}

async function sendAll() {
  const total = filled().length;
  let sent = 0;
  sending = true;
  render();
  try {
    for (let index = receipts.findIndex(parts => parts.length); index !== -1;
         index = receipts.findIndex(parts => parts.length)) {
      say(`Sending receipt ${sent + 1} of ${total}…`);
      try {
        await upload(receipts[index]);
      } catch (error) {
        throw new Error(`Receipt ${index + 1}: ${error.message}`);
      }
      receipts.splice(index, 1);
      sent++;
      render();
      await save();
    }
    receipts = [[]];
    say(`✓ Sent ${plural(sent, "receipt")}. They're waiting in the Inbox on your computer.`, "ok");
  } catch (error) {
    const done = sent ? `Sent ${sent} of ${total}. ` : "";
    say(`${done}${error.message} The rest are kept here: press Send all to try again.`, "error");
  } finally {
    sending = false;
    // new photos start a new receipt rather than join one waiting to be resent
    if (!receipts.length || receipts[receipts.length - 1].length) receipts.push([]);
    render();
    await save();
  }
}

function startOver() {
  if (!confirm(`Remove all ${plural(filled().length, "receipt")} without sending?`)) return;
  receipts = [[]];
  say("");
  render();
  save();
}

$("camera").addEventListener("change", event => { addFiles(event.target.files); event.target.value = ""; });
$("gallery").addEventListener("change", event => { addFiles(event.target.files); event.target.value = ""; });
$("next").addEventListener("click", nextReceipt);
$("send").addEventListener("click", sendAll);
$("restart").addEventListener("click", startOver);
restore();
</script>
</body>
</html>
"""
