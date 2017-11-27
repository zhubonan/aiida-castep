AIIDA plugin for interface with CASTEP
======================================

TODOS
=====

* Allow helper to be used without CASTEP binary
* Parsing of the .bands file
* Test the `CastepRelaxWorkChain`
* Write docs

How to test
===========

Use `verdi devel tests ` to do tests. Note that this require manual editing of
aiida.backend.tests.__init__.py to append pulgins tests.

A test profile should be used together with a test database.
