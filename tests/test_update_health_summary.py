"""Unit tests for scripts/update_health_summary.py (no pi invocation).

Covers the offline-testable pieces: statistics computation from the data
dicts, prompt building, pi JSON event extraction, output cleaning, and the
CLI main() flow with run_pi/load_yaml monkeypatched.
"""

import json
from datetime import date, datetime

import pytest
import update_health_summary as uhs

# ---------------------------------------------------------------------------
#  pi output parsing
# ---------------------------------------------------------------------------


def _assistant_message_end(text: str) -> str:
    return json.dumps(
        {
            "type": "message_end",
            "message": {"role": "assistant", "content": [{"type": "text", "text": text}]},
        }
    )


def test_extract_text_skips_thinking_and_takes_last_assistant_message():
    events = "\n".join(
        [
            json.dumps({"type": "agent_start"}),
            _assistant_message_end("旧消息"),
            json.dumps(
                {
                    "type": "message_end",
                    "message": {
                        "role": "assistant",
                        "content": [
                            {"type": "thinking", "thinking": "内部推理…"},
                            {"type": "text", "text": "第一行"},
                            {"type": "text", "text": "\n第二行"},
                        ],
                    },
                }
            ),
            json.dumps({"type": "turn_end", "message": {}, "toolResults": []}),
        ]
    )
    assert uhs.extract_text(events) == "第一行\n第二行"


def test_extract_text_ignores_non_json_lines_and_returns_none_when_absent():
    assert uhs.extract_text("not json\n") is None
    assert uhs.extract_text('{"type":"agent_start"}\n') is None
    assert uhs.extract_text("") is None


def test_extract_model_from_message():
    events = json.dumps(
        {
            "type": "message_end",
            "message": {
                "role": "assistant",
                "content": [{"type": "text", "text": "你好"}],
                "provider": "deepseek",
                "model": "deepseek-v4-flash",
            },
        }
    )
    assert uhs.extract_model(events) == "deepseek-v4-flash"
    assert uhs.extract_model('{"type":"agent_start"}') is None


def test_prettify_model():
    assert uhs.prettify_model("deepseek-v4-flash") == "DeepSeek V4 Flash"
    assert uhs.prettify_model("claude-sonnet-4") == "Claude Sonnet 4"
    assert uhs.prettify_model("qwen/qwen3-32b") == "Qwen Qwen3 32B"
    assert uhs.prettify_model(None) == "本地 AI"
    assert uhs.prettify_model("") == "本地 AI"


def test_clean_ai_text_unwraps_fence_and_strips_headings():
    assert uhs.clean_ai_text("```\n## 标题\n正文\n```") == "正文"
    assert uhs.clean_ai_text("```markdown\n正文\n```") == "正文"
    assert uhs.clean_ai_text("# 一级标题\n\n正文") == "正文"
    assert uhs.clean_ai_text("### 保留三级标题\n正文") == "### 保留三级标题\n正文"
    assert uhs.clean_ai_text("正文含```代码\n```样例") == "正文含```代码\n```样例"


def test_run_pi_builds_expected_command(monkeypatch):
    captured = {}

    class FakeProc:
        returncode = 0
        stderr = ""
        stdout = json.dumps(
            {
                "type": "message_end",
                "message": {
                    "role": "assistant",
                    "content": [{"type": "text", "text": "你好"}],
                    "model": "deepseek-v4-flash",
                },
            }
        )

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["kwargs"] = kwargs
        return FakeProc()

    monkeypatch.setattr(uhs.subprocess, "run", fake_run)
    monkeypatch.setattr(uhs.shutil, "which", lambda name: "/usr/local/bin/pi")

    text, label = uhs.run_pi("提示词", model="anthropic/claude-sonnet-4", timeout=42)
    assert text == "你好"
    assert label == "DeepSeek V4 Flash"
    assert captured["cmd"] == [
        "/usr/local/bin/pi",
        "-p",
        "--no-session",
        "--no-tools",
        "--no-context-files",
        "--mode",
        "json",
        "--model",
        "anthropic/claude-sonnet-4",
        "提示词",
    ]
    assert captured["kwargs"]["timeout"] == 42
    assert captured["kwargs"]["encoding"] == "utf-8"


