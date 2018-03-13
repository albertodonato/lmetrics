from pathlib import Path
from setuptools import (
    find_packages,
    setup,
)

from lmetrics import (
    __doc__ as description,
    __version__,
)

tests_require = ['asynctest', 'fixtures']

config = {
    'name': 'lmetrics',
    'version': __version__,
    'license': 'GPLv3+',
    'description': description,
    'long_description': Path('README.rst').read_text(),
    'author': 'Alberto Donato',
    'author_email': 'alberto.donato@gmail.com',
    'maintainer': 'Alberto Donato',
    'maintainer_email': 'alberto.donato@gmail.com',
    'url': 'https://github.com/albertodonato/lmetrics',
    'packages': find_packages(),
    'include_package_data': True,
    'entry_points': {'console_scripts': [
        'lmetrics = lmetrics.main:script']},
    'test_suite': 'lmetrics',
    'install_requires': [
        'aiohttp',
        'butter <= 0.12.3',
        'lupa',
        'prometheus-client',
        'PyYaml',
        'prometheus-aioexporter >= 1.4.0',
        'toolrack >= 2.0.1'],
    'tests_require': tests_require,
    'extras_require': {'testing': tests_require},
    'keywords': 'log metric prometheus exporter',
    'classifiers': [
        'Development Status :: 3 - Alpha',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: GNU General Public License (GPL)',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python :: 3.5',
        'Topic :: Utilities']}

setup(**config)
