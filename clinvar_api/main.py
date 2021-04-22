import sys
import os
import argparse
import pandas
import json

import clinvar_api
from clinvar_api.submission import (
    row_to_clinvar_submission,
    do_submit,
    do_status_check
)
from clinvar_api.generate import generate_excel_colmap
from clinvar_api.util import (str_to_bool, pandas_df_without_nan)
from clinvar_api.validate import validate_batch_submission

def main(argv):
    parser = argparse.ArgumentParser("clinvar_api.py")
    subparsers = parser.add_subparsers(help="subcommand",
                                       required=True,
                                       dest="subcommand")

    generate_subparser = subparsers.add_parser("generate")
    generate_subparser.add_argument(
        "--input-file", required=True, help="ClinVar submission MS Excel file")
    generate_subparser.add_argument(
        "--submission-name", required=True, help="Submission name to use in request")
    generate_subparser.add_argument(
        "--assertion-criteria-url", required=True, help="URL for assertion criteria document")
    generate_subparser.add_argument(
        "--assertion-criteria-name", required=True, help="Display name for the assertion criteria document")
    generate_subparser.add_argument(
        "--prettyjson", default="true",
        choices=["true", "false"],
        help="Set to false to write output files without newlines or indentation")

    submit_subparser = subparsers.add_parser("submit")
    submit_subparser.add_argument(
        "--directory", type=str, help="Submit all files from this directory")
    submit_subparser.add_argument(
        "--file", type=str, help="Submit this file")
    # submit_subparser.add_argument(
    #     "--config", required=True, help="Config file for clinvar-api")
    submit_subparser.add_argument(
        "--key-file", required=True, help="File name containing the key to use")
    submit_subparser.add_argument(
        "--submit-url", required=False,
        default="https://submit.ncbi.nlm.nih.gov/api/v1/submissions/",
        help="URL to POST submission data to")

    # assertion_criteria = {
    #     "citation": {
    #         "url": "https://submit.ncbi.nlm.nih.gov/ft/byid/wzxvueak/clingen_myelomalig_acmg_specifications_v1.pdf"
    #     },
    #     "method": "ClinGen MyeloMalig ACMG Specifications v1"
    # }

    opts = parser.parse_args(argv)

    if opts.subcommand == "generate":
        input_filename = opts.input_file
        opts.prettyjson = str_to_bool(opts.prettyjson)
        assertion_criteria = {
            "citation": {"url": opts.assertion_criteria_url},
            "method": opts.assertion_criteria_name
        }

        excel_col_labels = [e[0] for e in sorted(
            generate_excel_colmap().items(), key=lambda e: e[1])]
        df = pandas.read_excel(input_filename, header=None,
                               names=excel_col_labels, sheet_name="Variant")
        df = df[5:]  # ClinVar excel has 5 leading rows, 0-based indexes 0 through 4 including 4

        df = pandas_df_without_nan(df)
        df_json = df.apply(
            row_to_clinvar_submission,
            axis=1,
            assertion_criteria=assertion_criteria,
            prettyjson=opts.prettyjson,
            submission_name=opts.submission_name
        #    args=(opts.prettyjson,)
        )

    elif opts.subcommand == "submit":
        with open(opts.key_file) as f:
            api_key = f.read().strip()
        if opts.directory and opts.file:
            raise RuntimeError(
                "Cannot use --directory and --file at the same time")
        if opts.directory == None and opts.file == None:
            raise RuntimeError("Must provide either --directory or --file")

        if opts.file:
            files = [opts.file]
        if opts.directory:
            files = os.listdir(opts.directory)
        docs = []
        for filename in files:
            with open(filename) as f_in:
                docs.append(json.load(f_in))
        for doc, filename in zip(docs, files):
            print("Submitting {}".format(filename))
            success, submission_response = do_submit(doc, api_key, opts.submit_url)
            if not success:
                raise RuntimeError("Submission failed, halting: " + submission_response)
            sub_id = submission_response["id"]
            status_check = do_status_check(sub_id, api_key)
            print(status_check)



if __name__ == "__main__":
    # Example
    # argv = [
    #     "generate",
    #     "--input-file", "ClinVar_Submission_RUNX1_01122021.xlsx",
    #     "--submission-name", "MyeloMalig_20200114_API"
    # ]

    argv = sys.argv[1:]

    sys.exit(main(argv))