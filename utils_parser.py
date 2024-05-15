import json
import requests
import time
from urllib.error import HTTPError
from future.utils import iteritems

def get_json_by_uri(uri):
    # Retrieves JSON data
    uri = uri[0:4] + 's' + uri[4:]
    headers = requests.utils.default_headers()
    headers.update({'User-Agent': 'Mozilla/5.0'})
    try:
        response = requests.get(uri+'.json', headers=headers)
        response.raise_for_status()
        return response.json()
    except (HTTPError, requests.exceptions.HTTPError):
        return None

def get_name(uri):
    # Get applicant/inventor/agent names
    names = []
    for u in uri:
        jsn = get_json_by_uri(u)
        if jsn is None:
            continue
        if 'result' in jsn.keys():
            names.append(jsn['result']['primaryTopic']['fn'])
    return names

def get_cpc(uri):
    # Take only the CPC code out of uri
    cpc = []
    for u in uri:
        cpc.append(u.split('/')[-1][0:-1])
    return cpc

# include this prefixes in SPARQL query
PREFIXES = """
prefix cpc: <http://data.epo.org/linked-data/def/cpc/>
prefix dcterms: <http://purl.org/dc/terms/>
prefix ipc: <http://data.epo.org/linked-data/def/ipc/>
prefix mads: <http://www.loc.gov/standards/mads/rdf/v1.rdf>
prefix owl: <http://www.w3.org/2002/07/owl#>
prefix patent: <http://data.epo.org/linked-data/def/patent/>
prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#>
prefix skos: <http://www.w3.org/2004/02/skos/core#>
prefix st3: <http://data.epo.org/linked-data/def/st3/>
prefix text: <http://jena.apache.org/text#>
prefix vcard: <http://www.w3.org/2006/vcard/ns#>
prefix xsd: <http://www.w3.org/2001/XMLSchema#>
"""

def application_query(start_date, end_date, auth):
    # Find all publications from authority auth between start_date and end_date
    return """SELECT ?apn ?pub {
      ?application rdf:type patent:Application;
          patent:applicationNumber ?apn;
          patent:publication ?pub;
          patent:filingDate        ?filingDate; 
          patent:applicationAuthority/skos:notation ?auth;
          
      .
      FILTER(?filingDate >= xsd:date(""" + start_date + ") && ?filingDate < xsd:date(""" + end_date + ") && ?auth = " + auth + """)}
    """
    
def sparql_get_publications(start_date, end_date, auth, sparql):
    """
        Parameters
            date (string): date to perform query for, written as: 
                   '"YEAR-MONTH-DAY"' (all with numbers)
            auth (string): authority, defined as: '"EP"' (or some other)
        ---------------
        Returns
            list: publiction URIs for specific date and authority
    """
    query = PREFIXES + application_query(start_date, end_date, auth)
    sparql.setQuery(query)
    q = sparql.queryAndConvert()
    return q['results']['bindings']


def publication_query(uri):
    return " SELECT DISTINCT * { <" + uri + """> ?title ?abstract;
              rdf:type patent:Publication;
                  patent:titleOfInvention ?toi;.
            FILTER(langMatches(lang(?toi),""" +  '"en"))}'

def sparql_extract_publications(uri, sparql):
    """
        Parameters
            uri (string): epo publication URI
        ---------------
        Returns
            dict: extracted publication data
    """
    query = PREFIXES + publication_query(uri)
    sparql.setQuery(query)
    try:
        q = sparql.queryAndConvert()
    except(HTTPError, requests.exceptions.HTTPError):
        return []
    return q['results']['bindings']

def name_converter(companies):
    result = list()
    mapping = {', INC.':' INC.',
           ' LIMITED':' LTD.',
           ' LTD.,':' LTD.',
           ' LTD':' LTD.',
           ' E. V.':' E.V.',
           ' B.V':' B.V.',
           '(S.A.S.)':'S.A.S.',
           'S.A.S.':' S.A.S.',
           ' S.A.S': ' S.A.S.',
           ' SAS ':' S.A.S.',
           ' ( S.A.S. )':' S.A.S.',
           ' SP.Z O.O.':' SP. Z O.O.',
           ' SP.Z.O.O.':' SP. Z O.O.',
           ' SP Z O.O.':' SP. Z O.O.',
           ' CO.,':' CO.',
           ' CO.,':' CO.',
           ' CO ':' CO.',
           ' COMPANY':' CO.',      # https://www.findlaw.com/smallbusiness/business-operations/what-does-co-mean-in-a-business-name-.html#:~:text=%E2%80%9CCo.%22%20usually%20stands%20for,of%20the%20business's%20legal%20structure.
           'AKTIENGESELLSCHAFT':'AG',
           ' CORPORATION':' CORP.',
           ' SA ':' S.A.',      # https://en.wikipedia.org/wiki/S.A._(corporation)
           ' AS ':' S.A.',
           ' S/A':' S.A.',
           ' A/S':' S.A.',
           ' LTDA.':' LTDA',
           ' LLC.':' L.L.C.',
           ', LLC ':' L.L.C.',
            ' LLC ':' L.L.C.',
           'Ü':'U',
           'À':'A',
           'É':'E',
           'Ô':'O',
           'È':'E',
           'Ä':'A',
           '\'' : '',
           '  ':' ',
           '..':'.',
           ' - ':' ',
           ')':'',
           '(':'',
           ' Ag ':' AG',
           ' Gmbh ':' GmbH',
           ' Ges. M.B.H.':' GmbH',
           '"':''}

    for c in companies:
        c = c.upper()
        c = c + ' '
        c = c.replace('\n', '')
        for k,v in iteritems(mapping):
            c = c.replace(k, v)
        c = c.title()
        c = c.strip()             # needs to be after the for loop because of the string replacements
        result.append(c)
    result = set(result)
    return list(result)
