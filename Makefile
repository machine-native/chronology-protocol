.PHONY: test milestone audit miner clean

test:
	python -m pytest -q

milestone:
	python scripts/run_milestone1.py

audit:
	python scripts/release_audit.py

miner:
	cc -O3 -march=native native/mine_sha256d.c -lcrypto -o native/mine_sha256d

clean:
	rm -f native/mine_sha256d
	rm -rf .pytest_cache __pycache__ ctp/__pycache__ tests/__pycache__
