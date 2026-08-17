---
icon: material/bookmark-multiple
hide:
  - tags
---

# :material-bookmark-multiple: Collection

Curated links, tools, and resources organized by domain.
Raw material for deeper research.

______________________________________________________________________

| Domain                                                 | Description                                |
| ------------------------------------------------------ | ------------------------------------------ |
| [:material-database: Database](./database.md)          | SQLite, PostgreSQL, Key-Value, Time-Series |
| [:material-chart-bell-curve: Monitor](./monitor.md)    | Prometheus, APM, system monitoring         |
| [:material-movie-open-play: Media](./media.md)         | Streaming, trackers, automation            |
| [:material-playlist-check: Plans](./scraps/plans.md)   | TODOs & ideas (action items, deletable)    |
| [:material-wrench: Dev Tools](./dev-tools.md)          | CLI, RPC, serialization, DevOps            |
| [:material-monitor-dashboard: Frontend](./frontend.md) | React, UI tools, frameworks                |
| [:material-robot: AI](./ai.md)                         | Local AI, AI Skills, MCP, AI CLI           |
| [:material-code-tags: Languages](./languages.md)       | Go, Java, C/C++ toolchains                 |
| [:material-gamepad-variant: Game Dev](./game-dev.md)   | Godot, Krita, LDTK, 2D game dev tools      |
| [:material-map: Maps](./maps.md)                       | MapLibre, Protomaps, PMTiles, Tippecanoe   |
| [:material-emoticon-happy-outline: Emoji](./emoji.md)  | 常用 emoji 复制清单                        |

______________________________________________________________________

> Collection is the first stage of the knowledge pipeline.
> Interesting topics move on to [Research](../research/index.md) for deep dives.

______________________________________________________________________

### 📥 Capture

```bash
poe collect-add "A neat CLI tool" --url https://...
poe collect-add "Book: ..." --source manual
poe collect-add "Check out Y" --source HN
poe collect-todo "看这个视频"
poe collect-idea "用 MapLibre 做热力图"
```

Then run `/skill:collect-organize arch` to batch-organize the inbox:

- **Resources** (link / book / note) → appended to the domain pages above
- **Action items** (todo / idea / misc) → appended to [Plans](./scraps/plans.md)

`todo` and `idea` skip the inbox and go directly to [Plans](./scraps/plans.md).
