import os
import sys
import argparse
import csv
import pandas
import xlrd
import datetime
import json
import requests


allowed_clinical_significance_descriptions = [
    'Pathogenic',
    'Likely pathogenic',
    'Uncertain significance',
    'Likely benign',
    'Benign',
    'affects',
    'association',
    'drug response',
    'confers sensitivity',
    'protective',
    'risk factor',
    'other',
    'not provided']

def normalize_clinical_significance_description(input_desc:str) -> str:
    for allowed in allowed_clinical_significance_descriptions:
        if allowed.lower() == input_desc.lower():
            return allowed
    raise RuntimeError("{} not an allowed clinical significance ({})".format(
        input_desc, str(allowed_clinical_significance_descriptions)))

def generate_excel_colmap(end_after="CS"):
    """
    Returns a dict of excel column labels to 0-indexed column indices
    """
    alpha = [chr(i) for i in range(ord('A'), ord('Z')+1)]
    out = [c for c in alpha]
    stop = False
    for i in alpha:
        for j in alpha:
            label = str(i) + str(j)
            out.append(label)
            if label == end_after:
                stop = True
                break
        if stop:
            break
    return {out[i]: i for i in range(len(out))}


def parse_citations(s: str):
    """
    Parse a citation identifier to a {db, id} map
    TODO add PubMedCentral, DOI, NCBI Bookshelf
    Optional.  Citations documenting the clinical significance.
    Any of PubMed, PubMedCentral, DOI, NCBI Bookshelf combined with the
    id in that database (e.g. PMID:123456,  PMCID:PMC3385229, NBK:56955).
    Separate multiple citations by a semicolon.
    """
    print("parse_citations(%s)" % s)
    if pandas.isnull(s) or not s:
        return []
    terms = [e.strip() for e in s.split(";")]
    print("parse_citations: " + str(terms))
    out = []
    for term in terms:
        if term.startswith("PMID"):
            out.append({"db": "PubMed", "id": term})
        else:
            raise RuntimeError("Unknown citation format: " + term)
    return out


def serialize_date(d: datetime.datetime) -> str:
    return d.strftime("%Y-%m-%d")


def makedir_if_not_exists(dirname: str):
    if os.path.exists(dirname):
        if os.path.isdir(dirname):
            return
        else:
            raise RuntimeError("Path {} already exists".format(dirname))
    else:
        os.mkdir(dirname)

# def all_as_string(df: pandas.DataFrame, cols=[]):
#     for col_name in df.columns:
#         df[col_name] = df[col_name].astype("string")
#     return df


def row_to_clinvar_submission(row: pandas.Series, prettyjson=True):
    row_idx = row.name
    # misc fields
    submission_name = "PAHVCEP_10_2020_API"
    local_id = row["A"]
    local_key = row["B"]
    record_status = "novel"
    release_status = "public"
    # variantSet
    variant_set = {
        "variant": [{
            "gene": [{"symbol": e.strip() for e in row["C"].split(";")}],
            "hgvs": row["D"] + ":" + row["E"]
        }]
    }
    # conditionSet
    condition_set = {
        "condition": [{
            "db": row["AD"],
            "id": row["AE"]
        }]
    }
    # clinicalSignificance
    clinsig_description = normalize_clinical_significance_description(row["AK"])
    clinsig_date_last_evaluated = serialize_date(row["AL"])
    clinsig_mode_of_inheritance = row["AO"]
    clinsig_comment = row["AR"]
    clinsig_citations = parse_citations(row["AP"])
    if pandas.notnull(row["AQ"]):
        clinsig_citations.append({"url": row["AQ"]})
    # observedIn
    observed_in = [{
        "collectionMethod": row["AX"],
        "alleleOrigin": row["AY"],
        "affectedStatus": row["AZ"],
        "numberOfIndividuals": 0
    }]
    # assertionCriteria
    # TODO using hardcoded assertion method and citation for now, update to generalize
    assertion_criteria = {
        "citation": {
            "url": "https://submit.ncbi.nlm.nih.gov/ft/byid/i2ra5ppm/clingen_pah_acmg_specifications_v1.pdf"
        },
        "method": "ClinGen PAH ACMG Specifications v1"
    }
    doc = {
        "clinvarSubmission": [{
            "assertionCriteria": assertion_criteria,
            "clinicalSignificance": {
                "citation": clinsig_citations,
                "clinicalSignificanceDescription": clinsig_description,
                "comment": clinsig_comment,
                "dateLastEvaluated": clinsig_date_last_evaluated,
                "modeOfInheritance": clinsig_mode_of_inheritance
            },
            "conditionSet": condition_set,
            "localID": local_id,
            "localKey": local_key,
            "observedIn": observed_in,
            "recordStatus": record_status,
            "releaseStatus": release_status,
            "variantSet": variant_set
        }],
        "submissionName": submission_name
    }
    makedir_if_not_exists("submissions")
    with open("submissions/submission-%s-%s.json" % (row_idx, local_id), "w") as f_out:
        indent = None
        if prettyjson:
            indent = 4
        json.dump(doc, f_out, indent=indent)
    return doc


