#!/bin/bash
# Exit on nonzero return code
set -e

# White space delimited list of files
files=$(ls submissions/*.json)
# File containing ClinVar API key
key_file=clinvar_key_runx1_vcep.txt

for f in $files; do
    echo $f
    python clinvar_api/submission.py submit --file $f --key-file $key_file
done
