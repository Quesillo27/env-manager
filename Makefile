.PHONY: install run test clean

install:
	pip install -r requirements.txt
	pip install -e .

run:
	env-manager --help

test:
	python3 -m pytest tests/ -v

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete
	rm -rf *.egg-info dist build .pytest_cache
