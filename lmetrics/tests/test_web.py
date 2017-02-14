from aiohttp.test_utils import (
    AioHTTPTestCase,
    unittest_run_loop)

from ..web import create_web_app


class FakeWatcher:

    watch_called = False
    stop_called = False

    def watch(self):
        self.watch_called = True

    async def stop(self):
        self.stop_called = True


class AppTestCase(AioHTTPTestCase):

    def setUp(self):
        self.watcher = FakeWatcher()
        super().setUp()

    def get_app(self, loop):
        return create_web_app(loop, 'localhost', 8000, [self.watcher])

    @unittest_run_loop
    async def test_watcher_start(self):
        '''Watchers are started when the app is stated.'''
        self.assertTrue(self.watcher.watch_called)

    @unittest_run_loop
    async def test_watcher_stop(self):
        '''Watchers are stopped when the app is shut down.'''
        await self.app.shutdown()
        self.assertTrue(self.watcher.stop_called)

    @unittest_run_loop
    async def test_homepage(self):
        '''The homepage shows an HTML page.'''
        request = await self.client.request('GET', '/')
        self.assertEqual(request.status, 200)
        self.assertEqual(request.content_type, 'text/html')
        text = await request.text()
        self.assertIn('LMetrics - Prometheus log metrics exporter', text)

    @unittest_run_loop
    async def test_metrics(self):
        '''The /metrics page display Prometheus metrics.'''
        request = await self.client.request('GET', '/metrics')
        self.assertEqual(request.status, 200)
        self.assertEqual(request.content_type, 'text/plain')
        text = await request.text()
        # the page includes metrics
        self.assertIn('process_open_fds', text)
