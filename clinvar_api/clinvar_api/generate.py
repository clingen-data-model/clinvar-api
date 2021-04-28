import datetime
import pandas
import json


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

def parse_curie(s: str):
    """
    Takes a CURIE formatted string and returns the namespace and identifier in a tuple.
    If multiple colons appear in the string, the first is taken to be the delimiter.
    Does not allow empty namespace elements (s starts with colon).
    """
    if ":" in s:
        cidx = s.index(":")
        if cidx == 0:
            raise RuntimeError("CURIE namespace element is empty")
        ns = s[:cidx]
        value = s[cidx+1:]
        return (ns, value)
    else:
        raise RuntimeError("Could not parse CURIE: " + s)

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

def removenone(d):
    """
    Return d with null values removed from all k,v pairs in d and sub objects (list and dict only).

    When invoked by external (non-recursive) callers, `d` should be a dict object, or else behavior is undefined.
    """
    if isinstance(d, dict):
        # Recursively call removenone on values in case value is itself a dict
        d = {k:removenone(v) for (k,v) in d.items()}
        # Filter out k,v tuples where v is None
        return dict(filter(lambda t: t[1] != None, d.items()))
    elif isinstance(d, list):
        # Recursively call removenone on values in case any is a dict
        d = [removenone(v) for v in d]
        # Filter out array values which are None
        return list(filter(lambda e: e!=None, d))
    else:
        # Do not iterate into d
        return d

def default_submission_name():
    return "ClinGen_Submission_" + datetime.datetime.now().isoformat()

def row_to_clinvar_submission(
    row: pandas.Series,
    assertion_criteria: dict,
    submission_name=default_submission_name()):
    """
    Takes a subscriptable object (dict or pandas.Series, or similar) with ClinVar
    Submission Excel fields, and converts it into a ClinVar Submission API record,
    meeting the API schema for objects under `clinvarSubmission`.
    """
    # row_idx = row.name
    # misc fields

    local_id = row["A"]
    local_key = row["B"]
    record_status = row["CR"]#.replace(None, "novel") # novel or update
    if record_status is None:
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
    # clinsig_date_last_evaluated = serialize_date(row["AL"])
    # Date has already been serialized to YYYY-mm-dd
    clinsig_date_last_evaluated = row["AL"]
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

    # assertionCriteria is taken from caller
    doc = {
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
    }
    # if clinsig_mode_of_inheritance is not None:
    #     doc["clinvarSubmission"][0]["clinicalSignificance"]["modeOfInheritance"] = clinsig_mode_of_inheritance
    if record_status == "update":
        clinvar_accession = row["CQ"]
        if clinvar_accession is None or len(clinvar_accession) == 0:
            raise RuntimeError("accession (column CQ) must be provided for updates (%s)" % doc)
        doc["clinvarAccession"] = clinvar_accession

    # Remove any fields for which the value is None, or any list elements that are None
    doc = removenone(doc)
    return doc

def dataframe_to_list(df: pandas.DataFrame) -> list:
    """
    Use caution with datetime columns, as they may not be de/serialized as desired
    """
    return json.loads(df.to_json(orient="records"))

def dataframe_to_clinvar_submission_list(
        df: pandas.DataFrame,
        assertion_criteria: dict,
        submission_name: str) -> dict:
    input_records = dataframe_to_list(df)
    print(input_records)
    submission_records = []

    for record in input_records:
        submission_record = row_to_clinvar_submission(record, assertion_criteria, submission_name)
        submission_records.append(submission_record)

    return submission_records

def dataframe_to_clinvar_submission(
        df: pandas.DataFrame,
        assertion_criteria: dict,
        submission_name: str) -> dict:
    """
    Takes a ClinVar submission excel dataframe and returns a batch ClinVar Submission dictionary.
    """
    records = dataframe_to_clinvar_submission_list(df, assertion_criteria, submission_name)
    doc = {
        "clinvarSubmission": records,
        "submissionName": submission_name
    }
    return doc
