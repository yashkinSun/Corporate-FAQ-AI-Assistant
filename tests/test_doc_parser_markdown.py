import sys
import textwrap
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from retrieval.doc_parser import parse_document, parse_markdown


def test_parse_markdown_normalizes_content(tmp_path):
    markdown_content = textwrap.dedent(
        """
        # Заголовок 1
        ## Заголовок 2

        Вступление с [ссылкой](https://example.com) и <b>жирным</b> HTML.

        - Первый пункт
        * Второй пункт
        1. Номер один
        2. Номер два

        | Имя | Значение |
        | --- | --- |
        | Foo | Bar |

        Просто текстовая строка.
        """
    ).strip()

    file_path = tmp_path / "sample.md"
    file_path.write_text(markdown_content, encoding="utf-8")

    parsed = parse_markdown(str(file_path))

    expected = textwrap.dedent(
        """
        Заголовок 1
        Заголовок 2

        Вступление с ссылкой (https://example.com) и жирным HTML.

        - Первый пункт
        - Второй пункт
        1. Номер один
        1. Номер два

        Имя | Значение
        Foo | Bar

        Просто текстовая строка.
        """
    ).strip()

    assert parsed == expected


def test_parse_document_dispatches_markdown(tmp_path):
    file_path = tmp_path / "notes.markdown"
    file_path.write_text("# Заголовок\n- пункт", encoding="utf-8")

    parsed = parse_document(str(file_path))

    assert parsed.startswith("Заголовок")
    assert "- пункт" in parsed
