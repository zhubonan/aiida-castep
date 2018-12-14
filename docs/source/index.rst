#####################################
`AiiDA`_ plugin for `CASTEP`_
#####################################

.. figure:: images/AiiDA_transparent_logo.png
    :width: 300px
    :align: center

.. figure:: images/CASTEP_Logo.png
    :width: 300px
    :align: center

.. _AiiDA: http://www.aiida.net
.. _CASTEP: http://www.castep.org

Welcome to the documentation of ``aiida-castep``
================================================

`CASTEP`_ is a plane-wave pseudopotential density functional theory code.
This plugin allow CASTEP calculations to be run using AiiDA.

The plugin is available at http://gitlab.com/bz1/aiida-castep.

If you use this plugin and/or AiiDA for your research, please cite the following work:

.. highlights:: Giovanni Pizzi, Andrea Cepellotti, Riccardo Sabatini, Nicola Marzari,
  and Boris Kozinsky, *AiiDA: automated interactive infrastructure and database
  for computational science*, Comp. Mat. Sci 111, 218-230 (2016);
  http://dx.doi.org/10.1016/j.commatsci.2015.09.013; http://www.aiida.net.


Why bother?
===========

CASTEP can be used perfectly fine with a text editor and some bash scripts.
However, there several advantages of running through the AiiDA framework.

* Preserving provenance - All input and outputs are stored in a database, together
  with relationships, e.g links between them. This form a graph and we can trace extract
  how the results is reached and make them reproducible. 

* Automated submission/retrieve/monitoring/parsing - more time can be spend to focus on preparing
  the right input for calculations and analysing the results.
  The rest of the boring jobs will be handled by AiiDA.
  The output will be parsed and made available for numerical analysis after the calculation is completed.

* Querying - the database can be queried easily to locate, for example, calculations with certain
  inputs parameters, or say all the children of a certain input structure.

* Automated workflows - you can write workflows, the use case can vary from simply recovering failed
  jobs automatically to complex high throughput computation projects.

Calculations ran though AiiDA can be also exported as plain files, in fact these files are stored in a
file repository so it is merely a copying + renaming process.

.. note: Importing existing calculations should be possible, but has not been implemented yet,
   mainly due the developer not having such need.


A graphical example
===================

As an example, let's say we want to compute the band structure of silicon. We should first need to do a
fully relaxation of the cell parameters and then use the output geometry as input of the band structure calculations.
Below is a graph for this simple two step process:

.. figure:: images/Si_bs_example.png
    :width: 600px
    :align: center

It can be seen that the second calculations reused the structure and the remote data (e.g the check file)
from the first calculations. Some nodes are shared between the two calculations, namely the *Code* (CASTEP executable),
the pseudopotentials and the k-point mesh. The second calculation also has an additional input of the k-point
path to compute the band structure.


User's guide
------------

.. toctree::
   :maxdepth: 4

   user_guide/index

Modules provided with aiida-castep (API reference)
--------------------------------------------------

.. toctree::
   :maxdepth: 4

   module_guide/index

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

