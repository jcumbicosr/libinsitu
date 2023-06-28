.PHONY: doc test test-local package tst-upload 

TSTENV=.tstenv

clean:
	rm -r dist

package:
	python setup.py sdist bdist_wheel --universal

tst-upload:
	twine upload --repository-url https://test.pypi.org/legacy/ dist/libinsitu*

upload:
	twine upload -u oie-minesparistech dist/libinsitu*

test: clean package
	rm -rf $(TSTENV)
	virtualenv $(TSTENV)
	. $(TSTENV)/bin/activate
	$(TSTENV)/bin/pip install dist/*.whl --force-reinstall
	$(TSTENV)/bin/pip install pytest
	$(TSTENV)/bin/pytest libinsitu/test/*.py

test-local:
	PYTHONPATH=. pytest libinsitu/test/*.py
