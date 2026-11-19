PYTHON ?= python3

.PHONY: check test test-ui build package start

check:
	$(PYTHON) scripts/build.py --check
	$(PYTHON) scripts/check-public.py

test:
	$(PYTHON) -m unittest discover -s tests -p 'test_*.py' -v

# Optional browser walk-through. Skips when Playwright is not available.
test-ui:
	node tests/browser/smoke.mjs

build:
	$(PYTHON) scripts/build.py

# A ZIP for outside testers. Their guide offers to open a GitHub issue on this repository.
# FEEDBACK_REPO defaults to the origin remote; override it with make package FEEDBACK_REPO=owner/name.
FEEDBACK_REPO ?= $(shell git remote get-url origin 2>/dev/null | sed -E 's|^.*github\.com[:/]||; s|\.git$$||')
package:
	$(PYTHON) scripts/build.py --feedback-repo "$(FEEDBACK_REPO)"

start:
	bash START.sh
