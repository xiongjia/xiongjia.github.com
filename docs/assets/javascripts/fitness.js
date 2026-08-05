/**
 * fitness.js — 健身计数工具
 *
 * 轻量每日训练计数：今日概览（总组数/总次数/大卡）、每日目标进度条、
 * 动作录入（MET 法估算卡路里）、记录列表（删除/清空）、localStorage 持久化、
 * 跨天自动重置。渲染全部由 state 驱动，事件委托处理交互。
 */
(function () {
  'use strict';

  var STORAGE_KEY = 'fitness_counter_v1';

  // 动作预设：emoji + MET 系数 + 单次耗时估算（秒）。平板支撑 reps 即秒数。
  var EXERCISES = {
    dumbbell: { name: '举哑铃', emoji: '🏋️', met: 5, secondsPerRep: 4 },
    situp: { name: '仰卧起坐', emoji: '🧘', met: 4, secondsPerRep: 3 },
    pushup: { name: '俯卧撑', emoji: '💪', met: 6, secondsPerRep: 3 },
    squat: { name: '深蹲', emoji: '🦵', met: 6, secondsPerRep: 3 },
    plank: { name: '平板支撑', emoji: '🧎', met: 3, secondsPerRep: 1 }
  };

  var LIMITS = { sets: [1, 50], reps: [1, 999], weight: [30, 200], goal: [1, 100] };

  // Material 风格内联 SVG 图标（跟随 currentColor）
  var ICONS = {
    settings:
      '<svg class="fitness-icon" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M19.43,12.98c0.04,-0.32 0.07,-0.64 0.07,-0.98s-0.03,-0.66 -0.07,-0.98l2.11,-1.65c0.19,-0.15 0.24,-0.42 0.12,-0.64l-2,-3.46c-0.12,-0.22 -0.37,-0.31 -0.6,-0.22l-2.49,1c-0.52,-0.4 -1.08,-0.73 -1.69,-0.98l-0.38,-2.65C14.46,2.18 14.25,2 14,2h-4c-0.25,0 -0.46,0.18 -0.5,0.42l-0.38,2.65c-0.61,0.25 -1.17,0.59 -1.69,0.98l-2.49,-1c-0.23,-0.08 -0.48,0 -0.6,0.22l-2,3.46c-0.13,0.22 -0.07,0.49 0.12,0.64l2.11,1.65c-0.04,0.32 -0.07,0.66 -0.07,0.98s0.03,0.66 0.07,0.98l-2.11,1.65c-0.19,0.15 -0.24,0.42 -0.12,0.64l2,3.46c0.12,0.22 0.37,0.31 0.6,0.22l2.49,-1c0.52,0.4 1.08,0.73 1.69,0.98l0.38,2.65c0.04,0.24 0.25,0.42 0.5,0.42h4c0.25,0 0.46,-0.18 0.5,-0.42l0.38,-2.65c0.61,-0.25 1.17,-0.59 1.69,-0.98l2.49,1c0.23,0.08 0.48,0 0.6,-0.22l2,-3.46c0.12,-0.22 0.07,-0.49 -0.12,-0.64l-2.11,-1.65zM12,15.5c-1.93,0 -3.5,-1.57 -3.5,-3.5s1.57,-3.5 3.5,-3.5 3.5,1.57 3.5,3.5 -1.57,3.5 -3.5,3.5z"/></svg>',
    reset:
      '<svg class="fitness-icon" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M12,5V2L21,12l-9,10v-3c-5.52,0-10-4.48-10-10c0-2.05,0.68-3.93,1.82-5.44l1.46,1.46C4.49,7.66,4,9.75,4,12c0,4.41,3.59,8,8,8v-3c-2.76,0-5-2.24-5-5s2.24-5,5-5z"/></svg>'
  };

  var state = loadState();
  var app = null;
  var clearCtrl = { armed: false, timer: null };
  var resetCtrl = { armed: false, timer: null };
  var saveTimer = null;

  // 记录 id：UUID 保证跨标签页/跨会话唯一。
  // 注意不能用 `Date.now() * 10000 + seq`——乘 10000 后超出
  // Number.MAX_SAFE_INTEGER，+seq 会被浮点舍入吞掉，id 可能碰撞。
  var recordSeq = 0;
  function nextRecordId() {
    if (window.crypto && typeof window.crypto.randomUUID === 'function') {
      return window.crypto.randomUUID();
    }
    // 降级（旧浏览器/非 secure context）：时间戳 + 序列 + 随机数，多标签页也基本唯一
    recordSeq += 1;
    return String(Date.now()) + '-' + recordSeq + '-' + Math.floor(Math.random() * 1e6);
  }

  /* ── 存储 ─────────────────────────────────────────── */

  function todayStr() {
    var d = new Date();
    var m = String(d.getMonth() + 1).padStart(2, '0');
    var day = String(d.getDate()).padStart(2, '0');
    return d.getFullYear() + '-' + m + '-' + day;
  }

  function nowTime() {
    return new Date().toTimeString().slice(0, 5);
  }

  function loadState() {
    var stored = null;
    try {
      stored = JSON.parse(localStorage.getItem(STORAGE_KEY));
    } catch (e) {
      stored = null;
    }
    var s = {
      records: stored && Array.isArray(stored.records) ? stored.records : [],
      dailyGoal:
        stored && typeof stored.dailyGoal === 'number' && isFinite(stored.dailyGoal)
          ? stored.dailyGoal
          : 5,
      userWeight:
        stored && typeof stored.userWeight === 'number' && isFinite(stored.userWeight)
          ? stored.userWeight
          : 70,
      lastDate: stored ? stored.lastDate : null,
      draft: { exercise: 'dumbbell', sets: 3, reps: 12 },
      showGoalModal: false
    };
    return s;
  }

  function saveState() {
    try {
      localStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({
          records: state.records,
          dailyGoal: state.dailyGoal,
          userWeight: state.userWeight,
          lastDate: state.lastDate
        })
      );
    } catch (e) {
      // 隐私模式/配额等写入失败时静默降级为仅本次会话
    }
  }

  function debouncedSave() {
    clearTimeout(saveTimer);
    saveTimer = setTimeout(saveState, 300);
  }

  /* ── 计算 ─────────────────────────────────────────── */

  // 消耗大卡 = MET × 体重(kg) × 时长(小时)；时长 = 组×次×单次秒数 / 3600
  function calcKcal(exercise, sets, reps, weight) {
    var e = EXERCISES[exercise];
    if (!e) return 0;
    var hours = (sets * reps * e.secondsPerRep) / 3600;
    return Math.round(e.met * weight * hours);
  }

  function summary() {
    var s = { sets: 0, reps: 0, kcal: 0 };
    state.records.forEach(function (r) {
      // Number() 防御：localStorage 可能被外部篡改为非数字，避免字符串拼接
      var sets = Number(r.sets) || 0;
      var reps = Number(r.reps) || 0;
      s.sets += sets;
      s.reps += sets * reps;
      s.kcal += Number(r.kcal) || 0;
    });
    return s;
  }

  function clamp(n, lim) {
    return Math.min(lim[1], Math.max(lim[0], n));
  }

  // HTML 转义：所有动态插值统一转义，防 localStorage 篡改/未来用户输入注入
  function esc(s) {
    return String(s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  /* ── 渲染 ─────────────────────────────────────────── */

  function render() {
    var sum = summary();
    var done = sum.sets >= state.dailyGoal;
    var pct = Math.min(100, Math.round((sum.sets / state.dailyGoal) * 100));

    var chips = Object.keys(EXERCISES)
      .map(function (k) {
        return (
          '<button type="button" role="tab" class="fitness-tab' +
          (state.draft.exercise === k ? ' is-active' : '') +
          '" data-action="select-exercise" data-exercise="' +
          k +
          '" aria-selected="' +
          (state.draft.exercise === k ? 'true' : 'false') +
          '">' +
          '<span class="fitness-tab-emoji">' +
          esc(EXERCISES[k].emoji) +
          '</span>' +
          '<span class="fitness-tab-name">' +
          esc(EXERCISES[k].name) +
          '</span>' +
          '</button>'
        );
      })
      .join('');

    var recordsHtml;
    if (state.records.length === 0) {
      recordsHtml = '<div class="fitness-empty">还没有记录，添加第一条吧 💪</div>';
    } else {
      recordsHtml =
        '<div class="fitness-records">' +
        state.records
          .map(function (r) {
            return (
              '<div class="fitness-record">' +
              '<div class="fitness-record-main">' +
              '<span class="fitness-record-name">' +
              (EXERCISES[r.exercise] ? esc(EXERCISES[r.exercise].emoji) + ' ' : '') +
              esc(r.name) +
              '</span>' +
              '<span class="fitness-record-meta">' +
              esc(r.time) +
              ' · ' +
              esc(r.sets) +
              ' 组 × ' +
              esc(r.reps) +
              '</span>' +
              '</div>' +
              '<span class="fitness-record-kcal">' +
              esc(r.kcal) +
              ' 大卡</span>' +
              '<button type="button" class="fitness-record-delete" data-action="delete" data-id="' +
              r.id +
              '" aria-label="删除记录">✕</button>' +
              '</div>'
            );
          })
          .join('') +
        '</div>';
    }

    app.innerHTML =
      '<div class="fitness-overview">' +
      '<div class="fitness-card"><div class="fitness-card-label">总组数</div>' +
      '<div class="fitness-card-value">' +
      esc(sum.sets) +
      '</div></div>' +
      '<div class="fitness-card"><div class="fitness-card-label">总次数</div>' +
      '<div class="fitness-card-value">' +
      esc(sum.reps) +
      '</div></div>' +
      '<div class="fitness-card fitness-card-accent"><div class="fitness-card-label">大卡</div>' +
      '<div class="fitness-card-value">' +
      esc(sum.kcal) +
      '<span class="fitness-unit">kcal</span></div></div>' +
      '</div>' +

      '<button type="button" class="fitness-reset" data-action="reset">' +
      ICONS.reset +
      (resetCtrl.armed ? '确认重置？' : '重置今日') +
      '</button>' +

      '<section class="fitness-goal" aria-label="每日目标">' +
      '<div class="fitness-section-head">' +
      '<h2>每日目标</h2>' +
      '<button type="button" class="fitness-goal-set" data-action="open-goal">' +
      ICONS.settings +
      '设置</button>' +
      '</div>' +
      '<div class="fitness-progress" role="progressbar" aria-valuemin="0" aria-valuemax="' +
      esc(state.dailyGoal) +
      '" aria-valuenow="' +
      esc(sum.sets) +
      '"><div class="fitness-progress-fill' +
      (done ? ' is-done' : '') +
      '" style="width:' +
      pct +
      '%"></div></div>' +
      '<div class="fitness-progress-stats' +
      (done ? ' is-done' : '') +
      '">' +
      (done ? '🎉 今日目标已达成！' : esc(sum.sets) + ' / ' + esc(state.dailyGoal) + ' 组') +
      '</div>' +
      '</section>' +

      '<section class="fitness-entry" aria-label="记录动作">' +
      '<div class="fitness-section-head"><h2>记录动作</h2></div>' +
      '<div class="fitness-tabs" role="tablist" aria-label="选择动作">' +
      chips +
      '</div>' +
      '<div class="fitness-field">' +
      '<span class="fitness-field-label">组数</span>' +
      '<span class="fitness-stepper">' +
      stepper('sets', '组数减一', '−', -1) +
      inputField('sets', state.draft.sets, '组数') +
      stepper('sets', '组数加一', '+', 1) +
      '<span class="fitness-step-unit">组</span>' +
      '</span>' +
      '</div>' +
      '<div class="fitness-field">' +
      '<span class="fitness-field-label">每组次数</span>' +
      '<span class="fitness-stepper">' +
      stepper('reps', '每组次数减一', '−', -1) +
      inputField('reps', state.draft.reps, '每组次数') +
      stepper('reps', '每组次数加一', '+', 1) +
      '<span class="fitness-step-unit">次</span>' +
      '</span>' +
      '</div>' +
      '<div class="fitness-field">' +
      '<span class="fitness-field-label">体重</span>' +
      '<span class="fitness-stepper">' +
      stepper('weight', '体重减一', '−', -1) +
      inputField('weight', state.userWeight, '体重（千克）') +
      stepper('weight', '体重加一', '+', 1) +
      '<span class="fitness-step-unit">kg</span>' +
      '</span>' +
      '</div>' +
      '<button type="button" class="fitness-add" data-action="add">添加记录 · ' +
      esc(EXERCISES[state.draft.exercise].emoji) +
      ' ' +
      esc(EXERCISES[state.draft.exercise].name) +
      '</button>' +
      '</section>' +

      '<section class="fitness-list" aria-label="记录列表">' +
      '<div class="fitness-section-head">' +
      '<h2>记录列表</h2>' +
      '<button type="button" class="fitness-clear" data-action="clear">' +
      (clearCtrl.armed ? '确认清空？' : '清空') +
      '</button>' +
      '</div>' +
      recordsHtml +
      '</section>' +

      (state.showGoalModal ? goalModalHtml() : '');

    if (state.showGoalModal) {
      var input = app.querySelector('.fitness-modal-input');
      if (input) {
        input.focus();
        input.select();
      }
    }
  }

  function stepper(field, label, text, delta) {
    return (
      '<button type="button" class="fitness-step-btn" data-action="step" data-target="' +
      field +
      '" data-delta="' +
      delta +
      '" aria-label="' +
      label +
      '">' +
      text +
      '</button>'
    );
  }

  function inputField(field, value, label) {
    return (
      '<input type="number" class="fitness-step-input" data-field="' +
      field +
      '" value="' +
      esc(value) +
      '" min="' +
      LIMITS[field][0] +
      '" max="' +
      LIMITS[field][1] +
      '" aria-label="' +
      label +
      '">'
    );
  }

  function goalModalHtml() {
    return (
      '<div class="fitness-modal-overlay" data-action="cancel-goal" role="dialog" aria-modal="true" aria-label="设置每日目标">' +
      '<div class="fitness-modal" data-overlay-anchor="true">' +
      '<h3>设置每日目标</h3>' +
      '<input type="number" class="fitness-modal-input" data-field="goal" value="' +
      esc(state.dailyGoal) +
      '" min="1" max="100" aria-label="每日目标组数">' +
      '<div class="fitness-modal-actions">' +
      '<button type="button" class="fitness-modal-save" data-action="save-goal">保存</button>' +
      '<button type="button" class="fitness-modal-cancel" data-action="cancel-goal">取消</button>' +
      '</div>' +
      '</div>' +
      '</div>'
    );
  }

  /* ── 动作 ─────────────────────────────────────────── */

  function addRecord() {
    var ex = state.draft.exercise;
    var sets = state.draft.sets;
    var reps = state.draft.reps;
    state.records.unshift({
      id: nextRecordId(),
      exercise: ex,
      name: EXERCISES[ex].name,
      sets: sets,
      reps: reps,
      kcal: calcKcal(ex, sets, reps, state.userWeight),
      time: nowTime()
    });
    saveState();
    render();
  }

  function deleteRecord(id) {
    state.records = state.records.filter(function (r) {
      // String() 兼容旧版数字 id 与新版 UUID id
      return String(r.id) !== String(id);
    });
    saveState();
    render();
  }

  function clearRecords() {
    twoStepConfirm(clearCtrl, function () {
      state.records = [];
      saveState();
      render();
    });
  }

  function resetRecords() {
    twoStepConfirm(resetCtrl, function () {
      state.records = [];
      saveState();
      render();
    });
  }

  // 两段式确认：第一次点击进入确认态（3 秒自动复位），再次点击执行 action
  function twoStepConfirm(ctrl, action) {
    if (!ctrl.armed) {
      ctrl.armed = true;
      render();
      ctrl.timer = setTimeout(function () {
        ctrl.armed = false;
        render();
      }, 3000);
      return;
    }
    clearTimeout(ctrl.timer);
    ctrl.armed = false;
    action();
  }

  function openGoalModal() {
    state.showGoalModal = true;
    render();
  }

  function closeGoalModal() {
    state.showGoalModal = false;
    render();
  }

  function saveGoal() {
    var input = app.querySelector('.fitness-modal-input');
    var n = parseInt(input.value, 10);
    if (!isNaN(n)) {
      state.dailyGoal = clamp(n, LIMITS.goal);
      saveState();
    }
    closeGoalModal();
  }

  function stepField(field, delta) {
    var cur = field === 'weight' ? state.userWeight : state.draft[field];
    var next = clamp(cur + delta, LIMITS[field]);
    if (field === 'weight') {
      state.userWeight = next;
    } else {
      state.draft[field] = next;
    }
    saveState();
    render();
  }

  function selectExercise(key) {
    if (EXERCISES[key]) {
      state.draft.exercise = key;
      render();
    }
  }

  function setField(key, n) {
    var v = clamp(n, LIMITS[key]);
    if (key === 'weight') {
      state.userWeight = v;
      debouncedSave();
    } else if (key === 'sets' || key === 'reps') {
      state.draft[key] = v;
    }
  }
  /* ── 事件委托 ─────────────────────────────────────── */

  function onAppClick(e) {
    var el = e.target.closest('[data-action]');
    if (!el) return;
    var action = el.getAttribute('data-action');
    switch (action) {
      case 'select-exercise':
        selectExercise(el.getAttribute('data-exercise'));
        break;
      case 'step':
        stepField(el.getAttribute('data-target'), parseInt(el.getAttribute('data-delta'), 10));
        break;
      case 'add':
        addRecord();
        break;
      case 'delete':
        deleteRecord(el.getAttribute('data-id'));
        break;
      case 'clear':
        clearRecords();
        break;
      case 'reset':
        resetRecords();
        break;
      case 'open-goal':
        openGoalModal();
        break;
      case 'save-goal':
        saveGoal();
        break;
      case 'cancel-goal':
        // 取消按钮：总是关闭
        if (el.classList.contains('fitness-modal-cancel')) {
          closeGoalModal();
          break;
        }
        // 遮罩点击：仅点击空白区域（面板外）时关闭
        if (el.classList.contains('fitness-modal-overlay') && !e.target.closest('[data-overlay-anchor]')) {
          closeGoalModal();
        }
        break;
    }
  }

  function onAppInput(e) {
    var input = e.target;
    var key = input.getAttribute('data-field');
    if (!key) return;
    var raw = input.value.trim();
    if (raw === '') return; // 留空时等待 blur 恢复
    var n = parseInt(raw, 10);
    if (isNaN(n)) {
      input.value = fieldValue(key);
      return;
    }
    setField(key, n);
    if (key === 'sets' || key === 'reps') {
      debouncedSave();
    }
  }

  function onAppBlur(e) {
    var input = e.target;
    var key = input.getAttribute('data-field');
    if (!key) return;
    // 仅规范化当前输入框的值，不重建 DOM——重建会移除按钮导致 mousedown→click 丢失
    var cur = fieldValue(key);
    var n = parseInt(input.value, 10);
    if (input.value.trim() === '' || isNaN(n)) {
      input.value = cur;
    } else {
      input.value = clamp(n, LIMITS[key]);
    }
  }

  // 各字段的当前值（goal 输入框在模态框内，属 state.dailyGoal）
  function fieldValue(key) {
    if (key === 'weight') return state.userWeight;
    if (key === 'goal') return state.dailyGoal;
    return state.draft[key];
  }

  function onDocKeydown(e) {
    if (state.showGoalModal) {
      if (e.key === 'Escape') {
        closeGoalModal();
      } else if (e.key === 'Enter' && e.target.classList.contains('fitness-modal-input')) {
        saveGoal();
      }
      return;
    }
    // 录入面板：在数字输入框内按 Enter 快速添加
    if (e.key === 'Enter' && e.target.classList.contains('fitness-step-input')) {
      addRecord();
    }
  }

  /* ── 跨标签同步的焦点/输入恢复 ───────────────────── */

  // 捕获当前输入框状态（字段/值/光标），供 storage 同步后恢复
  function captureFocus(el) {
    if (!el || typeof el.getAttribute !== 'function') return null;
    var field = el.getAttribute('data-field');
    if (!field) return null;
    return { field: field, value: el.value, caret: el.selectionStart };
  }

  function restoreFocus(info, modalValue) {
    if (!info) return;
    if (info.field === 'goal') {
      var mi = app.querySelector('.fitness-modal-input');
      if (mi) {
        mi.value = modalValue != null ? modalValue : info.value;
        mi.focus();
      }
      return;
    }
    var el = app.querySelector('.fitness-step-input[data-field="' + info.field + '"]');
    if (!el) return;
    el.value = info.value;
    el.focus();
    if (typeof el.setSelectionRange === 'function' && info.caret != null) {
      el.setSelectionRange(info.caret, info.caret);
    }
  }

  /* ── 启动 ─────────────────────────────────────────── */

  document.addEventListener('DOMContentLoaded', function () {
    app = document.getElementById('fitness-app');
    if (!app) return;
    // 跨天处理：非今日则清空 records 并立即持久化，避免旧数据滞留
    var today = todayStr();
    if (state.lastDate !== today) {
      state.records = [];
      state.lastDate = today;
      saveState();
    }
    render();
    app.addEventListener('click', onAppClick);
    app.addEventListener('input', onAppInput);
    app.addEventListener('blur', onAppBlur, true);
    document.addEventListener('keydown', onDocKeydown);
    // 跨标签页同步：其他标签页写入 localStorage 时重载状态并重渲染
    window.addEventListener('storage', function (e) {
      if (e.key !== STORAGE_KEY) return;
      // 记录重建前的输入状态，同步后恢复，避免打断正在进行的输入
      var focusInfo = captureFocus(document.activeElement);
      var modalInputValue = state.showGoalModal
        ? (app.querySelector('.fitness-modal-input') || {}).value || null
        : null;
      var draft = state.draft; // 保留当前录入面板输入
      var modal = state.showGoalModal;
      state = loadState();
      state.draft = draft;
      state.showGoalModal = modal;
      // 未落盘的体重输入（防抖窗口内）合并回 state，避免同步后内存回退
      if (focusInfo && focusInfo.field === 'weight') {
        var n = parseInt(focusInfo.value, 10);
        if (!isNaN(n)) state.userWeight = clamp(n, LIMITS.weight);
      }
      render();
      restoreFocus(focusInfo, modalInputValue);
    });
  });
})();
