#!/usr/bin/env bash
set -xe

python clinvar_api/main.py submit --key-file clinvar_key_runx1_vcep.txt --file executions/20210422/RUNX1/1/submissions/submission-5-603cd528-c485-4e30-934a-cabde6c6d80d.json
python clinvar_api/main.py submit --key-file clinvar_key_runx1_vcep.txt --file executions/20210422/RUNX1/1/submissions/submission-6-369b5ad5-da61-4f82-b250-fca73fbd9ae4.json
python clinvar_api/main.py submit --key-file clinvar_key_runx1_vcep.txt --file executions/20210422/RUNX1/1/submissions/submission-7-98ed23b5-7557-477d-af0e-20f02ed05e0e.json
python clinvar_api/main.py submit --key-file clinvar_key_runx1_vcep.txt --file executions/20210422/RUNX1/1/submissions/submission-8-2bedec2a-8416-4eac-980c-34c0172629cd.json
python clinvar_api/main.py submit --key-file clinvar_key_runx1_vcep.txt --file executions/20210422/RUNX1/1/submissions/submission-9-a5303f14-d570-492c-aaa8-b258e957fb6d.json

