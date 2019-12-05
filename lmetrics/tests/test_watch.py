import asyncio
from pathlib import Path
from typing import (
    Callable,
    NamedTuple,
)

import pytest

from ..watch import (
    create_watchers,
    FileWatcher,
    WatchedFiles,
)


class FakeAnalyzer(NamedTuple):

    path: str
    analyze_line: Callable[[str], None]


@pytest.fixture
def watched_dir(tmpdir):
    watched_dir = Path(tmpdir / "dir")
    watched_dir.mkdir()
    yield watched_dir


@pytest.fixture
def watched_file(watched_dir):
    yield watched_dir / "file.txt"


@pytest.fixture
def analyze_calls():
    yield []


@pytest.fixture
def watcher(event_loop, watched_file, analyze_calls):
    yield FileWatcher(watched_file, analyze_calls.append, loop=event_loop)


@pytest.mark.asyncio
class TestFileWatcher:
    async def test_file_already_exists(self, watched_file, watcher, analyze_calls):
        """If the file already exists, its content is read."""
        watched_file.write_text("line1\nline2\n")
        watcher.watch()
        await asyncio.sleep(0.1)  # let the loop run
        await watcher.stop()
        assert analyze_calls == ["line1", "line2"]

    async def test_file_created_later(self, watched_file, watcher, analyze_calls):
        """If the file doesn't exist upfront, it's read once it's created."""
        watcher.watch()
        watched_file.write_text("line1\nline2\n")
        await asyncio.sleep(0.1)  # let the loop run
        await watcher.stop()
        assert analyze_calls == ["line1", "line2"]

    async def test_file_appended(self, watched_file, watcher, analyze_calls):
        """If content is appended to a file, new content is read."""
        watched_file.write_text("line1\nline2\n")
        watcher.watch()
        await asyncio.sleep(0.1)  # let the loop run
        # the original content is read
        assert analyze_calls == ["line1", "line2"]

        # append content to the file
        with watched_file.open("a") as fd:
            fd.write("line3\nline4\n")
        await asyncio.sleep(0.1)  # let the loop run
        await watcher.stop()
        assert analyze_calls == ["line1", "line2", "line3", "line4"]

    async def test_file_appended_open(self, watched_file, watcher, analyze_calls):
        """If new content is appended to an open file, it's read."""
        with watched_file.open("w") as fd:
            watcher.watch()
            fd.write("line1\nline2\n")
            fd.flush()
            await asyncio.sleep(0.1)  # let the loop run
            # the original content is read
            assert analyze_calls == ["line1", "line2"]

            fd.write("line3\nline4\n")

        await asyncio.sleep(0.1)  # let the loop run
        await watcher.stop()
        assert analyze_calls == ["line1", "line2", "line3", "line4"]

    async def test_file_renamed_to_watched(
        self, watched_dir, watched_file, watcher, analyze_calls
    ):
        """If a file gets renamed to the watched name, its content is read."""
        old_file = watched_dir / "file2.txt"
        old_file.write_text("line1\nline2\n")
        watcher.watch()
        await asyncio.sleep(0.1)  # let the loop run
        # no content is read from the other file
        assert analyze_calls == []
        old_file.rename(watched_file)
        await asyncio.sleep(0.1)  # let the loop run
        await watcher.stop()
        assert analyze_calls == ["line1", "line2"]

    async def test_file_renamed_from_watched(
        self, watched_dir, watched_file, watcher, analyze_calls
    ):
        """If a file gets renamed, its content is no longer read."""
        watched_file.write_text("line1\nline2\n")
        watcher.watch()
        await asyncio.sleep(0.1)  # let the loop run
        assert analyze_calls == ["line1", "line2"]
        new_file = watched_dir / "file2.txt"
        watched_file.rename(new_file)
        await asyncio.sleep(0.1)  # let the loop run
        # append content to the new file
        with new_file.open("a") as fd:
            fd.write("line3\nline4\n")
        await asyncio.sleep(0.1)  # let the loop run
        await watcher.stop()
        assert analyze_calls == ["line1", "line2"]

    async def test_file_recreated(self, watched_file, watcher, analyze_calls):
        """If a file is removed and created again, new content is read."""
        watched_file.write_text("line1\nline2\n")
        watcher.watch()
        await asyncio.sleep(0.1)  # let the loop run
        # the original content is read
        assert analyze_calls == ["line1", "line2"]

        # delete and recreate the file
        watched_file.unlink()
        watched_file.write_text("line3\nline4\n")
        await asyncio.sleep(0.1)  # let the loop run
        await watcher.stop()
        assert analyze_calls == ["line1", "line2", "line3", "line4"]


