.PHONY: doc test package tst-upload

TSTENV=.tstenv

clean:
	rm -r dist

package:
	python setup.py sdist bdist_wheel --universal

tst-upload:
	twine upload --repository-url https://test.pypi.org/legacy/ dist/libinsitu*

upload:
	twine upload -u oie-minesparistech dist/libinsitu*

test:
	rm -rf $(TSTENV)
	virtualenv $(TSTENV)
	. $(TSTENV)/bin/activate
	$(TSTENV)/bin/pip install dist/*.whl
	$(TSTENV)/bin/pip install pytest
	$(TSTENV)/bin/pytest libinsitu/test/*.py
