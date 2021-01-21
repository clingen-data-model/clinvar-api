#!/bin/bash
set -e

files=$(ls submissions/*.json)
key_file=clinvar_key_runx1_vcep.txt

for f in $files; do
    echo $f
    python clinvar_api/submission.py submit --file $f --key-file $key_file
done
