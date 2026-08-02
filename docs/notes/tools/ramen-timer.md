---
icon: material/timer-sand
hide:
  - tags
---

# 🍜 泡面计时器

默认 **3 分钟**，也可以输入自定义时间（分钟 + 秒）。支持 **Start / Pause / Reset**，默认静音，可开启到时提示音。

______________________________________________________________________

<div class="rt-wrap">
  <div id="rt-display" class="rt-display">03:00</div>
  <div class="rt-set">
    <input id="rt-min" type="number" min="0" max="99" value="3" aria-label="分钟" />
    <span class="rt-sep">:</span>
    <input id="rt-sec" type="number" min="0" max="59" value="0" aria-label="秒" />
  </div>
  <div class="rt-controls">
    <button id="rt-start" type="button">▶ Start</button>
    <button id="rt-pause" type="button" disabled>⏸ Pause</button>
    <button id="rt-reset" type="button">↺ Reset</button>
  </div>
  <div class="rt-sound">
    <label>
      <input id="rt-mute" type="checkbox" checked />
      🔕 静音
    </label>
  </div>
  <div id="rt-status" class="rt-status" role="status" aria-live="polite"></div>
</div>

<script>
(function () {
  "use strict";

  var DEFAULT_SEC = 180;          // 3:00
  var configured = DEFAULT_SEC;   // last user-set time (or default)
  var remaining = DEFAULT_SEC;
  var running = false;
  var timerId = null;
  var endAt = 0;
  var audioCtx = null;
  var beepTimer = null;
  var blinkTimer = null;

  var display = document.getElementById("rt-display");
  var minInput = document.getElementById("rt-min");
  var secInput = document.getElementById("rt-sec");
  var btnStart = document.getElementById("rt-start");
  var btnPause = document.getElementById("rt-pause");
  var btnReset = document.getElementById("rt-reset");
  var muteEl = document.getElementById("rt-mute");
  var statusEl = document.getElementById("rt-status");

  function pad(n) { return (n < 10 ? "0" : "") + n; }

  function fmt(sec) {
    return pad(Math.floor(sec / 60)) + ":" + pad(sec % 60);
  }

  function readInput(rewrite) {
    var m = parseInt(minInput.value, 10);
    var s = parseInt(secInput.value, 10);
    if (isNaN(m)) m = 0;
    if (isNaN(s)) s = 0;
    var mRaw = m;
    var sRaw = s;
    if (m < 0) m = 0;
    if (s < 0) s = 0;
    if (s > 59) s = 59;
    if (m > 99) m = 99;
    // full normalization on blur/change; while typing only snap out-of-range
    // values so the box and display stay in sync without fighting keystrokes
    if (rewrite || m !== mRaw || s !== sRaw) {
      minInput.value = m;
      secInput.value = s;
    }
    return m * 60 + s;
  }

  function render() {
    display.textContent = fmt(remaining);
  }

  function stop() {
    if (timerId) { clearInterval(timerId); timerId = null; }
    if (beepTimer) { clearInterval(beepTimer); beepTimer = null; }
    running = false;
    updateButtons();
  }

  function finish() {
    stop();
    if (blinkTimer) { clearTimeout(blinkTimer); blinkTimer = null; }
    display.classList.add("rt-done");
    if (muteEl.checked) {
      statusEl.textContent = "⏰ 时间到!（🔇 静音）";
    } else if (audioCtx && audioCtx.state === "running") {
      statusEl.textContent = "⏰ 时间到! 🔔";
      beep();
    } else {
      statusEl.textContent = "⏰ 时间到!（🔕 无音频）";
    }
    blinkTimer = setTimeout(function () {
      display.classList.remove("rt-done");
      blinkTimer = null;
    }, 4000);
  }

  function tick() {
    var left = Math.ceil((endAt - Date.now()) / 1000);
    if (left <= 0) {
      remaining = 0;
      render();
      finish();
      return;
    }
    remaining = left;
    render();
  }

  // Create/unlock the AudioContext inside a user gesture (click) so the
  // beep is allowed by the browser autoplay policy. Reused across runs.
  function ensureAudio() {
    try {
      if (!audioCtx) {
        var AudioCtx = window.AudioContext || window.webkitAudioContext;
        if (!AudioCtx) return null;
        audioCtx = new AudioCtx();
      }
      if (audioCtx.state === "suspended") {
        var p = audioCtx.resume();
        if (p && p.catch) p.catch(function () {});
      }
      return audioCtx;
    } catch (e) {
      return null;
    }
  }

  function beep() {
    if (muteEl.checked) return;
    var ctx = audioCtx;
    if (!ctx) return;
    // cancel any pending beep so rapid finish/restart cycles don't overlap
    if (beepTimer) { clearInterval(beepTimer); beepTimer = null; }
    var count = 0;
    try {
      beepTimer = setInterval(function () {
        try {
          var osc = ctx.createOscillator();
          var gain = ctx.createGain();
          osc.connect(gain);
          gain.connect(ctx.destination);
          osc.frequency.value = 880;
          gain.gain.value = 0.15;
          osc.start();
          osc.stop(ctx.currentTime + 0.18);
          if (++count >= 3) { clearInterval(beepTimer); beepTimer = null; }
        } catch (e) {
          // audio unavailable: stop the cycle instead of leaking it
          clearInterval(beepTimer);
          beepTimer = null;
        }
      }, 350);
    } catch (e) { /* setInterval unavailable */ }
  }

  function updateButtons() {
    btnStart.disabled = running;
    btnPause.disabled = !running;
    minInput.disabled = running;
    secInput.disabled = running;
  }

  btnStart.addEventListener("click", function () {
    if (running) return;
    if (remaining <= 0) remaining = configured;
    if (!muteEl.checked) ensureAudio();   // unlock audio on user gesture
    if (blinkTimer) { clearTimeout(blinkTimer); blinkTimer = null; }
    if (beepTimer) { clearInterval(beepTimer); beepTimer = null; }   // cut residual completion beeps
    display.classList.remove("rt-done");
    statusEl.textContent = "▶ 计时中...";
    endAt = Date.now() + remaining * 1000;
    running = true;
    timerId = setInterval(tick, 250);
    updateButtons();
  });

  btnPause.addEventListener("click", function () {
    if (!running) return;
    stop();
    statusEl.textContent = "⏸ 已暂停";
  });

  btnReset.addEventListener("click", function () {
    stop();
    if (blinkTimer) { clearTimeout(blinkTimer); blinkTimer = null; }
    configured = readInput();
    if (configured <= 0) configured = DEFAULT_SEC;
    remaining = configured;
    minInput.value = Math.floor(configured / 60);
    secInput.value = configured % 60;
    display.classList.remove("rt-done");
    statusEl.textContent = "";
    render();
  });

  muteEl.addEventListener("change", function () {
    if (!muteEl.checked) ensureAudio();   // unmuting is also a user gesture
  });

  function onInputChange() {
    if (running) return;
    var v = readInput(false);
    if (v > 0) configured = v;
    remaining = v;
    display.classList.remove("rt-done");
    statusEl.textContent = "";
    render();
  }

  function onInputCommit() {
    if (running) return;
    readInput(true);   // normalize the fields on blur/Enter
    onInputChange();
  }

  function onKeydown(e) {
    if (e.key === "Enter" || e.key === "NumpadEnter") {
      e.preventDefault();
      btnStart.click();   // Enter in a time field starts the timer
    }
  }

  minInput.addEventListener("input", onInputChange);
  secInput.addEventListener("input", onInputChange);
  minInput.addEventListener("change", onInputCommit);
  secInput.addEventListener("change", onInputCommit);
  minInput.addEventListener("keydown", onKeydown);
  secInput.addEventListener("keydown", onKeydown);

  document.addEventListener("visibilitychange", function () {
    if (!document.hidden && running) tick();   // catch up after tab throttling
  });

  minInput.value = 3;
  secInput.value = 0;
  remaining = DEFAULT_SEC;
  configured = DEFAULT_SEC;
  render();
  updateButtons();
})();
</script>

