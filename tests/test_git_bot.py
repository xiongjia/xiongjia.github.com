"""Unit tests for scripts/git_bot.py — pure logic (no git / network).

Covers task parsing/planning, TemplateTask rendering, commit aggregation,
branch naming, env helpers, marker bookkeeping, plan-file variable resolution
and task config loading. The git/GitHub halves are exercised end-to-end by the
developer (needs BOT_GH_TOKEN).
"""

import json
import os
from datetime import datetime
from types import SimpleNamespace

import git_bot as gb
import pytest

# -- task parsing -------------------------------------------------------------


def test_parse_task_specs_basic():
    assert gb.parse_task_specs(["weight 82", "text-moment hi"]) == [
        ("weight", ["82"]),
        ("text-moment", ["hi"]),
    ]


def test_parse_task_specs_plus_shorthand():
    assert gb.parse_task_specs(["weight 82 + text-moment hi"]) == [
        ("weight", ["82"]),
        ("text-moment", ["hi"]),
    ]


def test_parse_task_specs_unknown():
    with pytest.raises(gb.BotError, match="unknown task"):
        gb.parse_task_specs(["bogus 1"])


def test_parse_task_specs_blank():
    assert gb.parse_task_specs(["   "]) == []


# -- TemplateTask ---------------------------------------------------------------


def test_template_task_plan():
    task = gb.TemplateTask(
        {
            "args": ["text"],
            "cmd": ["uv", "run", "python", "scripts/create_moment.py", "{text}"],
            "commit": '[bot] feat(moment): add text "{text}"',
            "body": "- text moment: {text}",
        }
    )
    info = task.plan(["你好", "--draft"])
    assert info["cmd"] == [
        "uv",
        "run",
        "python",
        "scripts/create_moment.py",
        "你好",
        "--draft",
    ]
    assert info["commit"] == '[bot] feat(moment): add text "你好"'
    assert info["body"] == "- text moment: 你好"


def test_template_task_missing_arg():
    task = gb.TemplateTask({"args": ["text"], "cmd": ["echo", "{text}"]})
    with pytest.raises(gb.BotError, match="text"):
        task.plan([])


def test_template_task_empty_body():
    task = gb.TemplateTask({"args": [], "cmd": ["echo", "x"]})
    assert task.plan([])["body"] == ""


# -- commit aggregation ----------------------------------------------------------


def test_aggregate_commit_single():
    subject, body = gb.aggregate_commit(
        [("weight", {"commit": "[bot] feat(weight): record 82 kg", "body": "- w"})]
    )
    assert subject == "[bot] feat(weight): record 82 kg"
    assert body == ["- w"]


def test_aggregate_commit_multiple():
    subject, body = gb.aggregate_commit(
        [
            ("weight", {"commit": "[bot] feat(weight): record 82 kg", "body": "- w"}),
            ("moment", {"commit": "[bot] feat(moment): add text hi", "body": "- m"}),
        ]
    )
    assert subject == "[bot] feat(weight): record 82 kg + feat(moment): add text hi"
    assert body == ["- w", "- m"]


# -- branch / env helpers ----------------------------------------------------------


def test_branch_for():
    branch = gb.branch_for(["weight", "text-moment"], datetime(2026, 8, 12, 10, 30, 5))
    assert branch == "bot/weight+text-moment/20260812-103005"


def test_base_branch_default():
    os.environ.pop("BOT_BASE_BRANCH", None)
    assert gb.base_branch() == "master"


def test_base_branch_env():
    os.environ["BOT_BASE_BRANCH"] = "dev"
    assert gb.base_branch() == "dev"
    os.environ.pop("BOT_BASE_BRANCH", None)


def test_env_true():
    os.environ["_T"] = "true"
    assert gb._env_true("_T")
    os.environ["_T"] = "yes"
    assert gb._env_true("_T")
    os.environ["_T"] = "0"
    assert not gb._env_true("_T")
    os.environ.pop("_T", None)
    assert not gb._env_true("_T")


# -- marker bookkeeping --------------------------------------------------------------


def test_marker_roundtrip(tmp_path):
    gb.write_marker(tmp_path, "bot/weight/20260812-000000", "running", [("weight", ["82"])])
    marker = gb.read_marker(tmp_path)
    assert marker["branch"] == "bot/weight/20260812-000000"
    assert marker["state"] == "running"
    assert json.loads(marker["tasks"]) == [["weight", ["82"]]]
    state, active = gb.marker_state(tmp_path)
    assert state == "running"
    assert active  # pid = the test process itself (alive)


def test_marker_state_dead_pid(tmp_path):
    (tmp_path / gb.MARKER).write_text(
        "pid=999999999\nbranch=bot/x/1\nstarted=2026-08-12T00:00:00\nstate=stale\ntasks=[]\n",
        encoding="utf-8",
    )
    state, active = gb.marker_state(tmp_path)
    assert state == "stale"
    assert not active


# -- plan files ------------------------------------------------------------------------


def _mk_plan(monkeypatch, tmp_path, content):
    plan_dir = tmp_path / ".bot" / "plans"
    plan_dir.mkdir(parents=True)
    (plan_dir / "morning.yml").write_text(content, encoding="utf-8")
    monkeypatch.setattr(gb, "REPO_ROOT", tmp_path)


def test_plan_specs_positional(monkeypatch, tmp_path):
    _mk_plan(
        monkeypatch,
        tmp_path,
        "vars:\n  weight: {desc: w, required: true}\ntasks:\n  - 'weight {weight}'\n"
        "auto_merge: true\n",
    )
    args = SimpleNamespace(plan="morning", tasks=["81.5"], var=[], auto_merge=None)
    assert gb.plan_specs(args) == ["weight 81.5"]
    assert args.auto_merge is True  # plan default applies when CLI flag absent


