import os
from collections import namedtuple
import unittest
import asyncio
import shutil

import asynctest

from toolrack.testing import (
    TempDirFixture,
    TestCase as ToolrackTestCase)

from ..watch import (
    FileWatcher,
    create_watchers,
    WatchedFiles)


FakeAnalyzer = namedtuple('FakeAnalyzer', ['filename', 'analyze_line'])


class FileWatcherTests(asynctest.TestCase, ToolrackTestCase):

    def setUp(self):
        super().setUp()
        self.dir = self.useFixture(TempDirFixture())
        self.filename = os.path.join(self.dir.path, 'file.txt')
        self.calls = []
        self.watcher = FileWatcher(
            self.filename, self.calls.append, loop=self.loop)

    async def test_file_already_exists(self):
        """If the file already exists, its content is read."""
        self.dir.mkfile(path='file.txt', content='line1\nline2\n')
        self.watcher.watch()
        await asyncio.sleep(0.1)  # let the loop run
        await self.watcher.stop()
        self.assertEqual(self.calls, ['line1', 'line2'])

    async def test_file_created_later(self):
        """If the file doesn't exist upfront, it's read once it's created."""
        self.watcher.watch()
        self.dir.mkfile(path='file.txt', content='line1\nline2\n')
        await asyncio.sleep(0.1)  # let the loop run
        await self.watcher.stop()
        self.assertEqual(self.calls, ['line1', 'line2'])

    async def test_file_appended(self):
        """If content is appended to a file, new content is read."""
        self.dir.mkfile(path='file.txt', content='line1\nline2\n')
        self.watcher.watch()
        await asyncio.sleep(0.1)  # let the loop run
        # the original content is read
        self.assertEqual(self.calls, ['line1', 'line2'])

        # append content to the file
        with open(self.filename, 'a') as fd:
            fd.write('line3\nline4\n')
        await asyncio.sleep(0.1)  # let the loop run
        await self.watcher.stop()
        self.assertEqual(self.calls, ['line1', 'line2', 'line3', 'line4'])

    async def test_file_appended_open(self):
        """If new content is appended to an open file, it's read."""
        with open(self.dir.mkfile(path='file.txt'), 'w') as fd:
            self.watcher.watch()
            fd.write('line1\nline2\n')
            fd.flush()
            await asyncio.sleep(0.1)  # let the loop run
            # the original content is read
            self.assertEqual(self.calls, ['line1', 'line2'])

            fd.write('line3\nline4\n')

        await asyncio.sleep(0.1)  # let the loop run
        await self.watcher.stop()
        self.assertEqual(self.calls, ['line1', 'line2', 'line3', 'line4'])

    async def test_file_renamed_to_watched(self):
        """If a file gets renamed to the watched name, its content is read."""
        file2 = self.dir.mkfile(path='file2.txt', content='line1\nline2\n')
        self.watcher.watch()
        await asyncio.sleep(0.1)  # let the loop run
        # no content is read from the other file
        self.assertEqual(self.calls, [])

        shutil.move(file2, self.filename)
        await asyncio.sleep(0.1)  # let the loop run
        await self.watcher.stop()
        self.assertEqual(self.calls, ['line1', 'line2'])

    async def test_file_renamed_from_watched(self):
        """If a file gets renamed, its content is no longer read."""
        self.dir.mkfile(path='file.txt', content='line1\nline2\n')
        self.watcher.watch()
        await asyncio.sleep(0.1)  # let the loop run
        self.assertEqual(self.calls, ['line1', 'line2'])
        new_filename = os.path.join(self.dir.path, 'file2.txt')
        shutil.move(self.filename, new_filename)
        await asyncio.sleep(0.1)  # let the loop run
        # append content to the new file
        with open(new_filename, 'a') as fd:
            fd.write('line3\nline4\n')
        await asyncio.sleep(0.1)  # let the loop run
        await self.watcher.stop()
        self.assertEqual(self.calls, ['line1', 'line2'])

    async def test_file_recreated(self):
        """If a file is removed and created again, new content is read."""
        self.dir.mkfile(path='file.txt', content='line1\nline2\n')
        self.watcher.watch()
        await asyncio.sleep(0.1)  # let the loop run
        # the original content is read
        self.assertEqual(self.calls, ['line1', 'line2'])

        # delete and recreate the file
        os.unlink(self.filename)
        self.dir.mkfile(path='file.txt', content='line3\nline4\n')
        await asyncio.sleep(0.1)  # let the loop run
        await self.watcher.stop()
        self.assertEqual(self.calls, ['line1', 'line2', 'line3', 'line4'])


