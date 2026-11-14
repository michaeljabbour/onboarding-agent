PYTHON ?= python3

.PHONY: check test build start

check:
	$(PYTHON) scripts/build.py --check
	$(PYTHON) scripts/check-public.py

test:
	$(PYTHON) -m unittest discover -s tests -p 'test_*.py' -v

build:
	$(PYTHON) scripts/build.py

start:
	bash START.sh
