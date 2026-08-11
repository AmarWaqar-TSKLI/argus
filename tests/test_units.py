"""Unit tests for Argus's deterministic core — no browser, no network, no models."""
import numpy as np
from PIL import Image

from argus.cv.dedup import is_near_duplicate, screenshot_hash
from argus.cv.visual_diff import baseline_path, compare
from argus.nodes.explorer import normalize
from argus.nodes.flows import _fill_value
from argus.providers import parse_json_array, text_of


def test_normalize_strips_fragment_and_trailing_slash():
    assert normalize("http://x.test/page/#section") == "http://x.test/page"
    assert normalize("http://x.test/") == "http://x.test"
    assert normalize("http://x.test/a?q=1") == "http://x.test/a?q=1"


def test_parse_json_array_tolerates_model_formatting():
    assert parse_json_array('[{"a": 1}]') == [{"a": 1}]
    assert parse_json_array('```json\n[{"a": 1}]\n```') == [{"a": 1}]
    assert parse_json_array('Sure! Here are the issues:\n[{"a": 1}] Hope that helps.') == [{"a": 1}]
    assert parse_json_array("no json here") == []
    assert parse_json_array('{"not": "an array"}') == []
    assert parse_json_array("[broken json") == []


def test_text_of_handles_content_blocks():
    assert text_of("plain") == "plain"
    assert text_of([{"type": "text", "text": "a"}, {"type": "text", "text": "b"}]) == "ab"


def test_fill_values_match_input_types():
    assert "@" in _fill_value("email")
    assert _fill_value("number").isdigit()
    assert _fill_value("mystery-type") == "Argus probe"


def test_baseline_path_slugs_are_filesystem_safe():
    p = baseline_path("http://127.0.0.1:5000/pricing/table?x=1")
    assert p.name == "127_0_0_1_5000_pricing_table.png"


def _write_png(path, arr):
    Image.fromarray(arr).save(path)


def test_visual_diff_flags_localized_change_not_noise(tmp_path):
    base = np.full((600, 800, 3), 255, dtype=np.uint8)
    same = base.copy()
    changed = base.copy()
    changed[100:220, 100:340] = 0  # a 120x240 black block appears

    _write_png(tmp_path / "base.png", base)
    _write_png(tmp_path / "same.png", same)
    _write_png(tmp_path / "changed.png", changed)

    score, hd, area = compare(str(tmp_path / "base.png"), str(tmp_path / "same.png"),
                              str(tmp_path / "d1.png"))
    assert score > 0.99 and area == 0 and hd == 0

    score, hd, area = compare(str(tmp_path / "base.png"), str(tmp_path / "changed.png"),
                              str(tmp_path / "d2.png"))
    assert area >= 1500  # the regression gate's signal
    assert (tmp_path / "d2.png").exists()


def test_phash_dedup_separates_different_screens(tmp_path):
    rng = np.random.default_rng(7)
    a = rng.integers(0, 255, (400, 600, 3), dtype=np.uint8)
    b = rng.integers(0, 255, (400, 600, 3), dtype=np.uint8)
    _write_png(tmp_path / "a.png", a)
    _write_png(tmp_path / "b.png", b)

    ha = screenshot_hash(str(tmp_path / "a.png"))
    hb = screenshot_hash(str(tmp_path / "b.png"))
    assert is_near_duplicate(ha, [ha])
    assert not is_near_duplicate(ha, [hb])
    assert not is_near_duplicate(ha, [])
