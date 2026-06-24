.PHONY: test install dev lint

test:        ## Run the smoke-test suite (no deps, throwaway HOME)
	bash tests/smoke_test.sh

install:     ## Install scripts + plugin and print the settings snippet
	./install.sh

dev:         ## Re-install and refresh the running SwiftBar plugin
	./install.sh >/dev/null
	open "swiftbar://refreshplugin?name=claude" || true

lint:        ## Byte-compile all Python (syntax check)
	python3 -m py_compile src/*.py scripts/*.py
