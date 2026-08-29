# Makefile for building the SharedLayer.
# SAM invokes `make build-SharedLayer` when BuildMethod is makefile.
# However, since BuildMethod is python3.12, SAM handles pip install automatically.
#
# This Makefile provides a manual build target for local testing and
# for syncing the app/ source into the layer's python/ directory.

.PHONY: sync-app clean

# Copy the shared app modules into the layer's python/ directory.
# Run this before `sam build` to ensure the layer has the latest code.
sync-app:
	@echo "Syncing app/ modules into shared/python/app/ ..."
	@rm -rf python/app/config.py python/app/models python/app/services python/app/middleware
	@cp ../app/config.py python/app/config.py
	@cp -r ../app/models python/app/models
	@cp -r ../app/services python/app/services
	@cp -r ../app/middleware python/app/middleware

clean:
	@rm -rf python/app/models python/app/services python/app/middleware
	@rm -f python/app/config.py
