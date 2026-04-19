# vista-meta Makefile — lean v1 (spec §8, ADR-032)
# RUNS ON: host
# Default target: help

include .env

IMAGE     := vista-meta
CONTAINER := vista-meta
VOLUME    := vehu-globals
BUILD_DATE := $(shell date +%F)
DOCKER    := docker

.DEFAULT_GOAL := help

# ── Lifecycle ─────────────────────────────────────────────────────────

.PHONY: build
build: ## Build the Docker image
	$(DOCKER) build \
		-f docker/Dockerfile \
		--build-arg BUILD_DATE=$(BUILD_DATE) \
		-t $(IMAGE):latest \
		-t $(IMAGE):$(BUILD_DATE) \
		docker/

.PHONY: run
run: ## Start the container (creates named volume on first run)
	$(DOCKER) run -d \
		--name $(CONTAINER) \
		--hostname vista-meta \
		-p $(TAILSCALE_IP):2222:22 \
		-p $(TAILSCALE_IP):9430:9430 \
		-p $(TAILSCALE_IP):8001:8001 \
		-p $(TAILSCALE_IP):1338:1338 \
		-p $(TAILSCALE_IP):8089:8089 \
		-v $(VOLUME):/home/vehu/g \
		-v $(PWD)/vista/dev-r:/home/vehu/dev/r \
		-v $(PWD)/vista/scripts:/home/vehu/scripts \
		-v $(PWD)/vista/export:/home/vehu/export \
		--stop-timeout 30 \
		$(IMAGE):latest

.PHONY: stop
stop: ## Stop the container gracefully
	$(DOCKER) stop $(CONTAINER) 2>/dev/null || true

.PHONY: restart
restart: stop ## Restart the container
	@sleep 2
	$(DOCKER) rm $(CONTAINER) 2>/dev/null || true
	@$(MAKE) run

.PHONY: rm
rm: stop ## Remove the container (keeps volume and image)
	$(DOCKER) rm $(CONTAINER) 2>/dev/null || true

.PHONY: clean
clean: ## Remove container + volume + image (DESTRUCTIVE — prompts)
	@echo "This will destroy the container, named volume (globals), and image."
	@echo "Snapshots in snapshots/ are not affected."
	@read -p "Are you sure? [y/N] " confirm && [ "$$confirm" = "y" ] || exit 1
	$(DOCKER) rm -f $(CONTAINER) 2>/dev/null || true
	$(DOCKER) volume rm $(VOLUME) 2>/dev/null || true
	$(DOCKER) rmi $(IMAGE):latest $(IMAGE):$(BUILD_DATE) 2>/dev/null || true

# ── Interactive ───────────────────────────────────────────────────────

.PHONY: shell
shell: ## SSH into the container as vehu
	ssh -p 2222 -o StrictHostKeyChecking=no vehu@$(TAILSCALE_IP)

.PHONY: mumps
mumps: ## Open a YottaDB/MUMPS prompt inside the container
	$(DOCKER) exec -it -u vehu $(CONTAINER) bash -lc '$$ydb_dist/mumps -direct'

.PHONY: python
python: ## Open a Python shell inside the container
	$(DOCKER) exec -it -u vehu $(CONTAINER) python3

.PHONY: logs
logs: ## Tail container logs (entrypoint output)
	$(DOCKER) logs -f $(CONTAINER)

.PHONY: bake-log
bake-log: ## Show the latest bake log
	@ls -t vista/export/logs/bake-*.log 2>/dev/null | head -1 | xargs cat 2>/dev/null \
		|| echo "No bake logs found"

# ── Bake ──────────────────────────────────────────────────────────────

.PHONY: bake
bake: ## Run bake.sh --all inside the container
	$(DOCKER) exec -u vehu $(CONTAINER) bash -lc '/usr/local/bin/bake.sh --all'

.PHONY: bake-xindex
bake-xindex: ## Run XINDEX baseline only
	$(DOCKER) exec -u vehu $(CONTAINER) bash -lc '/usr/local/bin/bake.sh --xindex'

.PHONY: bake-dd-text
bake-dd-text: ## Run DD exporter A (FileMan text)
	$(DOCKER) exec -u vehu $(CONTAINER) bash -lc '/usr/local/bin/bake.sh --only=dd-text'

