import sys
import os
import argparse
import pandas
import json

import clinvar_api
from clinvar_api.submission import (
    row_to_clinvar_submission,
    do_submit,
    do_status_check)
from clinvar_api.generate import (
    generate_excel_colmap,
    parse_citations,
    parse_curie,
    dataframe_to_clinvar_submission)
from clinvar_api.util import (
    str_to_bool,
    pandas_df_without_nan,
    makedir_if_not_exists)
from clinvar_api.validate import validate_batch_submission

def parse_args_assertion_criteria(args: argparse.Namespace) -> dict:
    assertion_criteria = {
        "method": args.assertion_criteria_name
    }
    # "citation": {"url": args.assertion_criteria_url},
    if args.assertion_criteria_db_curie:
        parsed_curie = parse_curie(args.assertion_criteria_db_curie)
        if parsed_curie is None:
            raise RuntimeError("Assertion criteria db curie was not a single parsable identifier: " + args.assertion_criteria_db_curie)
        db_ns, db_id = parsed_curie
        assertion_criteria["citation"] = {"db": db_ns, "id": db_id}
    elif args.assertion_criteria_url:
        assertion_criteria["citation"] = {"url": args.assertion_criteria_url}
    else:
        # Should be unreachable due to required argument group
        raise RuntimeError("Neither an assertion criteria db nor url was provided")
    return assertion_criteria


def save_submission_to_file(clinvar_submission: dict) -> None:
    """
    Saves the submission to a file, and each individual record to a file for easier
    later inspection. Returns the list of files written, with the overal submission filename
    being the first in the list.
    """
    makedir_if_not_exists("submissions")
    def saveone(row_idx, local_id, doc):
        filename = "submissions/submission-%s-%s.json" % (row_idx, local_id)
        with open(filename, "w") as f_out:
            indent = None
            json.dump(doc, f_out, indent=indent)
            return filename
    filenames = []
    filenames.append(saveone("ALL", clinvar_submission["submissionName"], clinvar_submission))
    for row_idx, rec in enumerate(clinvar_submission["clinvarSubmission"]):
        local_id = rec["localID"]
        filenames.append(saveone(row_idx, local_id, rec))
    return filenames


def main(argv):
    parser = argparse.ArgumentParser("clinvar_api.py")
    subparsers = parser.add_subparsers(help="subcommand",
                                       required=True,
                                       dest="subcommand")

    # Generate subparser
    generate_subparser = subparsers.add_parser("generate")
    generate_subparser.add_argument(
        "--input-file", required=True, help="ClinVar submission MS Excel file")
    generate_subparser.add_argument(
        "--submission-name", required=True, help="Submission name to use in request")
    generate_subparser.add_argument(
        "--assertion-criteria-name", required=True, help="Display name for the assertion criteria document")
    def add_assertion_criteria_group(parser):
        assertion_criteria_group = parser.add_mutually_exclusive_group(required=True)
        assertion_criteria_group.add_argument(
            "--assertion-criteria-url",
            help="URL for assertion criteria document")
        assertion_criteria_group.add_argument(
            "--assertion-criteria-db-curie",
            help="Identifier of criteria document in a document database in CURIE format. Example: PubMed:0000")
    add_assertion_criteria_group(generate_subparser)
    generate_subparser.add_argument(
        "--prettyjson", default="true",
        choices=["true", "false"],
        help="Set to false to write output files without newlines or indentation")

    # Submit subparser
    submit_subparser = subparsers.add_parser("submit")
    # submit_subparser.add_argument(
    #     "--directory", type=str, help="Submit all files from this directory")
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
    submit_subparser.add_argument(
        "--dry-run", default="false",
        choices=["true", "false"],
        help="Submit as a dry run. Will perform submission as usual but with ?dry-run=true")

    # assertion_criteria = {
    #     "citation": {
    #         "url": "https://submit.ncbi.nlm.nih.gov/ft/byid/wzxvueak/clingen_myelomalig_acmg_specifications_v1.pdf"
    #     },
    #     "method": "ClinGen MyeloMalig ACMG Specifications v1"
    # }

    args = parser.parse_args(argv)

    if args.subcommand == "generate":
        input_filename = args.input_file
        args.prettyjson = str_to_bool(args.prettyjson)
        assertion_criteria = parse_args_assertion_criteria(args)

        excel_col_labels = [e[0] for e in sorted(
            generate_excel_colmap().items(), key=lambda e: e[1])]
        df = pandas.read_excel(input_filename, header=None, #dtype='str',
                               names=excel_col_labels, sheet_name="Variant")
        df = df[5:]  # ClinVar excel has 5 leading rows, 0-based indexes 0 through 4 including 4

        df = pandas_df_without_nan(df)
        # def dates_to_string(df: pandas.DataFrame) -> pandas.DataFrame:
        #     for colname in df.columns:
        df["AL"] = df["AL"].dt.strftime("%Y-%m-%d")


        # df_json = df.apply(
        #     row_to_clinvar_submission,
        #     axis=1,
        #     assertion_criteria=assertion_criteria,
        #     prettyjson=args.prettyjson,
        #     submission_name=args.submission_name
        # #    args=(args.prettyjson,)
        # )
        df_json = dataframe_to_clinvar_submission(
            df, assertion_criteria, args.submission_name)
        print(json.dumps(df_json))
        print("Saving submission documents to files")
        filenames = save_submission_to_file(df_json)
        print(json.dumps(filenames, indent=2))

        print("Validating submission payload")
        validate_batch_submission(df_json)

    elif args.subcommand == "submit":
        args.dry_run = str_to_bool(args.dry_run)
        with open(args.key_file) as f:
            api_key = f.read().strip()
        if "directory" in args and "file" in args:
            raise RuntimeError(
                "Cannot use --directory and --file at the same time")
        if "directory" not in args and "file" not in args:
            raise RuntimeError("Must provide either --directory or --file")

        if "file" in args:
            files = [args.file]
        if "directory" in args:
            files = os.listdir(args.directory)
        docs = []
        for filename in files:
            with open(filename) as f_in:
                docs.append(json.load(f_in))
        for doc, filename in zip(docs, files):
            print("Submitting {}".format(filename))
            success, submission_response = do_submit(doc, api_key, submission_url=args.submit_url, dry_run=args.dry_run)
            if not success:
                raise RuntimeError("Submission failed, halting: " + submission_response)
            if args.dry_run is False:
                sub_id = submission_response["id"]
                status_check = do_status_check(sub_id, api_key)
                print(status_check)
                status_filename = "status-check-%s-%s.json" % (doc["submissionName"], sub_id)
                with open(status_filename, "w") as f:
                    json.dump(status_check, f)
                print("Saved status check to: " + status_filename)
            else:
                print("Dry run finished")


if __name__ == "__main__":
    # Example
    # argv = [
    #     "generate",
    #     "--input-file", "ClinVar_Submission_RUNX1_01122021.xlsx",
    #     "--submission-name", "MyeloMalig_20200114_API"
    # ]

    argv = sys.argv[1:]
    sys.exit(main(argv))
