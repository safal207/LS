.PHONY: grant-evidence clean-grant-evidence

PYTHON ?= python3
PYTEST ?= pytest
GRANT_EVIDENCE_DIR ?= reports/grant_evidence

grant-evidence:
	mkdir -p $(GRANT_EVIDENCE_DIR)
	$(PYTHON) scripts/run_personal_cognitive_garden_demo.py --json > $(GRANT_EVIDENCE_DIR)/pcg_demo_output.json
	$(PYTHON) scripts/run_pcg_red_team.py --json > $(GRANT_EVIDENCE_DIR)/pcg_red_team_block_output.json
	$(PYTHON) scripts/run_pcg_evaluation.py --json > $(GRANT_EVIDENCE_DIR)/pcg_evaluation_report.json
	PYTHONPATH=. $(PYTEST) tests/test_pcg_grant_evidence_artifacts.py -q > $(GRANT_EVIDENCE_DIR)/pcg_governance_tests.txt
	$(PYTHON) scripts/render_grant_evidence_summary.py \
		--input-dir $(GRANT_EVIDENCE_DIR) \
		--output $(GRANT_EVIDENCE_DIR)/grant_evidence_summary.md

clean-grant-evidence:
	rm -rf $(GRANT_EVIDENCE_DIR)
