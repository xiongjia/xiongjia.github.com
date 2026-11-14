import assert from 'node:assert/strict'
import { test } from 'node:test'

import {
  matchCommands,
  mergeRanges,
  type PaletteCommand,
} from '@frontend-lab/command-palette/match'

/*
 * The palette's ranking is the part a DOM test cannot see clearly: two boxes both "work" while one
 * puts the command you meant in the first slot. These cases pin the ordering rules from `match.ts`.
 */

function command(id: string, title: string, extra: Partial<PaletteCommand> = {}): PaletteCommand {
  return { id, title, run: () => {}, ...extra }
}

const titles = (commands: PaletteCommand[]) => commands.map((command) => command.title)

test('an exact title wins over every other kind of match', () => {
  const commands = [
    command('a', 'Search everything'),
    command('b', 'Search'),
    command('c', 'Advanced search'),
  ]

  assert.deepEqual(titles(matchCommands(commands, 'search').map((match) => match.command)), [
    'Search',
    'Search everything',
    'Advanced search',
  ])
})

test('a word start beats a match in the middle of a word', () => {
  const commands = [command('a', 'Reopen settings'), command('b', 'Open settings')]

  // Both contain "set"; "Open settings" starts a word at index 5, "Reopen settings" at index 7.
  assert.deepEqual(titles(matchCommands(commands, 'set').map((match) => match.command)), [
    'Open settings',
    'Reopen settings',
  ])
})

test('a subsequence matches and highlights each matched character', () => {
  // "Settings": s at 0, t at 2, g at 6 — not adjacent, so each hit stays its own range.
  const [match] = matchCommands([command('a', 'Settings')], 'stg')
  assert.ok(match)
  assert.deepEqual(match.ranges, [
    [0, 1],
    [2, 3],
    [6, 7],
  ])
})

test('keywords can match a command the title does not contain', () => {
  const commands = [
    command('a', 'Preferences', { keywords: 'settings theme appearance' }),
    command('b', 'Open settings'),
  ]

  const matches = matchCommands(commands, 'settings')
  // A title match outranks a keyword match even though "settings" is a keyword *prefix*.
  assert.deepEqual(titles(matches.map((match) => match.command)), ['Open settings', 'Preferences'])
  // A keyword hit has nothing to highlight: the word is not on screen.
  assert.deepEqual(matches[1]?.ranges, [])
})

test('unmatched commands disappear instead of ranking last', () => {
  const commands = [command('a', 'Toggle theme'), command('b', 'New note')]
  assert.deepEqual(titles(matchCommands(commands, 'zzz').map((match) => match.command)), [])
})

test('an empty query keeps the caller order (and highlights nothing)', () => {
  const commands = [command('b', 'Second'), command('a', 'First')]
  const matches = matchCommands(commands, '   ')

  assert.deepEqual(titles(matches.map((match) => match.command)), ['Second', 'First'])
  assert.deepEqual(
    matches.map((match) => match.ranges),
    [[], []],
  )
})

test('equal scores keep the input order, which is how recents stay on top', () => {
  const commands = [command('a', 'Theme light'), command('b', 'Theme dark')]
  // Both are prefix matches with the same shape, so only the input order can decide.
  assert.deepEqual(titles(matchCommands(commands, 'theme').map((match) => match.command)), [
    'Theme light',
    'Theme dark',
  ])
})

test('highlight ranges are merged so adjacent characters render as one mark', () => {
  assert.deepEqual(
    mergeRanges([
      [4, 5],
      [0, 1],
      [1, 2],
      [6, 8],
      [7, 9],
    ]),
    [
      [0, 2],
      [4, 5],
      [6, 9],
    ],
  )
})

test('a subsequence spread across unrelated words is not a match', () => {
  // "s…e…t" appears in order in "share people team", but 16 characters apart — that is noise.
  const invite = {
    id: 'invite',
    title: 'Invite a teammate',
    keywords: 'share people team',
    run: () => {},
  }
  assert.deepEqual(matchCommands([invite], 'set'), [])

  // Inside one word but still spanning "Send" and "test": initials across words are not supported.
  const send = { id: 'send', title: 'Send a test message', run: () => {} }
  assert.deepEqual(matchCommands([send], 'set'), [])
})

test('the query is trimmed and case-insensitive', () => {
  const [match] = matchCommands([command('a', 'Toggle theme')], '  THEME  ')
  assert.ok(match)
  assert.deepEqual(match.ranges, [[7, 12]])
})
