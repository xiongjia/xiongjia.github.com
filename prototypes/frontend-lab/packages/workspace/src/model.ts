/*
 * The workspace model: files, open documents and the buffer rule.
 *
 * This module is pure functions over a plain snapshot, which is the point: the contract between a
 * file tree, an editor and a tab strip is testable without a DOM. See `store.ts` for the store that
 * wraps it, `../../apps/lab/tests/workspace-contract.test.ts` for the integration test, and
 * `apps/lab/content/scenarios/ide-workspace.mdx` for the written contract.
 *
 * Two rules carry it:
 *
 * 1. **One buffer per file.** The editor owns the text *between* a mount and its unmount; the
 *    snapshot owns it across mounts. A tab switch therefore remounts the editor with
 *    `documentText(snapshot, path)` — drafts survive, undo history does not.
 * 2. **Dirty is derived, never stored.** `draft !== saved` is the whole definition, so a save that
 *    writes the same text, or a revert, cannot leave a stale flag behind.
 */

export type WorkspaceLanguage = 'javascript' | 'plain'

/** A file of the virtual project, as the caller hands it in. */
export type WorkspaceFile = {
  /** POSIX path inside the project, e.g. `src/components/button.tsx`. */
  path: string
  content: string
  /** `javascript` enables syntax colours; `plain` is text. */
  language?: WorkspaceLanguage
}

/** Saved content, keyed by path. */
export type SavedFile = {
  content: string
  language: WorkspaceLanguage
}

/** One open tab: the visible draft plus the last saved text. */
export type OpenDocument = {
  path: string
  draft: string
  saved: string
}

export type WorkspaceSnapshot = {
  /** Saved content of every file in the project. */
  files: Record<string, SavedFile>
  /** Open tabs, in the order they were opened. */
  open: OpenDocument[]
  /** Path of the visible document; `undefined` when no tab is open. */
  active?: string
}

export type WorkspaceTreeNode =
  | { kind: 'folder'; name: string; path: string; children: WorkspaceTreeNode[] }
  | { kind: 'file'; name: string; path: string; language: WorkspaceLanguage }

const DEFAULT_LANGUAGE: WorkspaceLanguage = 'plain'

/** `a//b/` -> `a/b`; the model never invents a path, it only compares them. */
export function normalizePath(path: string): string {
  return path.replace(/^\/+|\/+$/g, '').replace(/\/{2,}/g, '/')
}

/** Build the initial snapshot from a flat file list. */
export function createSnapshot(files: readonly WorkspaceFile[]): WorkspaceSnapshot {
  const saved: Record<string, SavedFile> = {}

  for (const file of files) {
    saved[normalizePath(file.path)] = {
      content: file.content,
      language: file.language ?? DEFAULT_LANGUAGE,
    }
  }

  return { files: saved, open: [] }
}

/** True when the open document differs from its last saved text. */
export function isDirty(document: OpenDocument): boolean {
  return document.draft !== document.saved
}

export function findDocument(
  snapshot: WorkspaceSnapshot,
  path: string | undefined,
): OpenDocument | undefined {
  if (!path) return undefined
  return snapshot.open.find((document) => document.path === path)
}

/** The visible document, if any. */
export function activeDocument(snapshot: WorkspaceSnapshot): OpenDocument | undefined {
  return findDocument(snapshot, snapshot.active)
}

/** Paths with unsaved changes, in tab order. */
export function dirtyPaths(snapshot: WorkspaceSnapshot): string[] {
  return snapshot.open.filter(isDirty).map((document) => document.path)
}

/**
 * What the editor should show for a path: the draft when the file is open, otherwise its saved
 * text. This is the only function an editor mount needs.
 */
export function documentText(snapshot: WorkspaceSnapshot, path: string): string {
  const document = findDocument(snapshot, path)
  if (document) return document.draft
  return snapshot.files[path]?.content ?? ''
}

/** Open a file (already open: just activate it). Unknown paths are ignored. */
export function openDocument(snapshot: WorkspaceSnapshot, rawPath: string): WorkspaceSnapshot {
  const path = normalizePath(rawPath)
  const file = snapshot.files[path]
  if (!file) return snapshot

  if (snapshot.open.some((document) => document.path === path)) {
    return snapshot.active === path ? snapshot : { ...snapshot, active: path }
  }

  return {
    ...snapshot,
    open: [...snapshot.open, { path, draft: file.content, saved: file.content }],
    active: path,
  }
}

