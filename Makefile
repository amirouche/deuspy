all:
	@echo héllo world!

doc:
	pandoc README.md -o README.rst
