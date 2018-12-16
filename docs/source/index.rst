#######################################
A Plugin to interface CASTEP with AiiDA
#######################################

.. figure:: images/AiiDA_transparent_logo.png
    :width: 300px
    :align: center
    :target: `AiiDA`_

.. figure:: images/CASTEP_Logo.png
    :width: 300px
    :align: center
    :target: `CASTEP`_

.. _AiiDA: http://www.aiida.net
.. _CASTEP: http://www.castep.org

Welcome to the documentation of ``aiida-castep``
================================================

`CASTEP`_ is a plane-wave pseudopotential density functional theory code.
This plugin allow CASTEP calculations to be run using `AiiDA`_.

The project home is located at http://gitlab.com/bz1/aiida-castep.

If you use this plugin and/or AiiDA for your research, please cite the following work:

.. highlights:: Giovanni Pizzi, Andrea Cepellotti, Riccardo Sabatini, Nicola Marzari,
  and Boris Kozinsky, *AiiDA: automated interactive infrastructure and database
  for computational science*, Comp. Mat. Sci 111, 218-230 (2016);
  http://dx.doi.org/10.1016/j.commatsci.2015.09.013; http://www.aiida.net.


Why bother?
===========

CASTEP calculations can be prepared and analysed  perfectly fine with a text editor and shell scripts.
However, there are several advantages of running CASTEP though Automated Interactive Infrastructure and Database for Computational Science (AiiDA).
I found it very hard to explain what AiiDA is and does in one or two sentences.
Hence, perhaps it is best to highlight some of and advantages of doing calculations this way:

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

* Detecting mistakes early - this plugin checks the inputs of a CASTEP calculation  before submitting to the remote cluster. Mistakes such as errors in keyword names or incompatible pairs will be catched.

Calculations ran though AiiDA can be also exported as plain files, in fact these files are stored in a
file repository so it is merely a copying + renaming process - you are not missing anything.


A graphical example
===================

As an example, let's say we want to compute the band structure of silicon. We should first need to do a
fully relaxation including the cell parameters, then use the output geometry as input of the band structure calculations and idelly reuse the model.
Below is a graph for this simple two step process:

.. figure:: images/Si_bs_example.png
    :width: 600px
    :align: center

Data and calculations are stored in AiiDA as *Nodes*, and they are connected by *Links*.
It can be seen in the graph that the second calculations reused the structure and the remote data (e.g the check file)
from the first calculations. Some nodes are shared between the two calculations, namely the *Code* (CASTEP executable),
the pseudopotentials and the k-point mesh. The second calculation also has an additional input of the k-point
path for the band structure.

You may want to do similar workflows for a range of material, or perhaps
also investigate the effects of strain or pressure and other properties.
The relationship between different calculations may quickly get complicated and non-trivial.
Having a record of not only the input and output of each calculation,
but also how they are linked together would help in these kind of studies.


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