class FileWatcherGlobTests(asynctest.TestCase, ToolrackTestCase):

    def setUp(self):
        super().setUp()
        self.dir = self.useFixture(TempDirFixture())
        self.calls = []
        glob_path = os.path.join(self.dir.path, 'file*.txt')
        self.watcher = FileWatcher(
            glob_path, self.calls.append, loop=self.loop)

    async def test_glob_match(self):
        """All files whose name matches the glob pattern are read."""
        self.dir.mkfile(path='file1.txt', content='file1\n')
        self.dir.mkfile(path='file2.txt', content='file2\n')
        self.dir.mkfile(path='other.txt', content='other\n')
        self.watcher.watch()
        await asyncio.sleep(0.1)  # let the loop run
        # only lines from matched files are present
        self.assertCountEqual(self.calls, ['file1', 'file2'])
        await self.watcher.stop()

    async def test_glob_match_file_created_after(self):
        """Created files whose name match are read."""
        self.watcher.watch()
        self.dir.mkfile(path='file.txt', content='file\n')
        self.dir.mkfile(path='other.txt', content='other\n')
        await asyncio.sleep(0.1)  # let the loop run
        # only the matching file has been read
        self.assertEqual(self.calls, ['file'])
        await self.watcher.stop()

    async def test_file_renamed_matching_read(self):
        """If a file is renamed to match the pattern, it's read."""
        other_filename = self.dir.mkfile(
            path='other.txt', content='some content\n')
        self.watcher.watch()
        await asyncio.sleep(0.1)  # let the loop run
        # nothing is read so far
        self.assertEqual(self.calls, [])

        new_filename = os.path.join(self.dir.path, 'file.txt')
        shutil.move(other_filename, new_filename)
        await asyncio.sleep(0.1)  # let the loop run
        # the file is now read
        self.assertEqual(self.calls, ['some content'])
        await self.watcher.stop()

    async def test_file_renamed_not_matching_not_read(self):
        """If a file is renamed not to match the pattern it's not read."""
        filename = self.dir.mkfile(path='file.txt', content='some content\n')
        self.watcher.watch()
        await asyncio.sleep(0.1)  # let the loop run
        # nothing is read so far
        self.assertEqual(self.calls, ['some content'])

        # rename the file
        new_filename = os.path.join(self.dir.path, 'other.txt')
        shutil.move(filename, new_filename)
        await asyncio.sleep(0.1)  # let the loop run

        # append content to the new file
        with open(new_filename, 'a') as fd:
            fd.write('more content\n')
        await asyncio.sleep(0.1)  # let the loop run

        # the new content is not read
        self.assertEqual(self.calls, ['some content'])
        await self.watcher.stop()

    async def test_file_renamed_still_match_not_read(self):
        """If the filename still matches after rename, it's not read again."""
        filename = self.dir.mkfile(path='file.txt', content='some content\n')
        self.watcher.watch()
        await asyncio.sleep(0.1)  # let the loop run
        # nothing is read so far
        self.assertEqual(self.calls, ['some content'])

        # rename the file, new name still matches the glob
        new_filename = os.path.join(self.dir.path, 'file-new.txt')
        shutil.move(filename, new_filename)
        await asyncio.sleep(0.1)  # let the loop run

        # the new content is not read again
        self.assertEqual(self.calls, ['some content'])
        await self.watcher.stop()

    async def test_file_renamed_still_match_new_content_read(self):
        """If content is appended to the renamed matching file, it's read."""
        filename = self.dir.mkfile(path='file.txt', content='some content\n')
        self.watcher.watch()
        await asyncio.sleep(0.1)  # let the loop run
        # nothing is read so far
        self.assertEqual(self.calls, ['some content'])

        # rename the file, new name still matches the glob
        new_filename = os.path.join(self.dir.path, 'file-new.txt')
        shutil.move(filename, new_filename)
        await asyncio.sleep(0.1)  # let the loop run

        # append content to the new file
        with open(new_filename, 'a') as fd:
            fd.write('more content\n')
        await asyncio.sleep(0.1)  # let the loop run

        # the new content is is read
        self.assertEqual(self.calls, ['some content', 'more content'])
        await self.watcher.stop()


