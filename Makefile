PYTHON ?= python

.PHONY: help test validate radio-cut film clean-tmp

help:
	@echo "Available targets:"
	@echo "  make test       - Run all offline unit & smoke tests"
	@echo "  make validate   - Validate storyboard.json against storyboard.schema.json"
	@echo "  make radio-cut  - Build placeholder/draft narration radio cut (no visual API calls)"
	@echo "  make film       - Run full pipeline assembly (requires FFmpeg and approved assets)"
	@echo "  make clean-tmp  - Remove temporary files in outputs/tmp"

test:
	$(PYTHON) -m unittest discover -s tests -v

validate:
	$(PYTHON) -m pipeline.cli validate

radio-cut:
	$(PYTHON) -m pipeline.cli radio-cut

film:
	$(PYTHON) -m pipeline.cli run-all --image-provider external_local --narration-provider local_tts --video-provider ken_burns --music-provider local_score

clean-tmp:
	$(PYTHON) -c "import shutil, pathlib; p = pathlib.Path('outputs/tmp'); shutil.rmtree(p, ignore_errors=True); p.mkdir(parents=True, exist_ok=True)"
