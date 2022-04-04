TST_NOTEBOOK:=example-notebook.ipynb
VERSION:=$(shell cat VERSION)

.PHONY: doc test package tst-upload

clean:
	rm -r dist

package:
	python setup.py sdist bdist_wheel --universal

tst-upload:
	twine upload --repository-url https://test.pypi.org/legacy/ dist/lca_algebraic*

upload:
	twine upload -u oie-minesparistech dist/lca_algebraic*