# ---------------------------------------------------------------------------
#  Statistics computation
# ---------------------------------------------------------------------------


def test_compute_retire_stats_with_expected_age():
    data = {"birth_date": "1981-08-12", "gender": "male", "expected_retire_age": 55}
    stats = uhs.compute_retire_stats(data, date(2026, 8, 3))
    assert stats["gender"] == "男性"
    assert stats["expected_age"] == 55
    assert stats["target_date"] == date(2036, 8, 1)
    assert stats["remaining_years"] == 10
    assert stats["remaining_months"] == 0
    assert stats["days_remaining"] > 3600
    assert 80 < stats["progress_pct"] < 85


def test_compute_retire_stats_invalid_data_returns_empty():
    assert uhs.compute_retire_stats({}, date(2026, 8, 3)) == {}
    assert uhs.compute_retire_stats({"birth_date": "bad", "gender": "male"}, date(2026, 8, 3)) == {}
    assert (
        uhs.compute_retire_stats(
            {"birth_date": "1981-08-12", "gender": "unknown"}, date(2026, 8, 3)
        )
        == {}
    )


def test_compute_retire_stats_retired_person():
    data = {"birth_date": "1950-01-01", "gender": "male"}
    stats = uhs.compute_retire_stats(data, date(2026, 8, 3))
    assert stats["is_retired"] is True
    assert stats["progress_pct"] == 100.0
    assert stats["remaining_years"] == 0
    assert stats["remaining_months"] == 0
    assert stats["days_remaining"] == 0


def test_compute_retire_stats_expected_date_passed_falls_back_to_legal():
    # expected plan (55) passed in 2025-01, but legal retirement is not reached
    data = {"birth_date": "1970-01-01", "gender": "male", "expected_retire_age": 55}
    stats = uhs.compute_retire_stats(data, date(2026, 8, 3))
    assert stats["is_retired"] is False
    assert stats["target_date"] == date(2031, 4, 1)
    assert stats["remaining_years"] == 4
    assert stats["remaining_months"] == 8
    assert stats["days_remaining"] > 1600


def test_compute_weight_stats_latest_and_delta():
    data = {
        "cm": 176,
        "start_date": "2026-07-27",
        "weeks": [
            {"days": [None, 82.35, 81.50, 82.90, 82.40, 82.40, 81.90]},
            {"days": [82.40, None, None, None, None, None, None]},
        ],
    }
    stats = uhs.compute_weight_stats(data)
    assert stats["latest"] == 82.40
    assert stats["latest_date"] == date(2026, 8, 3)
    assert stats["latest_week_avg"] == 82.40
    assert stats["bmi"] == 82.40 / 1.76**2
    assert stats["bmi_status"] == "超重"
    assert stats["delta"] == pytest.approx(82.40 - 493.45 / 6)
    assert stats["healthy_min"] < stats["healthy_max"]


def test_compute_weight_stats_no_data_returns_empty():
    assert uhs.compute_weight_stats({}) == {}
    stats = uhs.compute_weight_stats({"cm": 176})
    assert stats["latest"] is None
    assert "bmi" not in stats


