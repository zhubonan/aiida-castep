===============
Getting started
===============

A short guide of setting up the plugin

How to setup the code
+++++++++++++++++++++

The pulgin needs to properly installed and setup to be used by AiidA::

 pip install -e .

To allow AiiDA to discover the plugin, run::

 reentry scan aiida

.. note:: Please refer to AiiDA's documentation for plugin installation.

Test the pulgin
+++++++++++++++

AiiDA's pulgin test framework can be used::

 verdi -p {your_test_profile_name} devel tests db.castep

