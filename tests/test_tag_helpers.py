import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from BrawlBotSlashTags.brawlbotslashtags import SlashTags


def test_chunk_embed_text_preserves_newlines():
    helper = SlashTags.__new__(SlashTags)
    text = "This is line one.\n\nThis is line two. " * 200
    chunks = helper._chunk_embed_text(text)

    assert chunks
    assert all(len(chunk) <= 4000 for chunk in chunks)
    assert any("\n\n" in chunk for chunk in chunks)


def test_duplicate_tag_name_detection():
    helper = SlashTags.__new__(SlashTags)
    data = {
        "alpha": {"shared": "value"},
        "beta": {"shared": "value2"},
    }

    assert helper._has_duplicate_tag_name(data, "shared") is True


if __name__ == "__main__":
    test_chunk_embed_text_preserves_newlines()
    test_duplicate_tag_name_detection()
    print("tag helper tests passed")
