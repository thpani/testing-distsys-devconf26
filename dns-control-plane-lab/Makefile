.PHONY: test run clean

test:
	uv run python -m pytest -q

run:
	uv run uvicorn dns_control_plane.mbt_harness:app --reload --port 8000

clean:
	rm -rf .pytest_cache
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	rm -f s3-persistence/current_dns_zone.json s3-persistence/current_dns_zone.tmp
	rm -f s3-persistence/plans/plan-*.json
