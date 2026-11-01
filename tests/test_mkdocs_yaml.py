"""Unit tests for shared/mkdocs_yaml.py — the shared mkdocs.yml loader."""

import pytest

import shared.mkdocs_yaml as mky


def test_load_document_returns_every_top_level_key(tmp_path, monkeypatch):
    yml = tmp_path / "mkdocs.yml"
    yml.write_text(
        "site_name: !ENV [SITE_NAME, 'x']\n"
        "exclude_docs: |\n  **/_*.md\n"
        "extra:\n  bucket:\n    enabled: true\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(mky, "MKDOCS_YML", yml)
    document = mky.load_document()
    assert document["site_name"] == "x"
    assert document["exclude_docs"] == "**/_*.md\n"
    assert document["extra"] == {"bucket": {"enabled": True}}


def test_load_document_missing_file_is_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(mky, "MKDOCS_YML", tmp_path / "nope.yml")
    assert mky.load_document() == {}


def test_load_document_parse_error_degrades_or_raises(tmp_path, monkeypatch, capsys):
    yml = tmp_path / "mkdocs.yml"
    yml.write_text("exclude_docs: [unclosed\n", encoding="utf-8")
    monkeypatch.setattr(mky, "MKDOCS_YML", yml)
    assert mky.load_document() == {}
    assert "cannot parse" in capsys.readouterr().err
    with pytest.raises(mky.MkdocsYamlError):
        mky.load_document(strict=True)


def test_load_extra_missing_file(tmp_path, monkeypatch):
    monkeypatch.setattr(mky, "MKDOCS_YML", tmp_path / "nope.yml")
    assert mky.load_extra("bucket") == {}


def test_load_extra_plain(tmp_path, monkeypatch):
    yml = tmp_path / "mkdocs.yml"
    yml.write_text("extra:\n  bucket:\n    enabled: true\n", encoding="utf-8")
    monkeypatch.setattr(mky, "MKDOCS_YML", yml)
    assert mky.load_extra("bucket") == {"enabled": True}
    assert mky.load_extra("missing") == {}


def test_load_extra_tolerates_mkdocs_tags(tmp_path, monkeypatch):
    yml = tmp_path / "mkdocs.yml"
    yml.write_text(
        "site_name: !ENV [SITE_NAME, 'x']\n"
        "extra:\n"
        "  bucket:\n"
        "    base_url: !ENV [MKDOCS_BUCKET_BASE_URL, 'https://example.com/img']\n"
        "  emoji:\n"
        "    index: !!python/name:material.extensions.emoji.twemoji\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(mky, "MKDOCS_YML", yml)
    # !ENV [NAME, default] resolves to the default; python:name is tolerated
    assert mky.load_extra("bucket")["base_url"] == "https://example.com/img"


def test_load_extra_parse_error_degrades(tmp_path, monkeypatch, capsys):
    yml = tmp_path / "mkdocs.yml"
    yml.write_text("extra:\n  bucket: [unclosed\n", encoding="utf-8")
    monkeypatch.setattr(mky, "MKDOCS_YML", yml)
    assert mky.load_extra("bucket") == {}
    assert "cannot parse" in capsys.readouterr().err


def test_load_extra_parse_error_strict_raises(tmp_path, monkeypatch):
    yml = tmp_path / "mkdocs.yml"
    yml.write_text("extra:\n  bucket: [unclosed\n", encoding="utf-8")
    monkeypatch.setattr(mky, "MKDOCS_YML", yml)
    with pytest.raises(mky.MkdocsYamlError):
        mky.load_extra("bucket", strict=True)


def test_load_extra_non_mapping_shapes(tmp_path, monkeypatch, capsys):
    yml = tmp_path / "mkdocs.yml"
    # 'extra' itself is a scalar -> warn + degrade (non-strict)
    yml.write_text("extra: not-a-mapping\n", encoding="utf-8")
    monkeypatch.setattr(mky, "MKDOCS_YML", yml)
    assert mky.load_extra("bucket") == {}
    assert "not a mapping" in capsys.readouterr().err

    # 'extra.bucket' is a list -> warn + degrade
    yml.write_text("extra:\n  bucket: [1, 2]\n", encoding="utf-8")
    assert mky.load_extra("bucket") == {}
    assert "'extra.bucket' in" in capsys.readouterr().err

    # ... but strict mode raises instead
    with pytest.raises(mky.MkdocsYamlError):
        mky.load_extra("bucket", strict=True)


def test_load_extra_root_not_mapping(tmp_path, monkeypatch, capsys):
    yml = tmp_path / "mkdocs.yml"
    # root is a list (valid YAML, broken mkdocs) -> warn + degrade
    yml.write_text("- just\n- a list\n", encoding="utf-8")
    monkeypatch.setattr(mky, "MKDOCS_YML", yml)
    assert mky.load_extra("bucket") == {}
    assert "is not a mapping" in capsys.readouterr().err

    # strict raises instead
    with pytest.raises(mky.MkdocsYamlError):
        mky.load_extra("bucket", strict=True)

    # empty file stays silent (treated as absent)
    yml.write_text("", encoding="utf-8")
    assert mky.load_extra("bucket") == {}
    assert capsys.readouterr().err == ""
