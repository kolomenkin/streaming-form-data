clean:
	rm -f dist/*.tar.gz
	rm -f dist/*.whl
	rm -rf build

# PyPI archive preparation
build:
	python setup.py sdist

upload: build
	twine upload dist/*

# no need to run 'build' step before
install:
	python -m pip install . --ignore-installed

# run tests and check code formatting
# needs 'install' step to be run before
test:
	py.test
	flake8

# gather library function call statistics (time, count, ...)
# needs 'install' step to be run before
profile:
	python utils/benchmark.py -f tests/data/image-high-res.jpg -c image/jpeg

# calculate library bandwidth
# needs 'install' step to be run before
speedtest:
	python utils/speedtest.py

.PHONY: clean build upload install test profile speedtest
