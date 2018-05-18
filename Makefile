help:
	$(info The following make commands are available:)
	$(info clean             - remove all generated files and directories)
	$(info test-all          - install locally, prepare for PyPI, run tests, speed test, profiler)
	$(info build             - prepare PyPI module archive)
	$(info upload            - upload built module archive to PyPI)
	$(info install_local     - build the module in the current directory)
	$(info                     it will be available for import from the project root directory)
	$(info test              - run tests and check code formatting)
	$(info profile           - gather library function call statistics (time, count, ...))
	$(info speedtest         - calculate library bandwidth)
	@:

clean:
	rm -f $(shell find streaming_form_data -maxdepth 1 -name '*.pyd')
	rm -rf build
	rm -rf dist
	rm -rf streaming_form_data.egg-info

requirements_output  := build/requirements.touch
annotation_output    := build/annotation.touch
build_output         := build/build.touch
install_local_output := build/install.touch
flake_output         := build/flake.touch
test_output          := build/test.touch

test-all: build test profile speedtest ;

build: $(annotation_output) $(test_output) $(flake_output) $(build_output)

upload: build
	twine upload dist/*

install_local: $(annotation_output) $(install_local_output) ;

test: $(test_output) $(flake_output) ;

profile: $(install_local_output)
	python utils/benchmark.py --data-size 17555000 -c binary/octet-stream

speedtest: $(install_local_output)
	python utils/speedtest.py

# list all targets which names does not match any real file name
.PHONY: help clean test-all build upload install_local test profile speedtest

# Real file rules begin

library_inputs := setup.py \
                  $(shell find streaming_form_data -maxdepth 1 -name '*.py') \
                  $(cython_file)

cython_file := streaming_form_data/_parser.pyx

python_syntax_files := $(shell find . -name '*.py' \
                         -not -path './.git/*' \
                         -not -path './.venv/*' \
                         -not -path './venv/*') \
                         $(cython_file)

test_files := $(shell find tests -maxdepth 1 -name '*.py')

$(requirements_output): requirements.dev.txt
	pip install -r requirements.dev.txt
	@mkdir -p "$(@D)" && touch "$@"

$(annotation_output): $(requirements_output) $(cython_file)
	cython -a $(cython_file) -o annotation.html
	@mkdir -p "$(@D)" && touch "$@"

$(build_output): $(requirements_output) $(library_inputs)
	python setup.py sdist
	@mkdir -p "$(@D)" && touch "$@"

$(install_local_output): $(requirements_output) $(library_inputs)
	pip install -e .
	@mkdir -p "$(@D)" && touch "$@"

$(flake_output): $(requirements_output) $(python_syntax_files)
	flake8
	@mkdir -p "$(@D)" && touch "$@"

$(test_output): $(requirements_output) $(install_local_output) $(test_files)
	py.test
	@mkdir -p "$(@D)" && touch "$@"