@pytest.fixture
async def glob_watcher(event_loop, watched_dir, analyze_calls):
    glob_path = watched_dir / "file*.txt"
    watcher = FileWatcher(glob_path, analyze_calls.append, loop=event_loop)
    yield watcher
    await watcher.stop()


@pytest.mark.asyncio
class TestFileWatcherGlob:
    async def test_glob_match(self, watched_dir, glob_watcher, analyze_calls):
        """All files whose name matches the glob pattern are read."""
        (watched_dir / "file1.txt").write_text("file1\n")
        (watched_dir / "file2.txt").write_text("file2\n")
        (watched_dir / "other.txt").write_text("other\n")
        glob_watcher.watch()
        await asyncio.sleep(0.1)  # let the loop run
        # only lines from matched files are present
        assert sorted(analyze_calls) == ["file1", "file2"]

    async def test_glob_match_file_created_after(
        self, watched_dir, glob_watcher, analyze_calls
    ):
        """Created files whose name match are read."""
        glob_watcher.watch()
        (watched_dir / "file.txt").write_text("file\n")
        (watched_dir / "other.txt").write_text("other\n")
        await asyncio.sleep(0.1)  # let the loop run
        # only the matching file has been read
        assert analyze_calls == ["file"]

    async def test_file_renamed_matching_read(
        self, watched_dir, glob_watcher, analyze_calls
    ):
        """If a file is renamed to match the pattern, it's read."""
        other_file = watched_dir / "other.txt"
        other_file.write_text("some content\n")
        glob_watcher.watch()
        await asyncio.sleep(0.1)  # let the loop run
        # nothing is read so far
        assert analyze_calls == []

        other_file.rename(watched_dir / "file.txt")
        await asyncio.sleep(0.1)  # let the loop run
        # the file is now read
        assert analyze_calls == ["some content"]

    async def test_file_renamed_not_matching_not_read(
        self, watched_dir, watched_file, glob_watcher, analyze_calls
    ):
        """If a file is renamed not to match the pattern it's not read."""
        watched_file.write_text("some content\n")
        glob_watcher.watch()
        await asyncio.sleep(0.1)  # let the loop run
        assert analyze_calls == ["some content"]

        # rename the file
        new_file = watched_dir / "other.txt"
        watched_file.rename(new_file)
        await asyncio.sleep(0.1)  # let the loop run

        # append content to the new file
        with new_file.open("a") as fd:
            fd.write("more content\n")
        await asyncio.sleep(0.1)  # let the loop run

        # the new content is not read
        assert analyze_calls == ["some content"]

    async def test_file_renamed_still_match_not_read(
        self, watched_dir, watched_file, glob_watcher, analyze_calls
    ):
        """If the filename still matches after rename, it's not read again."""
        watched_file.write_text("some content\n")
        glob_watcher.watch()
        await asyncio.sleep(0.1)  # let the loop run
        assert analyze_calls == ["some content"]

        # rename the file, new name still matches the glob
        new_file = watched_dir / "file-new.txt"
        watched_file.rename(new_file)
        await asyncio.sleep(0.1)  # let the loop run

        # the new content is not read again
        assert analyze_calls == ["some content"]

    async def test_file_renamed_still_match_new_content_read(
        self, watched_dir, watched_file, glob_watcher, analyze_calls
    ):
        """If content is appended to the renamed matching file, it's read."""
        watched_file.write_text("some content\n")
        glob_watcher.watch()
        await asyncio.sleep(0.1)  # let the loop run
        assert analyze_calls == ["some content"]

        # rename the file, new name still matches the glob
        new_file = watched_dir / "file-new.txt"
        watched_file.rename(new_file)
        await asyncio.sleep(0.1)  # let the loop run

        # append content to the new file
        with new_file.open("a") as fd:
            fd.write("more content\n")
        await asyncio.sleep(0.1)  # let the loop run

        # the new content is is read
        assert analyze_calls == ["some content", "more content"]


