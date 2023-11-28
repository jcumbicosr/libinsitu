.PHONY: doc test test-local package tst-upload 

TSTENV=.tstenv

clean:
	rm -rf dist

package:
	python setup.py sdist bdist_wheel --universal

tst-upload:
	twine upload --repository-url https://test.pypi.org/legacy/ dist/libinsitu*

upload:
	twine upload dist/libinsitu*

test: clean package
	rm -rf $(TSTENV)
	virtualenv $(TSTENV)
	. $(TSTENV)/bin/activate
	$(TSTENV)/bin/pip install dist/*.whl --force-reinstall
	$(TSTENV)/bin/pip install pytest
	$(TSTENV)/bin/python -m pytest

test-local:
	python -m pytest
