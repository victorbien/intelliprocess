# Makefile for building the SharedLayer.
#
# SAM invokes `make build-SharedLayer` when the layer's BuildMethod is
# `makefile` (see template.yaml). SAM sets $(ARTIFACTS_DIR) to the directory
# whose contents become the layer. For a Python layer, importable content must
# live under $(ARTIFACTS_DIR)/python.
#
# This target does two things SAM's built-in python builder does NOT do together:
#   1. pip-install the layer's runtime dependencies (requirements.txt)
#   2. copy the shared `app` package source into the layer
# so the API Lambdas can `from app.main import handler`.

.PHONY: build-SharedLayer sync-app clean

build-SharedLayer:
	@echo "Installing layer dependencies into $(ARTIFACTS_DIR)/python ..."
	python -m pip install -r requirements.txt -t "$(ARTIFACTS_DIR)/python"
	@echo "Copying app package into $(ARTIFACTS_DIR)/python/app ..."
	python build_layer.py
	cp -r python/app "$(ARTIFACTS_DIR)/python/app"

# Manual helper: copy the shared app modules into shared/python/app/ for local
# testing. Run before a local `sam build` if not using the makefile build.
sync-app:
	python build_layer.py

clean:
	@rm -rf python/app/config.py python/app/main.py python/app/dev_mock.py \
		python/app/__init__.py python/app/models python/app/services \
		python/app/middleware python/app/routers
