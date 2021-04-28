import os
import sys
import argparse
import csv
import pandas
import xlrd
import datetime
import json
import requests
import numpy

import clinvar_api
from clinvar_api.generate import (
    generate_excel_colmap,
    row_to_clinvar_submission)


def handle_request_failure(response: requests.Response):
    """
    Prints the status code and headers of the response and throws runtime error.
    """
    print("< status={}".format(response.status_code))
    for k, v in response.headers.items():
        print("< {}: {}".format(k, v))
    print(json.dumps(json.loads(response.content.decode("UTF-8")), indent=2))
    raise RuntimeError("Request failed, HTTP status code {}".format(response.status_code))


def scrape_status_check_response_files(status_check: dict) -> dict:
    """
    For each response object
    """


def do_status_check(sub_id: str, api_key: str, submission_url="https://submit.ncbi.nlm.nih.gov/api/v1/submissions/"):
    """
    sub_id is the generated submission id that is returned from ClinVar when a submission is posted to
    their API.

    Returns the parsed status endpoint response, with actions[0].responses[0].files[].value set to the
    file content of the file at each actions[0].responses[0].files[].url
    """
    headers = {
        "Content-Type": "application/json",
        "SP-API-KEY": api_key
    }
    url = os.path.join(submission_url, sub_id, "actions")
    print("GET " + url)
    response = requests.get(url, headers=headers)
    response_content = response.content.decode("UTF-8")
    for k,v in response.headers.items():
        print("< %s: %s" % (k, v))
    print(response_content)
    if response.status_code not in [200]:
        raise RuntimeError("Status check failed:\n" + str(headers) + "\n" + url + "\n" + response_content)

    status_response = json.loads(response_content)

    # Load summary file
    action = status_response["actions"][0]
    print("Submission %s status %s" % (sub_id, action["status"]))
    responses = action["responses"]
    if len(responses) == 0:
        print("Status 'responses' field had no items, check back later")
    else:
        print("Status response had one or more responses, attempting to retrieve any files listed")
        summary_files = responses[0]["files"]
        for f in summary_files:
            url = f["url"]
            print("GET " + url)
            f_response = requests.get(url, headers=headers)
            f_response_content = f_response.content.decode("UTF-8")
            if f_response.status_code not in [200]:
                raise RuntimeError("Status check summary file fetch failed:\n%s\n%s\n%s" % (
                                    str(headers), url, f_response_content))
            file_content = json.loads(f_response_content)
            f["value"] = file_content

    return status_response


def save_response_to_file(submission: dict, response: requests.Response) -> str:
    if not os.path.isdir("responses"):
        os.mkdir("responses")
    basename = submission["submissionName"] + ".json" #+ "_" + "_".join(s["localID"] for s in submission["clinvarSubmission"])
    filename = os.path.join("responses", basename)
    with open(filename, "w") as f_out:
        json.dump({
                "timestamp": datetime.datetime.isoformat(datetime.datetime.now()),
                "status": response.status_code,
                "content": response.content.decode("UTF-8")
            },
            f_out,
            indent=2)
    return filename


def do_submit(submission: dict, api_key: str, dry_run=False, submission_url="https://submit.ncbi.nlm.nih.gov/api/v1/submissions/"):
    print("Submitting entries [{}] for submission {}".format(
        [csub["localID"] for csub in submission["clinvarSubmission"]],
        submission["submissionName"]
    ))
    data = {
        "actions": [{
            "type": "AddData",
            "targetDb": "clinvar",
            "data": {"content": submission}
        }]
    }
    headers = {
        "Content-Type": "application/json",
        "SP-API-KEY": api_key
    }

    params = {}
    if dry_run:
        print("dry-run = true")
        params["dry-run"] = "true"

    print("POST {}".format(submission_url))
    # NOTE if process stdout is being logged, sensitive headers may be included.
    # print(json.dumps(headers, indent=4))
    print(json.dumps(data, indent=4))
    response = requests.post(
        submission_url,
        data=json.dumps(data),
        headers=headers,
        params=params
    )
    response_content = response.content.decode("UTF-8")
    # Write response to file with name submissionName_localid[_localid ...]
    saved_filename = save_response_to_file(submission, response)
    print("Saved response to: " + saved_filename)

    if dry_run:
        if response.status_code != 204:
            raise RuntimeError("dry-run expected HTTP status code 204 (No Content)")
        print("Dry run submission was successful")
        return (True, "")

    if response.status_code not in [200, 201]:
        handle_request_failure(response)
        raise RuntimeError(response_content)  # unreachable with exception in handle_request_failure
    else:
        print("Successful submission")
        print("Response code {}".format(response.status_code))
        for k, v in response.headers.items():
            print("< {}: {}".format(k, v))
        print(response_content)
        response_object = json.loads(response_content)
        return (True, response_object)
