.PHONY: dev test deploy cli docker-build docker-test docker-run web-install web-dev web-build

IMAGE ?= nerdearla-captions
ENV_FILE ?= .env
HF_SPACE ?=

# two-process dev workflow: this serves the API on :7860; `make web-dev` serves
# the React app on :5173, proxying /api and /ws back to this process.
dev:
	uvicorn backend.app:app --reload --port 7860 --ws-ping-interval 20 --ws-ping-timeout 20

web-install:
	cd web && npm ci

web-dev:
	cd web && npm run dev

web-build:
	cd web && npm run build

test:
	pytest -q

# Uploads the working tree to the Space (no git history: HF rejects binaries outside Xet/LFS).
# Needs `pip install -U huggingface_hub` and `hf auth login`.
deploy:
	@test -n "$(HF_SPACE)" || (echo "usage: make deploy HF_SPACE=<user>/<space>" && exit 1)
	hf upload $(HF_SPACE) . . --repo-type=space \
		--commit-message "deploy $$(git rev-parse --short HEAD)$$(git diff --quiet || echo -dirty)" \
		--exclude ".git/*" --exclude ".env" --exclude ".venv/*" --exclude "data/*" \
		--exclude "**/__pycache__/*" --exclude "samples/mp3/*" \
		--exclude "web/node_modules/*" --exclude "web/dist/*"

cli:
	python -m backend.main_cli $(F)

docker-build:
	docker build -t $(IMAGE) .

docker-test: docker-build
	docker run --rm $(IMAGE) pytest -q

# runs as the host user so it can write to ./data
docker-run: docker-build
	mkdir -p data
	docker run --rm -it -p 7860:7860 --env-file $(ENV_FILE) --user $$(id -u):$$(id -g) \
		-v $(CURDIR)/samples:/home/user/app/samples:ro -v $(CURDIR)/data:/home/user/app/data $(IMAGE)