.PHONY: bake-dd-fmql
bake-dd-fmql: ## Run DD exporter B (FMQL)
	$(DOCKER) exec -u vehu $(CONTAINER) bash -lc '/usr/local/bin/bake.sh --only=dd-fmql'

.PHONY: bake-dd-template
bake-dd-template: ## Run DD exporter D (Print Templates)
	$(DOCKER) exec -u vehu $(CONTAINER) bash -lc '/usr/local/bin/bake.sh --only=dd-template'

.PHONY: wait-for-bake
wait-for-bake: ## Poll sentinel until bake completes (progress dots)
	@echo -n "[wait-for-bake] "
	@while true; do \
		if [ ! -f vista/export/.vista-meta-initialized ]; then \
			echo -n "."; sleep 30; continue; \
		fi; \
		if $(DOCKER) exec $(CONTAINER) jq -e \
			'.phases | to_entries[] | select(.value.status == "pending")' \
			/home/vehu/export/.vista-meta-initialized >/dev/null 2>&1; then \
			echo -n "."; sleep 30; \
		else \
			echo " done"; \
			$(DOCKER) exec $(CONTAINER) jq '.phases | to_entries[] | "\(.key): \(.value.status)"' \
				/home/vehu/export/.vista-meta-initialized 2>/dev/null; \
			break; \
		fi; \
	done

# ── Snapshot ──────────────────────────────────────────────────────────

.PHONY: snapshot-globals
snapshot-globals: ## Snapshot the globals volume (auto-prune to last 5)
	@mkdir -p snapshots
	$(DOCKER) run --rm -v $(VOLUME):/data -v $(PWD)/snapshots:/snapshots \
		alpine tar czf /snapshots/globals-$$(date +%F-%H%M%S).tar.gz -C /data .
	@echo "Snapshot saved. Pruning to last 5..."
	@ls -t snapshots/globals-*.tar.gz 2>/dev/null | tail -n +6 | xargs rm -f 2>/dev/null || true
	@ls -lh snapshots/globals-*.tar.gz

.PHONY: restore-globals
restore-globals: ## Restore globals from snapshot (SNAPSHOT=path/to/file.tar.gz)
	@[ -n "$(SNAPSHOT)" ] || { echo "Usage: make restore-globals SNAPSHOT=snapshots/globals-YYYY-MM-DD.tar.gz"; exit 1; }
	@[ -f "$(SNAPSHOT)" ] || { echo "File not found: $(SNAPSHOT)"; exit 1; }
	@echo "This will replace ALL globals with the snapshot contents."
	@read -p "Are you sure? [y/N] " confirm && [ "$$confirm" = "y" ] || exit 1
	$(DOCKER) run --rm -v $(VOLUME):/data -v $(PWD)/$(SNAPSHOT):/snapshot.tar.gz \
		alpine sh -c 'rm -rf /data/* && tar xzf /snapshot.tar.gz -C /data'

# ── Verify ────────────────────────────────────────────────────────────

.PHONY: smoke
smoke: ## Run post-build smoke tests
	@bash tests/smoke/smoke.sh

# ── Docs ──────────────────────────────────────────────────────────────

.PHONY: adr-new
adr-new: ## Create a new ADR (TITLE="decision title")
	@[ -n "$(TITLE)" ] || { echo "Usage: make adr-new TITLE=\"My Decision\""; exit 1; }
	@NEXT=$$(ls docs/adr/*.md 2>/dev/null | grep -oP '\d+' | sort -n | tail -1); \
	NEXT=$$(printf "%03d" $$(( NEXT + 1 ))); \
	SLUG=$$(echo "$(TITLE)" | tr '[:upper:]' '[:lower:]' | tr ' ' '-' | tr -cd 'a-z0-9-'); \
	FILE="docs/adr/$${NEXT}-$${SLUG}.md"; \
	printf "# ADR-$${NEXT}: $(TITLE)\n\nDate: $$(date +%F)\nStatus: Proposed\n\n## Context\n\n## Decision\n\n## Consequences\n\n## Alternatives considered\n" > "$$FILE"; \
	echo "Created $$FILE"

.PHONY: help
help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' Makefile | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
