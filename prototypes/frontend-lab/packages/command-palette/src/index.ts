/*
 * A command palette that is a component, not an app framework.
 *
 * `match.ts` is pure and testable; `command-palette.tsx` owns the dialog, the combobox/listbox wiring
 * and focus restoration. The caller supplies the commands, which is what lets the lab shell and a
 * demo share one implementation with completely different command sets.
 */

export { CommandPalette } from './command-palette'
export type { CommandPaletteProps } from './command-palette'
export { useCommandShortcut } from './use-command-shortcut'
export { matchCommands, mergeRanges } from './match'
export type { CommandMatch, PaletteCommand } from './match'
