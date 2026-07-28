/**
 * retire.js — 退休倒计时月度表动态填充
 *
 * Reads retire_grid() generated cells with data-month-index,
 * fills them based on current time. Supports pre-work vs work distinction.
 */
(function () {
  'use strict';

  document.addEventListener('DOMContentLoaded', function () {
    const grid = document.querySelector('.retire-grid');
    if (!grid) return;

    const totalMonths = parseInt(grid.getAttribute('data-retire-total'), 10);
    if (isNaN(totalMonths)) return;

    // Read birth date from grid data attributes (set by the macro)
    const birthYear = parseInt(grid.getAttribute('data-birth-year'), 10);
    const birthMonth = parseInt(grid.getAttribute('data-birth-month'), 10);
    if (isNaN(birthYear) || isNaN(birthMonth)) return;

    const cells = grid.querySelectorAll('.retire-cell[data-month-index]');
    if (cells.length === 0) return;

    const now = new Date();
    const currentYear = now.getFullYear();
    const currentMonth = now.getMonth() + 1; // JS months are 0-based

    const currentIdx = (currentYear - birthYear) * 12 + (currentMonth - birthMonth);

    const lastIdx = cells.length - 1;
    const lastMonthIdx = parseInt(cells[lastIdx].getAttribute('data-month-index'), 10);
    const allFilled = currentIdx >= lastMonthIdx;

    cells.forEach(function (cell) {
      const idx = parseInt(cell.getAttribute('data-month-index'), 10);
      if (isNaN(idx)) return;

      const isPreWork = cell.classList.contains('pre-work');

      if (allFilled) {
        cell.classList.add('retired');
      } else if (isPreWork) {
        cell.classList.add('filled');
      } else if (idx < currentIdx) {
        cell.classList.add('filled');
      } else if (idx === currentIdx) {
        cell.classList.add('current');
        cell.textContent = '🚶‍➡️';
      }
      // idx > currentIdx → leave empty (default transparent)
    });
  });
})();
