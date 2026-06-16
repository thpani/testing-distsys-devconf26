.PHONY: pbt pbt-deep spec-story mbt

PBT_TEST := pbt/test_dns_control_plane_root_resolvable.py
PBT_PYTEST := uv run --project pbt python -m pytest

MBT_TRACE := spec/n3_30_20_no_inconsistent_root_violation.itf.json

pbt:
	rm -rf .hypothesis
	$(PBT_PYTEST) -q $(PBT_TEST) --hypothesis-show-statistics

pbt-deep:
	rm -rf .hypothesis
	$(PBT_PYTEST) -p pbt.hypothesis_profiles -q $(PBT_TEST) --hypothesis-profile=deep --hypothesis-show-statistics

spec-story:
	cd spec && PYTHONPATH=. uv run pytest --codeblocks ../spec-story.md

mbt:
	cd dns-control-plane-lab && uv run python ../mbt/test_dns_control_plane_itf_replay.py ../$(MBT_TRACE)