def handle_submission_failure(response):
    for k, v in response.headers.items():
        print("< {}: {}".format(k, v))
    print(json.dumps(json.loads(response.content.decode("UTF-8")), indent=2))

    raise RuntimeError(
        "Submission failed, HTTP status code {}".format(response.status_code))


def do_submit(submission_json: dict, api_key: str, submission_url="https://submit.ncbi.nlm.nih.gov/api/v1/submissions/"):
    data = {
        "actions": [{
            "type": "AddData",
            "targetDb": "clinvar",
            "data": {"content": submission_json}
        }]
    }
    headers = {
        "Content-Type": "application/json",
        "SP-API-KEY": api_key
    }
    print("post")
    print(json.dumps(headers, indent=4))
    print(json.dumps(data, indent=4))
    response = requests.post(
        submission_url,
        data=json.dumps(data),
        headers=headers
    )
    if response.status_code not in [200, 201]:
        handle_submission_failure(response)
        return False  # unreachable with exception in handle_submission_failure
    else:
        print("Successful submission")
    return True


# input_filename = "ClinVar_Submission_ClinGen_PAHVCEP_10_2020.xlsx"
# excel_col_labels = [e[0] for e in sorted(generate_excel_colmap().items(), key=lambda e: e[1])]
# df = pandas.read_excel(input_filename, header=None, names=excel_col_labels, sheet_name="Variant")
# # df = all_as_string(df)
# df = df[6:] # ClinVar excel has 6 leading rows 0 through 5 including 5
# df_json = df.apply(row_to_clinvar_submission, axis=1)

def str_to_bool(s):
    if s == "false":
        return False
    return True


def main(argv):
    parser = argparse.ArgumentParser("clinvar_api.py")
    subparsers = parser.add_subparsers(help="subcommand",
                                       required=True,
                                       dest="subcommand")

    generate_subparser = subparsers.add_parser("generate")
    generate_subparser.add_argument(
        "--input-file", required=True, help="ClinVar submission MS Excel file")
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

    opts = parser.parse_args(argv)

    if opts.subcommand == "generate":
        input_filename = opts.input_file
        opts.prettyjson = str_to_bool(opts.prettyjson)
        excel_col_labels = [e[0] for e in sorted(
            generate_excel_colmap().items(), key=lambda e: e[1])]
        df = pandas.read_excel(input_filename, header=None,
                               names=excel_col_labels, sheet_name="Variant")
        df = df[6:]  # ClinVar excel has 6 leading rows 0 through 5 including 5
        df_json = df.apply(row_to_clinvar_submission,
                           axis=1,
                           args=(opts.prettyjson,))
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
            do_submit(doc, api_key, opts.submit_url)


if __name__ == "__main__":
    argv = [
        "generate",
        "--filename", "ClinVar_Submission_ClinGen_PAHVCEP_10_2020.xlsx"
    ]
    argv = sys.argv[1:]

    sys.exit(main(argv))
