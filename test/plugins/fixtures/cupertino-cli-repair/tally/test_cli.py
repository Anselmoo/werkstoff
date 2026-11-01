from tally.cli import count_lines, count_words, main


def test_words():
    assert count_words("a b  c\nd") == 4


def test_lines():
    assert count_lines("a\nb\n") == 2


def test_main_words(tmp_path, capsys):
    f = tmp_path / "t.txt"
    f.write_text("one two", encoding="utf-8")
    assert main(["words", str(f)]) == 0
    assert capsys.readouterr().out.strip() == "2"
