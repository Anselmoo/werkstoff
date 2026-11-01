// The palette lives in JS on purpose: a canvas cannot read CSS custom properties,
// so `ctx.fillStyle = "var(--accent)"` would silently paint black.
const PALETTE = { bar: "#1874c2", barDark: "#73b6fa", axis: "#8b9aa4" };
const DATA = [62, 66, 71, 74, 79, 84];
const LABELS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun"];

function draw() {
  const canvas = document.getElementById("revenue");
  const ctx = canvas.getContext("2d");
  const dark = window.matchMedia("(prefers-color-scheme: dark)").matches;
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  const w = canvas.width / DATA.length;
  DATA.forEach((v, i) => {
    const h = (v / 100) * (canvas.height - 30);
    ctx.fillStyle = dark ? PALETTE.barDark : PALETTE.bar;
    ctx.fillRect(i * w + 10, canvas.height - 20 - h, w - 20, h);
    ctx.fillStyle = PALETTE.axis;
    ctx.fillText(LABELS[i], i * w + w / 2 - 8, canvas.height - 6);
  });
}
draw();
