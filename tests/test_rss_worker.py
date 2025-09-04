import os
import tempfile
import importlib
import sys
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).resolve().parent.parent))


@pytest.fixture(scope="module")
def rw_module():
    tmpdir = tempfile.mkdtemp()
    os.environ["DATA_DIR"] = tmpdir

    import bot.db as db
    importlib.reload(db)
    db.init_db()

    import bot.rss_worker as rw
    importlib.reload(rw)
    return rw, db


@pytest.mark.parametrize("tag,attr", [
    ("enclosure", "url"),
    ("enclosure", "href"),
    ("media:content", "url"),
    ("media:content", "href"),
])
def test_extract_items_media_url(rw_module, tag, attr):
    rw, _ = rw_module
    xml = (
        "<rss><channel><item><title>t</title>"
        f"<{tag} {attr}='http://example.com/img.jpg'/></item></channel></rss>"
    )
    items = rw._extract_items(xml)
    assert items[0]["media_url"] == "http://example.com/img.jpg"


def test_insert_draft_uses_photo_content_type(rw_module):
    rw, db = rw_module
    draft_id = rw._insert_draft(
        text="hello",
        media_url="http://example.com/img.jpg",
        source_url="http://example.com",
        hash_hex="hash",
    )
    row = db.fetchone("SELECT content_type, media_url FROM drafts WHERE id=?", (draft_id,))
    assert row == ("photo", "http://example.com/img.jpg")

