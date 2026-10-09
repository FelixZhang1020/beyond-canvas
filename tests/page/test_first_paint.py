"""The scanner that writes the Chinese into the page before it is ever sent.

What can only go wrong here: a nested object's inner name quietly overwriting a
real key, a quote style the scanner cannot read, and a label with no Chinese
slipping through in English instead of stopping the build.
"""

import re
from pathlib import Path

import pytest

from tests.conftest import load_script

first_paint = load_script("studio/page/first_paint.py", "first_paint")


def test_both_quote_styles_and_bare_names_are_read():
    table = first_paint.chinese_table("""
        Studio.strings.zh = {
          "mode.feedback": "聊聊你的画",
          'mode.pose': '让画动起来',
          brand: "画里画外",
          2: '第二问',
        };
    """)
    assert table == {"mode.feedback": "聊聊你的画", "mode.pose": "让画动起来",
                     "brand": "画里画外", "2": "第二问"}


def test_a_nested_name_never_overwrites_the_key_it_shares():
    """`book: { title: ... }` holds a title of its own, and it is not the page's."""
    table = first_paint.chinese_table("""
        Studio.strings.zh = {
          title: "画里画外 Beyond Canvas",
          colours: { coral: '珊瑚红' },
          book: { title: '今天的故事', pages: ['从前', '接着'] },
          close: "关闭",
        };
    """)
    assert table["title"] == "画里画外 Beyond Canvas"
    assert table["close"] == "关闭", "the scan lost its place after a nested object"
    assert "coral" not in table and "pages" not in table


def test_a_comment_holding_an_apostrophe_does_not_swallow_the_file():
    table = first_paint.chinese_table("""
        Studio.strings.zh = {
          // the child's own words, not the model's
          "review.words": "孩子说的话",
        };
    """)
    assert table == {"review.words": "孩子说的话"}


def test_a_label_with_no_chinese_stops_the_build_and_names_itself():
    with pytest.raises(ValueError) as stopped:
        first_paint.fill('<span data-t="mode.pose">Pose preview</span>', {"brand": "画里画外"})
    assert "mode.pose" in str(stopped.value)


def test_text_that_would_break_the_markup_is_written_safely():
    filled = first_paint.fill('<span data-t="k">x</span>', {"k": "动作 & 光影 <新>"})
    assert filled == '<span data-t="k">动作 &amp; 光影 &lt;新&gt;</span>'


def test_an_example_is_written_into_the_box_that_has_none_yet():
    filled = first_paint.fill('<input data-t-ph="k">', {"k": "比如：今天画理发店"})
    assert 'placeholder="比如：今天画理发店"' in filled


def test_every_label_in_the_real_page_has_a_chinese_string():
    """The live check: the build would stop, so this says so first and by name."""
    page = Path("studio/page")
    table = first_paint.chinese_table((page / "locales/zh.js").read_text(encoding="utf-8"))
    markup = (page / "src/10-app.html").read_text(encoding="utf-8")
    keys = set(re.findall(r'\bdata-t(?:-ph)?="([\w.\-]+)"', markup))
    assert keys, "no labels found in the markup at all"
    assert sorted(k for k in keys if k not in table) == []


def test_a_label_only_a_screen_reader_hears_is_written_in_too():
    """Skipped when this was written, on the grounds that nobody sees it.

    A screen reader is somebody, and twenty-one of these sat in English in the
    markup until the page's script ran.
    """
    filled = first_paint.fill('<button data-t-aria="k" aria-label="Switch language"></button>',
                              {"k": "切换语言"})
    assert 'aria-label="切换语言"' in filled
    assert "Switch language" not in filled


def test_a_spoken_label_with_no_chinese_stops_the_build_too():
    with pytest.raises(ValueError) as stopped:
        first_paint.fill('<button data-t-aria="tool.lang"></button>', {"other": "x"})
    assert "tool.lang" in str(stopped.value)
