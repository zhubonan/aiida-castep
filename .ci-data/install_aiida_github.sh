#!/bin/bash
cd ..
git clone https://github.com/aiidateam/aiida_core
cd aiida_core
echo "Checking out: $AIIDA_DEVELOP_GIT_HASH"
git checkout $AIIDA_DEVELOP_GIT_HASH
pip install -e .[docs,testing]
cd -