______________________________________________________________________

## 📝 使用说明

| 操作        | 说明                                               |
| ----------- | -------------------------------------------------- |
| **Start**   | 开始倒计时，计时中可随时 **Pause** 暂停            |
| **Pause**   | 暂停计时，再次 **Start** 继续                      |
| **Reset**   | 重置为输入的时间（留空则回到默认 3 分钟）          |
| 自定义时间  | 修改「分钟 / 秒」输入框即可，例如 `1 : 30` = 90 秒 |
| **🔕 静音** | 默认勾选（静音）；取消勾选后倒计时结束播放提示音   |
| 快捷键      | 在「分钟 / 秒」输入框内按 **Enter** 直接开始计时   |

## 🔔 到时提醒说明

- 倒计时归零时：时间显示 **00:00** 闪烁，状态栏提示 **⏰ 时间到!**
- **默认静音**：不播放任何声音（勾选「🔕 静音」）
- 取消静音后：播放 3 声 880Hz 提示音，持续约 1 秒
- 提示音基于 Web Audio（`AudioContext`）实现；浏览器首次允许音频发生在点击 **Start**（或取消静音）时，无需额外授权弹窗

> 提示：如果浏览器拒绝了音频播放（如 Chrome 的自动播放策略）或设备没有音频输出，状态栏会显示「🔕 无音频」，但屏幕闪烁提醒始终有效。
