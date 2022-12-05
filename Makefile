.PHONY: doc test package tst-upload

clean:
	rm -r dist

package:
	python setup.py sdist bdist_wheel --universal

tst-upload:
	twine upload --repository-url https://test.pypi.org/legacy/ dist/libinsitu*

upload:
	twine upload -u oie-minesparistech dist/libinsitu*

test:
	PYTHONPATH=$(CURDIR) pytest libinsitu/test/unit_tests.py