def test_plan_specs_cli_flag_wins(monkeypatch, tmp_path):
    _mk_plan(monkeypatch, tmp_path, "vars: {}\ntasks: ['weight 82']\nauto_merge: false\n")
    args = SimpleNamespace(plan="morning", tasks=[], var=[], auto_merge=True)
    assert gb.plan_specs(args) == ["weight 82"]
    assert args.auto_merge is True  # explicit CLI flag not overridden by plan


def test_plan_specs_missing_required(monkeypatch, tmp_path):
    _mk_plan(
        monkeypatch,
        tmp_path,
        "vars:\n  weight: {desc: w, required: true}\ntasks:\n  - 'weight {weight}'\n",
    )
    args = SimpleNamespace(plan="morning", tasks=[], var=[], auto_merge=None)
    with pytest.raises(gb.BotError, match="weight"):
        gb.plan_specs(args)


def test_plan_specs_var_and_empty_skip(monkeypatch, tmp_path):
    _mk_plan(
        monkeypatch,
        tmp_path,
        "vars:\n  weight: {required: true}\n  note: {default: ''}\n"
        "tasks:\n  - 'weight {weight}'\n  - 'text-moment {note}'\n",
    )
    args = SimpleNamespace(plan="morning", tasks=[], var=["weight=82"], auto_merge=None)
    # empty note renders an empty task line → skipped
    assert gb.plan_specs(args) == ["weight 82"]


def test_plan_specs_not_found(monkeypatch, tmp_path):
    monkeypatch.setattr(gb, "REPO_ROOT", tmp_path)
    args = SimpleNamespace(plan="nope", tasks=[], var=[], auto_merge=None)
    with pytest.raises(gb.BotError, match="plan not found"):
        gb.plan_specs(args)


# -- config loading (mkdocs.yml with !ENV / !!python:name tags) -------------------------


def test_load_task_config(monkeypatch, tmp_path):
    (tmp_path / "mkdocs.yml").write_text(
        "site_name: !ENV [SITE_NAME, 'x']\n"
        "extra:\n"
        "  bot:\n"
        "    tasks:\n"
        "      text-moment:\n"
        "        args: [text]\n"
        "        cmd: [echo, '{text}']\n"
        "        commit: '[bot] c {text}'\n"
        "        body: '- {text}'\n"
        "  emoji:\n"
        "    index: !!python/name:material.extensions.emoji.twemoji\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(gb, "REPO_ROOT", tmp_path)
    cfg = gb.load_task_config()
    assert cfg["text-moment"]["args"] == ["text"]
    assert cfg["text-moment"]["commit"] == "[bot] c {text}"


# -- proxy ------------------------------------------------------------------


def test_apply_proxy_keeps_shell_when_unset():
    os.environ.pop("BOT_HTTP_PROXY", None)
    os.environ["HTTPS_PROXY"] = "http://shell:8080"
    os.environ.pop("NO_PROXY", None)
    try:
        gb._apply_proxy()
        assert os.environ["HTTPS_PROXY"] == "http://shell:8080"  # shell kept
    finally:
        os.environ.pop("HTTPS_PROXY", None)
        os.environ.pop("NO_PROXY", None)


def test_apply_proxy_bot_wins_over_shell():
    os.environ["HTTPS_PROXY"] = "http://shell:8080"
    os.environ["BOT_HTTP_PROXY"] = "http://bot:1095"
    try:
        gb._apply_proxy()
        assert os.environ["HTTPS_PROXY"] == "http://bot:1095"  # bot wins
        assert os.environ["HTTP_PROXY"] == "http://bot:1095"
        assert os.environ["NO_PROXY"] == "127.0.0.1,localhost"
    finally:
        os.environ.pop("BOT_HTTP_PROXY", None)
        os.environ.pop("HTTP_PROXY", None)
        os.environ.pop("HTTPS_PROXY", None)
        os.environ.pop("NO_PROXY", None)


# -- branch guard -----------------------------------------------------------


def test_bot_branch_guard_accepts_bot():
    gb._bot_branch_guard("bot/weight/20260812-000000")  # no raise


def test_bot_branch_guard_rejects_others():
    for bad in ("master", "dev/daily2", "feature/x", "", "botx"):
        with pytest.raises(gb.BotError, match="non-bot"):
            gb._bot_branch_guard(bad)


# -- enu task ----------------------------------------------------------------


def test_enu_task_joins_free_text():
    info = gb.task_enu(None, ["mermaid", "一个", "libary", "name"])
    assert info["cmd"] == [
        "uv",
        "run",
        "python",
        "scripts/enu.py",
        "add",
        "mermaid 一个 libary name",
    ]
    assert info["commit"] == '[bot] feat(enu): add scrap "mermaid 一个 libary name"'


def test_enu_task_options():
    info = gb.task_enu(None, ["cumbersome", "--date", "2026-08-11"])
    assert info["cmd"] == [
        "uv",
        "run",
        "python",
        "scripts/enu.py",
        "add",
        "cumbersome",
        "--date",
        "2026-08-11",
    ]
    assert info["commit"] == '[bot] feat(enu): add scrap "cumbersome"'


def test_enu_task_no_args():
    with pytest.raises(gb.BotError, match="enu task needs"):
        gb.task_enu(None, [])


def test_enu_task_only_options_rejected():
    with pytest.raises(gb.BotError, match="enu task needs"):
        gb.task_enu(None, ["--date", "2026-08-11"])
