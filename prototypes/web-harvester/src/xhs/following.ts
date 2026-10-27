/** One entry of the account's following list (关注). */
export interface FollowItem {
  nickname: string;
  /** Whatever the row shows under the name ("1篇笔记未看", "8件商品上新", …). */
  desc: string;
  avatarUrl: string | null;
}

/** Raw row data pulled out of the list panel. */
export interface FollowRow {
  name: string | null;
  desc: string | null;
  avatar: string | null;
}

/**
 * Turn a scraped row into an item.
 *
 * The panel renders rows as plain divs — no profile link, so there is no user id
 * to read (unlike note pages). The nickname is the only stable handle, and rows
 * without one are dropped.
 */
export function toFollowItem(row: FollowRow): FollowItem | null {
  const nickname = (row.name ?? "").trim();
  if (!nickname) {
    return null;
  }
  return {
    nickname,
    desc: (row.desc ?? "").trim(),
    avatarUrl: row.avatar?.trim() || null,
  };
}

/** Drop duplicate rows, keeping the first occurrence. */
export function uniqueFollowItems(
  items: Array<FollowItem | null>,
): FollowItem[] {
  const seen = new Set<string>();
  const out: FollowItem[] = [];
  for (const item of items) {
    if (!item) {
      continue;
    }
    const key = `${item.nickname}|${item.avatarUrl ?? ""}`;
    if (seen.has(key)) {
      continue;
    }
    seen.add(key);
    out.push(item);
  }
  return out;
}

/** One JSON object per line — the format both humans and `jq` like. */
export function toJsonl(items: FollowItem[]): string {
  return (
    items.map((item) => JSON.stringify(item)).join("\n") +
    (items.length ? "\n" : "")
  );
}