/**
 * Close a tab. An unsaved draft is discarded — the tree keeps showing the saved text, and the
 * caller is expected to confirm first (the demo does not ask; it says so in its notes).
 */
export function closeDocument(snapshot: WorkspaceSnapshot, rawPath: string): WorkspaceSnapshot {
  const path = normalizePath(rawPath)
  const index = snapshot.open.findIndex((document) => document.path === path)
  if (index === -1) return snapshot

  const open = snapshot.open.filter((document) => document.path !== path)
  if (snapshot.active !== path) return { ...snapshot, open }

  // Focus the tab that took its place, else the one before it; an empty strip has no active tab.
  const next = open[index] ?? open[index - 1]

  return { ...snapshot, open, active: next?.path }
}

/** Record a keystroke. Closing over the open tab means a typed path cannot create a document. */
export function updateDraft(
  snapshot: WorkspaceSnapshot,
  rawPath: string,
  draft: string,
): WorkspaceSnapshot {
  const path = normalizePath(rawPath)
  const document = findDocument(snapshot, path)
  if (!document || document.draft === draft) return snapshot

  return {
    ...snapshot,
    open: snapshot.open.map((entry) => (entry.path === path ? { ...entry, draft } : entry)),
  }
}

/** Commit the draft: the tab and the file tree both move to the new text in one update. */
export function saveDocument(
  snapshot: WorkspaceSnapshot,
  rawPath: string = snapshot.active ?? '',
): WorkspaceSnapshot {
  const path = normalizePath(rawPath)
  const document = findDocument(snapshot, path)
  const file = snapshot.files[path]

  if (!document || !file || !isDirty(document)) return snapshot

  return {
    ...snapshot,
    files: { ...snapshot.files, [path]: { ...file, content: document.draft } },
    open: snapshot.open.map((entry) =>
      entry.path === path ? { ...entry, saved: entry.draft } : entry,
    ),
  }
}

/** Throw away the draft and go back to the saved text. */
export function revertDocument(
  snapshot: WorkspaceSnapshot,
  rawPath: string = snapshot.active ?? '',
): WorkspaceSnapshot {
  const path = normalizePath(rawPath)
  const document = findDocument(snapshot, path)
  if (!document || !isDirty(document)) return snapshot

  return {
    ...snapshot,
    open: snapshot.open.map((entry) =>
      entry.path === path ? { ...entry, draft: entry.saved } : entry,
    ),
  }
}

function compareNodes(a: WorkspaceTreeNode, b: WorkspaceTreeNode): number {
  if (a.kind !== b.kind) return a.kind === 'folder' ? -1 : 1
  return a.name.localeCompare(b.name)
}

/**
 * Project the saved files into a sorted folder tree. Folders first, then files, each alphabetically
 * — the order every file explorer uses, and the reason the generator-heavy sidebar looks calm.
 */
export function treeOf(files: Record<string, SavedFile>): WorkspaceTreeNode[] {
  type Folder = {
    name: string
    path: string
    folders: Map<string, Folder>
    files: WorkspaceTreeNode[]
  }
  const root: Folder = { name: '', path: '', folders: new Map(), files: [] }

  const folderFor = (segments: string[]): Folder => {
    let current = root
    for (const segment of segments) {
      const path = current.path ? `${current.path}/${segment}` : segment
      const existing = current.folders.get(segment)
      if (existing) {
        current = existing
        continue
      }
      const folder: Folder = { name: segment, path, folders: new Map(), files: [] }
      current.folders.set(segment, folder)
      current = folder
    }
    return current
  }

  for (const path of Object.keys(files).sort((a, b) => a.localeCompare(b))) {
    const segments = path.split('/')
    const name = segments.pop() ?? path
    const parent = folderFor(segments)
    parent.files.push({
      kind: 'file',
      name,
      path,
      language: files[path]?.language ?? DEFAULT_LANGUAGE,
    })
  }

  const render = (folder: Folder): WorkspaceTreeNode[] => [
    ...[...folder.folders.values()].map((child) => ({
      kind: 'folder' as const,
      name: child.name,
      path: child.path,
      children: render(child),
    })),
    ...folder.files,
  ]

  return render(root).sort(compareNodes)
}

/** Number of lines the editor would show; the status bar reads it back. */
export function lineCount(text: string): number {
  return text === '' ? 1 : text.split('\n').length
}
