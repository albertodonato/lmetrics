import asyncio
import contextlib
from pathlib import Path

from butter.asyncio.inotify import Inotify_async
from butter.inotify import (
    IN_CREATE,
    IN_DELETE,
    IN_MOVED_FROM,
    IN_MOVED_TO,
    IN_MODIFY,
)
from toolrack.async import StreamHelper
from toolrack.log import Loggable


class FileWatcher(Loggable):
    """Watch a file with inotify and call back with every line."""

    _task = None

    def __init__(self, path, callback, encoding='utf-8', loop=None):
        self.loop = loop or asyncio.get_event_loop()
        self.path = Path(path).absolute()
        self.name = str(self.path)  # for the logger
        self._encoding = encoding
        self._stream = StreamHelper(callback=callback)
        self._files = WatchedFiles()
        self._move_cookies = set()

    def watch(self):
        """Start watching for the file."""
        self._task = self.loop.create_task(self._watch())
        return self._task

    async def stop(self):
        """Stop watching the file."""
        if self._task:
            self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass

        for file_path in self._files.paths():
            self._close_file(file_path)

        self.logger.debug('stop watch loop')

    async def _watch(self):
        with contextlib.closing(Inotify_async(loop=self.loop)) as inotify:
            self.logger.debug('start watch loop')
            await self._watch_loop(inotify)

    async def _watch_loop(self, inotify):
        # always watch the containing directory
        self._watch_dir(inotify)

        # split the basename which might contain glob chars
        for file_path in self.path.parent.glob(self.path.name):
            self._read_file_content(file_path, from_start=True)
            self._watch_file(inotify, file_path)

        while True:
            event = await inotify.get_event()
            if event.filename:
                # the event is for a file in the watched directory
                self._handle_dir_event(inotify, event)
            else:
                # the event is on a file
                self._handle_file_event(inotify, event)

    def _watch_dir(self, inotify):
        """Watch the containing dir."""
        self.logger.debug('watching directory {}'.format(self.path.parent))
        inotify.watch(
            str(self.path.parent),
            IN_CREATE | IN_MOVED_FROM | IN_MOVED_TO | IN_DELETE)

    def _watch_file(self, inotify, path):
        """Watch a file."""
        self.logger.debug('watching file {}'.format(path))
        wd = inotify.watch(str(path), IN_MODIFY)
        self._files.set(path, wd=wd)

    def _handle_dir_event(self, inotify, event):
        file_path = self.path.parent / event.filename.decode(self._encoding)
        if not file_path.match(str(self.path)):
            return
        if event.create_event or event.moved_to_event:
            if event.cookie in self._move_cookies:
                # the file has been moved within the watched dir, don't read
                # content again
                self._move_cookies.remove(event.cookie)
                self._skip_to_file_end(file_path)
            else:
                self._read_file_content(file_path, from_start=True)
            self._watch_file(inotify, file_path)
        elif event.moved_from_event:
            self.logger.debug('file moved {}'.format(file_path))
            inotify.ignore(self._files[file_path]['wd'])
            self._move_cookies.add(event.cookie)
            self._close_file(file_path)
            del self._files[file_path]
        elif event.delete_event:
            self.logger.debug('file removed: {}'.format(file_path))
            self._close_file(file_path)
            del self._files[file_path]

    def _handle_file_event(self, inotify, event):
        file_info = self._files[event.wd]
        if not file_info:
            return  # the file has been ignored or removed
        file_path = file_info['path']
        if event.modify_event:
            self.logger.debug('file modified: {}'.format(file_path))
            self._read_file_content(file_path)

    def _read_file_content(self, path, from_start=False):
        """Read and process content of the file."""
        if from_start:
            # force a close, in case file has been overwritten
            self._close_file(path)

        fd = self._get_file_fd(path)
        self._stream.receive_data(fd.read())

    def _skip_to_file_end(self, path):
        """Skip to the end of a file, leaving the file open."""
        fd = self._get_file_fd(path)
        fd.seek(0, 2)  # go the the end

    def _get_file_fd(self, path):
        """Return the file descriptor for a path."""
        file_info = self._files.set(path)
        fd = file_info['fd']
        if fd is None:
            fd = path.open(encoding=self._encoding)
            self._files.set(path, fd=fd)
        return fd

    def _close_file(self, path):
        """Close the file if open."""
        file_info = self._files[path]
        if not file_info:
            return

        fd = file_info['fd']
        if fd is not None:
            fd.close()
            self._files.set(path, fd=None)


def create_watchers(analyzers, loop):
    """Return a list of FileWatchers for FileAnalyzers."""
    return [
        FileWatcher(analyzer.path, analyzer.analyze_line, loop=loop)
        for analyzer in analyzers]


class WatchedFiles:
    """Track info about watched files."""

    _DEFAULT = object

    def __init__(self):
        self._wd_to_path = {}
        self._path_to_info = {}

    def set(self, path, wd=_DEFAULT, fd=_DEFAULT):
        """Set and return info about a watched file."""
        file_info = self._path_to_info.setdefault(
            path, {'path': path, 'wd': None, 'fd': None})

        # update only provided info
        if wd is not self._DEFAULT:
            file_info['wd'] = wd
        if fd is not self._DEFAULT:
            file_info['fd'] = fd

        if wd is None:
            self._wd_to_path.pop(wd, None)
        elif wd is not self._DEFAULT:
            self._wd_to_path[wd] = path

        return file_info

    def paths(self):
        """Return an iterator yielding file paths."""
        return self._path_to_info.keys()

    def wds(self):
        """Return an iterator yielding watch descriptors."""
        return self._wd_to_path.keys()

    def __getitem__(self, key):
        """Return info by watch descriptor or path."""
        if isinstance(key, int):
            return self._get_by_wd(key)
        return self._get_by_path(key)

    def __delitem__(self, key):
        """Delete an item by watch descriptor or path."""
        if isinstance(key, int):
            path = self._get_by_wd(key)['path']
            del self._wd_to_path[key]
        else:
            path = key

        del self._path_to_info[path]

    def __contains__(self, key):
        """Return whether info for a file is present."""
        if isinstance(key, int):
            return key in self._wd_to_path
        else:
            return key in self._path_to_info

    def _get_by_wd(self, wd):
        """Return info for a file by watch descriptor."""
        path = self._wd_to_path.get(wd)
        return self._get_by_path(path)

    def _get_by_path(self, path):
        """Return info for a file by path."""
        return self._path_to_info.get(path)
