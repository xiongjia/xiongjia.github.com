import { describe, expect, it } from "vitest";
import { toFollowItem, toJsonl, uniqueFollowItems } from "./following";

describe("following helpers", () => {
  it("maps a scraped row to an item", () => {
    expect(
      toFollowItem({
        name: " 财经不眠姐 ",
        desc: " 1篇笔记未看 ",
        avatar: "https://sns-avatar-qc.xhscdn.com/avatar/x.jpg",
      }),
    ).toEqual({
      nickname: "财经不眠姐",
      desc: "1篇笔记未看",
      avatarUrl: "https://sns-avatar-qc.xhscdn.com/avatar/x.jpg",
    });
  });

  it("drops rows without a nickname", () => {
    expect(toFollowItem({ name: "  ", desc: "x", avatar: null })).toBeNull();
    expect(toFollowItem({ name: null, desc: null, avatar: null })).toBeNull();
  });

  it("keeps a null avatar and empty desc", () => {
    expect(toFollowItem({ name: "NASA宇宙", desc: null, avatar: "" })).toEqual({
      nickname: "NASA宇宙",
      desc: "",
      avatarUrl: null,
    });
  });

  it("de-duplicates on nickname + avatar", () => {
    const items = [
      { nickname: "A", desc: "", avatarUrl: "u/a" },
      { nickname: "A", desc: "again", avatarUrl: "u/a" },
      { nickname: "A", desc: "", avatarUrl: "u/b" },
      null,
    ];

    expect(uniqueFollowItems(items).map((item) => item.avatarUrl)).toEqual([
      "u/a",
      "u/b",
    ]);
  });

  it("writes one JSON object per line, nothing for an empty list", () => {
    expect(toJsonl([])).toBe("");
    const lines = toJsonl([
      { nickname: "A", desc: "d", avatarUrl: null },
      { nickname: "B", desc: "", avatarUrl: "u/b" },
    ])
      .trimEnd()
      .split("\n");
    expect(lines).toHaveLength(2);
    expect(JSON.parse(lines[0] ?? "")).toMatchObject({ nickname: "A" });
  });
});