def test_compute_running_stats_aggregates():
    data = {
        "activities": [
            {
                "run_id": 1,
                "distance": 2000.0,
                "moving_time": "0:20:00",
                "elevation_gain": 5,
                "average_heartrate": 130,
                "start_date_local": "2026-08-02 14:00:00",
            },
            {
                "run_id": 2,
                "distance": 1000.0,
                "moving_time": "0:10:00",
                "elevation_gain": 2,
                "average_heartrate": 120,
                "start_date_local": "2026-08-01 14:00:00",
            },
            {
                "run_id": 3,
                "distance": 3000.0,
                "moving_time": "0:30:00",
                "elevation_gain": 8,
                "average_heartrate": 125,
                "start_date_local": "2026-07-20 14:00:00",
            },
            {
                "run_id": 4,
                "distance": 500.0,
                "moving_time": "0:05:00",
                "elevation_gain": 1,
                "average_heartrate": 110,
                "start_date_local": "2025-12-01 14:00:00",
            },
        ]
    }
    today = date(2026, 8, 3)
    stats = uhs.compute_running_stats(data, today)
    assert stats["runs"] == 4
    assert stats["total_km"] == 6.5
    assert stats["recent30_runs"] == 3
    assert stats["recent30_km"] == 6.0
    assert stats["week7_runs"] == 2
    assert stats["streak"] == 2
    assert stats["avg_hr"] == 121.25
    assert stats["latest_date"] == date(2026, 8, 2)


def test_compute_running_stats_empty():
    assert uhs.compute_running_stats({}, date(2026, 8, 3)) == {}


# ---------------------------------------------------------------------------
#  Prompt building
# ---------------------------------------------------------------------------


def test_build_prompt_embeds_stats_and_requirements():
    stats = {
        "retire": {
            "gender": "男性",
            "expected_age": 55,
            "target_date": date(2036, 8, 1),
            "is_retired": False,
            "total_months": 661,
            "months_lived": 541,
            "remaining_years": 10,
            "remaining_months": 0,
            "days_remaining": 3651,
            "progress_pct": 81.8,
        },
        "weight": {
            "cm": 176,
            "latest": 82.40,
            "latest_date": date(2026, 8, 3),
            "bmi": 26.6,
            "bmi_status": "超重",
            "latest_week_avg": 82.40,
            "delta": 0.16,
            "healthy_min": 57.3,
            "healthy_max": 74.0,
        },
        "running": {
            "runs": 4,
            "total_km": 6.5,
            "total_time_h": 1.08,
            "elevation": 16,
            "recent30_runs": 3,
            "recent30_km": 6.0,
            "week7_runs": 2,
            "avg_hr": 121.25,
            "latest_date": date(2026, 8, 2),
            "streak": 2,
        },
    }
    prompt = uhs.build_prompt(stats, date(2026, 8, 3))
    assert "2026-08-03" in prompt
    assert "2036-08-01" in prompt
    assert "（预期 55 岁退休）" in prompt
    assert "82.40" in prompt
    assert "6.5 km" in prompt
    assert "250–400 字" in prompt


def test_build_prompt_handles_missing_sections():
    prompt = uhs.build_prompt({"retire": {}, "weight": {}, "running": {}}, date(2026, 8, 3))
    assert "数据摘要" in prompt
    assert "### 退休倒计时" not in prompt
    assert "### 跑步" not in prompt
    assert "### 体重" not in prompt


def test_build_prompt_retired_section():
    stats = {
        "retire": {
            "gender": "男性",
            "target_date": date(2010, 1, 1),
            "is_retired": True,
            "total_months": 721,
            "months_lived": 920,
            "remaining_years": 0,
            "remaining_months": 0,
            "days_remaining": 0,
            "progress_pct": 100.0,
        },
        "weight": {},
        "running": {},
    }
    prompt = uhs.build_prompt(stats, date(2026, 8, 3))
    assert "退休状态：已退休 🎉" in prompt
    assert "进度：100%" in prompt
    assert "距离退休" not in prompt
    assert "已过" not in prompt
    assert "约 0 天" not in prompt


# ---------------------------------------------------------------------------
#  CLI main() flow
# ---------------------------------------------------------------------------


