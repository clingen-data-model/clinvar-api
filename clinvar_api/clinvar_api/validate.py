import os
import json
import jsonschema
import pathlib


schema_dir = os.path.join(pathlib.Path(__file__).parent, "schemas")

def validate_batch_submission(doc: dict) -> None:
    """
    Validates a ClinVar Submission API payload against the API schema version on 2021-04-20.

    Throws jsonschema.exceptions.ValidationError on error. Returns None on success.
    """
    with open(os.path.join(schema_dir, "clinvar_submission.json")) as f:
        schema = json.load(f)
    return jsonschema.validate(doc, schema)
