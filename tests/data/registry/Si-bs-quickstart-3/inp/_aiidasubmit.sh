#!/bin/bash
exec > _scheduler-stdout.txt
exec 2> _scheduler-stderr.txt


'mpirun' '-np' '2' '/home/bonan/appdir/castep/bin/castep.mpi' 'aiida'