def test_main_writes_output(tmp_path, monkeypatch):
    out = tmp_path / "_summary.md"

    def fake_run_pi(prompt, model=None, timeout=300):
        assert "健康" in prompt
        return "总体状态：良好。\n\n**建议**：继续保持。", "DeepSeek V4 Flash"

    monkeypatch.setattr(uhs, "run_pi", fake_run_pi)
    monkeypatch.setattr(uhs, "load_yaml", lambda path: {})
    monkeypatch.setattr(uhs, "DATA_DIR", tmp_path)

    assert uhs.main(["--output", str(out)]) == 0
    content = out.read_text(encoding="utf-8")
    assert content.startswith('???+ note "🤖 AI 健康建议 · DeepSeek V4 Flash')
    assert "总体状态" in content
    assert "**建议**" in content
    assert "uv run poe" not in content


def test_main_dry_run_prints_prompt_without_writing(tmp_path, monkeypatch, capsys):
    out = tmp_path / "_summary.md"
    monkeypatch.setattr(
        uhs, "load_yaml", lambda path: {"birth_date": "1981-08-12", "gender": "male"}
    )

    assert uhs.main(["--dry-run", "--output", str(out)]) == 0
    captured = capsys.readouterr()
    assert "数据摘要" in captured.out
    assert not out.exists()


def test_main_pi_failure_keeps_existing_summary(tmp_path, monkeypatch, capsys):
    out = tmp_path / "_summary.md"
    out.write_text("旧内容", encoding="utf-8")

    def boom(prompt, model=None, timeout=300):
        raise RuntimeError("pi failed")

    monkeypatch.setattr(uhs, "run_pi", boom)
    monkeypatch.setattr(uhs, "load_yaml", lambda path: {})

    assert uhs.main(["--output", str(out)]) == 1
    assert out.read_text(encoding="utf-8") == "旧内容"
    assert "pi failed" in capsys.readouterr().err


def test_main_pi_oserror_keeps_existing_summary(tmp_path, monkeypatch, capsys):
    out = tmp_path / "_summary.md"
    out.write_text("旧内容", encoding="utf-8")

    def boom(prompt, model=None, timeout=300):
        raise PermissionError("exec format error")

    monkeypatch.setattr(uhs, "run_pi", boom)
    monkeypatch.setattr(uhs, "load_yaml", lambda path: {})

    assert uhs.main(["--output", str(out)]) == 1
    assert out.read_text(encoding="utf-8") == "旧内容"
    assert "exec format error" in capsys.readouterr().err


def test_main_rejects_directory_output(tmp_path):
    with pytest.raises(SystemExit) as exc:
        uhs.main(["--output", str(tmp_path)])
    assert exc.value.code == 2


def test_write_summary_wraps_in_expanded_card_with_model_and_time(tmp_path):
    out = tmp_path / "_summary.md"
    uhs.write_summary(out, "正文", "DeepSeek V4 Flash", datetime(2026, 8, 3, 21, 30))
    content = out.read_text(encoding="utf-8")
    assert content.startswith('???+ note "🤖 AI 健康建议 · DeepSeek V4 Flash · 2026-08-03 21:30"')
    assert "    正文\n" in content
    assert "uv run poe" not in content


def test_write_summary_normalizes_ordered_lists_like_poe_fmt(tmp_path):
    out = tmp_path / "_summary.md"
    uhs.write_summary(
        out, "1. 建议一\n2. 建议二\n3. 建议三", "DeepSeek V4 Flash", datetime(2026, 8, 3, 21, 30)
    )
    content = out.read_text(encoding="utf-8")
    assert "    1. 建议一\n    1. 建议二\n    1. 建议三" in content


def test_write_summary_strips_ai_code_fence(tmp_path):
    out = tmp_path / "_summary.md"
    uhs.write_summary(
        out, "```\n总体状态：良好。\n```", "DeepSeek V4 Flash", datetime(2026, 8, 3, 21, 30)
    )
    content = out.read_text(encoding="utf-8")
    assert "```" not in content
    assert "    总体状态：良好。" in content


def test_write_summary_empty_body_falls_back(tmp_path):
    out = tmp_path / "_summary.md"
    uhs.write_summary(out, "```\n```", "DeepSeek V4 Flash", datetime(2026, 8, 3, 21, 30))
    content = out.read_text(encoding="utf-8")
    assert "（本轮未生成内容）" in content
