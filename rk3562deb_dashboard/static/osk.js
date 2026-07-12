// Dependency-free on-screen keyboard for the cog/WPEWebKit kiosk (which has
// no system OSK). Generic: createOSK(input, container, onSubmit) renders a
// 3-layer keyboard (lowercase / shift / symbols) that types into `input` and
// fires an "input" event per key so callers can stay input-driven.
//
// Deliberately not built: long-press accents, key preview popups, locales.

const LAYERS = {
  lower: [
    ["q", "w", "e", "r", "t", "y", "u", "i", "o", "p"],
    ["a", "s", "d", "f", "g", "h", "j", "k", "l"],
    ["⇧", "z", "x", "c", "v", "b", "n", "m", "del"],
    ["?123", " ", "✓"],
  ],
  upper: [
    ["Q", "W", "E", "R", "T", "Y", "U", "I", "O", "P"],
    ["A", "S", "D", "F", "G", "H", "J", "K", "L"],
    ["⇧", "Z", "X", "C", "V", "B", "N", "M", "del"],
    ["?123", " ", "✓"],
  ],
  symbols: [
    ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0"],
    ["!", "@", "#", "$", "%", "^", "&", "*", "(", ")"],
    ["-", "_", "=", "+", "[", "]", "{", "}", ";", ":"],
    ["abc", "'", '"', ",", ".", "<", ">", "/", "?", "del"],
    [" ", "✓"],
  ],
};

export function createOSK(input, container, onSubmit) {
  let layer = "lower";
  let capsLock = false;
  let lastShiftTap = 0;

  const root = document.createElement("div");
  root.className = "osk";

  function type(char) {
    input.value += char;
    input.dispatchEvent(new Event("input", { bubbles: true }));
    if (layer === "upper" && !capsLock) {
      layer = "lower";
      render();
    }
  }

  function backspace() {
    input.value = input.value.slice(0, -1);
    input.dispatchEvent(new Event("input", { bubbles: true }));
  }

  function handleKey(key) {
    if (key === "⇧") {
      const now = Date.now();
      capsLock = layer === "upper" ? false : now - lastShiftTap < 400;
      layer = layer === "upper" ? "lower" : "upper";
      lastShiftTap = now;
      render();
    } else if (key === "del") {
      backspace();
    } else if (key === "?123") {
      layer = "symbols";
      render();
    } else if (key === "abc") {
      layer = "lower";
      render();
    } else if (key === "✓") {
      if (onSubmit) onSubmit();
    } else {
      type(key);
    }
  }

  function render() {
    root.textContent = "";
    for (const row of LAYERS[layer]) {
      const rowEl = document.createElement("div");
      rowEl.className = "osk-row";
      for (const key of row) {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "osk-key";
        if (key === " ") {
          btn.classList.add("osk-space");
          btn.textContent = "space";
        } else {
          btn.textContent = key;
        }
        if (key === "✓") btn.classList.add("osk-submit");
        if (key === "⇧" && (layer === "upper" || capsLock)) btn.classList.add("osk-shift-on");
        if ("⇧✓".includes(key) || key === "del" || key === "?123" || key === "abc") {
          btn.classList.add("osk-mod");
        }
        // pointerdown (not click): immediate response and preventDefault
        // keeps the text input from losing focus to the button.
        btn.addEventListener("pointerdown", (event) => {
          event.preventDefault();
          handleKey(key === " " ? " " : key);
        });
        rowEl.appendChild(btn);
      }
      root.appendChild(rowEl);
    }
  }

  render();
  container.appendChild(root);
  return {
    destroy() {
      root.remove();
    },
  };
}
