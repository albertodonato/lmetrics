from functools import partial

from aiohttp.web import Application, Response

from prometheus_client import REGISTRY, generate_latest, CONTENT_TYPE_LATEST


HOMEPAGE = '''<!DOCTYPE html>
<html>
  <head>
    <title>LMetrics - Prometheus log metrics exporter</title>
  </head>
  <body>
    <h1>LMetrics - Prometheus log metrics exporter</h1>
    <p>Metric are exported at the <a href="/metrics">/metrics</a> endpoint.</p>
  </body>
</html>
'''


def create_web_app(loop, host, port, watchers):
    '''Create an aiohttp web application to export metrics.'''
    app = Application(loop=loop)
    app['endpoint'] = (host, port)

    app.router.add_get('/', _home)
    app.router.add_get('/metrics', _metrics)
    app.on_startup.append(partial(_start_watchers, watchers))
    app.on_startup.append(_log_startup_message)
    app.on_shutdown.append(partial(_stop_watchers, watchers))
    return app


async def _home(request):
    '''Home page request handler.'''
    return Response(content_type='text/html', text=HOMEPAGE)


async def _metrics(request):
    '''Handler for metrics.'''
    response = Response(body=generate_latest(REGISTRY))
    response.content_type = CONTENT_TYPE_LATEST
    return response


def _start_watchers(watchers, app):
    '''Start all FileWatchers.'''
    for watcher in watchers:
        watcher.watch()


async def _stop_watchers(watchers, app):
    '''Stop all FileWatchers.'''
    for watcher in watchers:
        await watcher.stop()


def _log_startup_message(app):
    '''Log message about application startup.'''
    app.logger.info('Listening on http://{}:{}'.format(*app['endpoint']))
