.PHONY: dev test deploy cli

dev:
	uvicorn backend.app:app --reload --port 7860

test:
	pytest -q

deploy:
	git push hf main

cli:
	python -m backend.main_cli $(F)
