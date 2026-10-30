function parseRow(i) { let s = 0; for (let k = 0; k < 20000; k++) s += (i * k) % 7; return s; }
function load() { let t = 0; for (let i = 0; i < 400; i++) t += parseRow(i); return t; }
console.log(load());
