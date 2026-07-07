# VAD Benchmark — common workflows
# Usage: `make <target>` (Windows: use `make` from Git Bash, or run via uv)

.PHONY: help install sync run serve test clean reset all

help:
	@echo "VAD Benchmark · make targets:"
	@echo ""
	@echo "  Local (host, uv):"
	@echo "    make install    - uv sync (install deps)"
	@echo "    make run        - run benchmark (writes reports/)"
	@echo "    make serve      - start dashboard on http://127.0.0.1:8770"
	@echo "    make test       - run smoke tests"
	@echo "    make clean      - delete reports/"
	@echo "    make reset      - clean + re-install"

install sync:
	uv sync

run:
	uv run python -m scripts.run_benchmark

# Override configs from CLI: `make run ARGS="--config name=silero_t07,vad_threshold=0.7"`
run-args:
	uv run python -m scripts.run_benchmark $(ARGS)

serve:
	uv run vad-bench-serve

test smoke:
	uv sync --extra dev
	.venv/Scripts/python.exe -m pytest tests/ -v

clean:
	rm -rf reports/summary.json reports/summary.csv reports/per_config reports/reference reports/history reports/.run_status.json

reset: clean
	uv sync --reinstall

all: install run serve