class CreateWatchersTests(unittest.TestCase):

    def test_create_watchers(self):
        """create_watchers return a FileWatcher for each analyzer."""
        fake_loop = object()
        analyzer1 = FakeAnalyzer('file1', lambda: True)
        analyzer2 = FakeAnalyzer('file2', lambda: True)
        watcher1, watcher2 = create_watchers([analyzer1, analyzer2], fake_loop)
        cwd = os.getcwd()
        self.assertEqual(watcher1.full_path, os.path.join(cwd, 'file1'))
        self.assertEqual(watcher2.full_path, os.path.join(cwd, 'file2'))


class WatchedFilesTests(unittest.TestCase):

    def setUp(self):
        super().setUp()
        self.files = WatchedFiles()

    def test_set_add(self):
        """The set method adds an entry."""
        entry = self.files.set('file.txt')
        self.assertEqual(entry, {'path': 'file.txt', 'fd': None, 'wd': None})

    def test_set_with_values(self):
        """The set method adds an entry with specified values."""
        entry = self.files.set('file.txt', fd=1, wd=2)
        self.assertEqual(entry, {'path': 'file.txt', 'fd': 1, 'wd': 2})

    def test_set_update(self):
        """The set method updates an entry if it's already there."""
        self.files.set('file.txt', fd=1, wd=2)
        entry = self.files.set('file.txt', fd=3, wd=4)
        self.assertEqual(entry, {'path': 'file.txt', 'fd': 3, 'wd': 4})

    def test_set_update_only_specified(self):
        """The set method updates only specified values for the entry."""
        self.files.set('file.txt', fd=1, wd=2)
        entry = self.files.set('file.txt', fd=3)
        self.assertEqual(entry, {'path': 'file.txt', 'fd': 3, 'wd': 2})
        entry = self.files.set('file.txt', wd=4)
        self.assertEqual(entry, {'path': 'file.txt', 'fd': 3, 'wd': 4})

    def test_set_update_to_none(self):
        """The set method can set updated values to None."""
        self.files.set('file.txt', fd=1, wd=2)
        entry = self.files.set('file.txt', fd=None, wd=None)
        self.assertEqual(entry, {'path': 'file.txt', 'fd': None, 'wd': None})

    def test_get_by_path(self):
        """It's possible to get items by path."""
        self.files.set('file.txt', fd=1, wd=2)
        entry = self.files['file.txt']
        self.assertEqual(entry, {'path': 'file.txt', 'fd': 1, 'wd': 2})

    def test_get_by_watcher_descriptor(self):
        """It's possible to get items by watcher descriptor."""
        self.files.set('file.txt', fd=1, wd=2)
        entry = self.files[2]
        self.assertEqual(entry, {'path': 'file.txt', 'fd': 1, 'wd': 2})

    def test_get_unknown(self):
        """Getting an unknown key returns None."""
        self.assertIsNone(self.files['not-here.txt'])
        self.assertIsNone(self.files[12])

    def test_del_by_path(self):
        """It's possible to remove an item by path."""
        self.files.set('file.txt', fd=1, wd=2)
        del self.files['file.txt']
        self.assertIsNone(self.files['file.txt'])
        self.assertIsNone(self.files[2])

    def test_del_by_wd(self):
        """It's possible to remove an item by watch descriptor."""
        self.files.set('file.txt', fd=1, wd=2)
        del self.files[2]
        self.assertIsNone(self.files['file.txt'])
        self.assertIsNone(self.files[2])

    def test_contains(self):
        """It's possible to check if an element is contained in the set."""
        self.files.set('file.txt', fd=1, wd=2)
        self.assertIn('file.txt', self.files)
        self.assertIn(2, self.files)
        self.assertNotIn('not-here.txt', self.files)
        self.assertNotIn(33, self.files)

    def test_paths(self):
        """The paths method returns an iterator yielding path names."""
        self.files.set('file1.txt')
        self.files.set('file2.txt')
        self.assertCountEqual(self.files.paths(), {'file1.txt', 'file2.txt'})

    def test_wds(self):
        """The wds method returns an iterator yielding watch descriptors."""
        self.files.set('file1.txt', wd=1)
        self.files.set('file2.txt', wd=2)
        self.assertCountEqual(self.files.wds(), {1, 2})
