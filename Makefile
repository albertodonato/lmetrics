PYTHON = python3
SETUP = $(PYTHON) setup.py


build:
	$(SETUP) build

devel:
	$(SETUP) develop

clean:
	rm -rf build html *.egg-info
	find . -type d -name __pycache__ | xargs rm -rf

test:
	@$(PYTHON) -m unittest

coverage:
	@coverage run -m unittest
	@coverage report --show-missing --skip-covered --fail-under=100 \
		--include=lmetrics/* --omit=**/test_\*.py --omit=lmetrics/main.py

lint:
	@flake8 setup.py lmetrics

html:
	sphinx-build -b html docs html

.PHONY: build devel clean test coverage lint html
