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
    print("< status={}".format(response.status_code))
    for k, v in response.headers.items():
        print("< {}: {}".format(k, v))
    print(json.dumps(json.loads(response.content.decode("UTF-8")), indent=2))
    raise RuntimeError("Request failed, HTTP status code {}".format(response.status_code))

def do_status_check(sub_id: str, api_key: str, submission_url="https://submit.ncbi.nlm.nih.gov/api/v1/submissions/"):
    """
    sub_id is the generated submission id that is returned from ClinVar when a submission is posted to
    their API.
    """
    headers = {
        "Content-Type": "application/json",
        "SP-API-KEY": api_key
    }
    url = os.path.join(submission_url, sub_id, "actions")
    print("GET " + url)
    response = requests.get(url, headers=headers)
    response_content = response.content.decode("UTF-8")
    if response.status_code not in [200]:
        raise RuntimeError("Status check failed:\n" + str(headers) + "\n" + url + "\n" + response_content)
    return json.loads(response_content)



def do_submit(submission: dict, api_key: str, submission_url="https://submit.ncbi.nlm.nih.gov/api/v1/submissions/"):
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
    print("POST {}".format(submission_url))
    # print(json.dumps(headers, indent=4))
    print(json.dumps(data, indent=4))
    response = requests.post(
        submission_url,
        data=json.dumps(data),
        headers=headers
    )
    response_content = response.content.decode("UTF-8")
    # Write response to file with name submissionName_localid[_localid ...]
    if not os.path.isdir("responses"):
        os.mkdir("responses")
    entry_identifier = submission["submissionName"] + "_" + "_".join(s["localID"] for s in submission["clinvarSubmission"])
    with open(os.path.join("responses", entry_identifier), "w") as f_out:
        json.dump({
                "timestamp": datetime.datetime.isoformat(datetime.datetime.now()),
                "status": response.status_code,
                "content": response_content
            },
            f_out,
            indent=2)
    if response.status_code not in [200, 201]:
        handle_request_failure(response)
        raise RuntimeError(response_content)  # unreachable with exception in handle_submission_failure
    else:
        print("Successful submission")
        print("Response code {}".format(response.status_code))
        for k, v in response.headers.items():
            print("< {}: {}".format(k, v))
        print(response_content)
        return (True, response_content)