class TestCreateWatchers:
    def test_create_watchers(self):
        """create_watchers return a FileWatcher for each analyzer."""
        fake_loop = object()
        analyzer1 = FakeAnalyzer("file1", lambda line: True)
        analyzer2 = FakeAnalyzer("file2", lambda line: True)
        watcher1, watcher2 = create_watchers([analyzer1, analyzer2], fake_loop)
        assert watcher1.path == Path.cwd() / "file1"
        assert watcher2.path == Path.cwd() / "file2"


@pytest.fixture
def files():
    yield WatchedFiles()


class TestWatchedFiles:
    def test_set_add(self, files):
        """The set method adds an entry."""
        entry = files.set("file.txt")
        assert entry == {"path": "file.txt", "fd": None, "wd": None}

    def test_set_with_values(self, files):
        """The set method adds an entry with specified values."""
        entry = files.set("file.txt", fd=1, wd=2)
        assert entry == {"path": "file.txt", "fd": 1, "wd": 2}

    def test_set_update(self, files):
        """The set method updates an entry if it's already there."""
        files.set("file.txt", fd=1, wd=2)
        entry = files.set("file.txt", fd=3, wd=4)
        assert entry == {"path": "file.txt", "fd": 3, "wd": 4}

    def test_set_update_only_specified(self, files):
        """The set method updates only specified values for the entry."""
        files.set("file.txt", fd=1, wd=2)
        entry = files.set("file.txt", fd=3)
        assert entry == {"path": "file.txt", "fd": 3, "wd": 2}
        entry = files.set("file.txt", wd=4)
        assert entry == {"path": "file.txt", "fd": 3, "wd": 4}

    def test_set_update_to_none(self, files):
        """The set method can set updated values to None."""
        files.set("file.txt", fd=1, wd=2)
        entry = files.set("file.txt", fd=None, wd=None)
        assert entry == {"path": "file.txt", "fd": None, "wd": None}

    def test_get_by_path(self, files):
        """It's possible to get items by path."""
        files.set("file.txt", fd=1, wd=2)
        entry = files["file.txt"]
        assert entry == {"path": "file.txt", "fd": 1, "wd": 2}

    def test_get_by_watcher_descriptor(self, files):
        """It's possible to get items by watcher descriptor."""
        files.set("file.txt", fd=1, wd=2)
        entry = files[2]
        assert entry == {"path": "file.txt", "fd": 1, "wd": 2}

    def test_get_unknown(self, files):
        """Getting an unknown key returns None."""
        assert files["not-here.txt"] is None
        assert files[12] is None

    def test_del_by_path(self, files):
        """It's possible to remove an item by path."""
        files.set("file.txt", fd=1, wd=2)
        del files["file.txt"]
        assert files["file.txt"] is None
        assert files[2] is None

    def test_del_by_wd(self, files):
        """It's possible to remove an item by watch descriptor."""
        files.set("file.txt", fd=1, wd=2)
        del files[2]
        assert files["file.txt"] is None
        assert files[2] is None

    def test_contains(self, files):
        """It's possible to check if an element is contained in the set."""
        files.set("file.txt", fd=1, wd=2)
        assert "file.txt" in files
        assert 2 in files
        assert "not-here.txt" not in files
        assert 33 not in files

    def test_paths(self, files):
        """The paths method returns an iterator yielding path names."""
        files.set("file1.txt")
        files.set("file2.txt")
        assert files.paths() == {"file1.txt", "file2.txt"}

    def test_wds(self, files):
        """The wds method returns an iterator yielding watch descriptors."""
        files.set("file1.txt", wd=1)
        files.set("file2.txt", wd=2)
        assert files.wds() == {1, 2}
