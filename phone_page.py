PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Send a receipt</title>
<style>
  :root { color-scheme: light dark; --blue: #2196F3; --green: #4CAF50; --red: #F44336; }
  body { font: 17px/1.4 system-ui, sans-serif; margin: 0; padding: 20px 16px 40px; max-width: 480px; margin-inline: auto; }
  h1 { font-size: 22px; margin: 0 0 6px; }
  p.hint { margin: 0 0 18px; opacity: .75; }
  button, label.button { display: block; width: 100%; box-sizing: border-box; padding: 16px; margin: 10px 0;
    border: 0; border-radius: 12px; font: 600 18px system-ui, sans-serif; text-align: center; cursor: pointer; }
  .primary { background: var(--blue); color: white; }
  .send { background: var(--green); color: white; }
  .plain { background: transparent; color: inherit; border: 1px solid #8888; font-weight: 400; padding: 12px; }
  button:disabled { opacity: .5; }
  #parts { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin: 14px 0; }
  #parts figure { margin: 0; position: relative; }
  #parts img { width: 100%; aspect-ratio: 3 / 4; object-fit: cover; border-radius: 8px; display: block; }
  #parts figcaption { position: absolute; top: 4px; left: 4px; background: #000a; color: white;
    border-radius: 6px; padding: 0 6px; font-size: 14px; }
  #status { margin-top: 14px; font-weight: 600; min-height: 1.4em; }
  .ok { color: var(--green); } .error { color: var(--red); }
  [hidden] { display: none !important; }
</style>
</head>
<body>
<h1>Send a receipt</h1>
<p class="hint">Photograph the whole receipt. For a long one, take several parts from top to bottom that overlap a little.</p>

<label class="button primary" id="take" for="camera">Take photo</label>
<input id="camera" type="file" accept="image/*" capture="environment" hidden>
<div id="parts"></div>
<button class="send" id="send" hidden>Send</button>
<button class="plain" id="restart" hidden>Start over</button>
<label class="button plain" for="gallery">Choose from gallery or screenshots</label>
<input id="gallery" type="file" accept="image/*" multiple hidden>
<div id="status"></div>

<script>
const parts = [];
const $ = id => document.getElementById(id);

function say(text, kind) {
  $("status").textContent = text;
  $("status").className = kind || "";
}

function render() {
  $("parts").replaceChildren(...parts.map((file, i) => {
    const figure = document.createElement("figure");
    const img = document.createElement("img");
    img.src = URL.createObjectURL(file);
    const caption = document.createElement("figcaption");
    caption.textContent = i + 1;
    figure.append(img, caption);
    return figure;
  }));
  $("take").textContent = parts.length ? "Add another part" : "Take photo";
  $("send").textContent = `Send (${parts.length} photo${parts.length === 1 ? "" : "s"})`;
  $("send").hidden = $("restart").hidden = !parts.length;
}

function add(event) {
  parts.push(...event.target.files);
  event.target.value = "";
  say("");
  render();
}

$("camera").addEventListener("change", add);
$("gallery").addEventListener("change", add);
$("restart").addEventListener("click", () => { parts.length = 0; say(""); render(); });

$("send").addEventListener("click", async () => {
  // each photo goes as a 4-byte length followed by its bytes
  const pieces = [];
  for (const file of parts) {
    const size = new Uint8Array(4);
    new DataView(size.buffer).setUint32(0, file.size);
    pieces.push(size, file);
  }
  $("send").disabled = true;
  say("Sending…");
  try {
    const response = await fetch(location.pathname.replace(/\\/$/, "") + "/receipt", {
      method: "POST", headers: { "Content-Type": "application/octet-stream" }, body: new Blob(pieces),
    });
    const answer = await response.json();
    if (!response.ok) throw new Error(answer.error);
    const count = parts.length;
    parts.length = 0;
    render();
    say(`✓ Sent ${count} photo${count === 1 ? "" : "s"}. It's waiting in the Inbox on your computer.`, "ok");
  } catch (error) {
    say(error.message && !(error instanceof TypeError) ? error.message
        : "Couldn't reach your computer. Is the app open, and is this phone on the same Wi-Fi?", "error");
  } finally {
    $("send").disabled = false;
  }
});
</script>
</body>
</html>
"""
