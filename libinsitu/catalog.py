# Handling fetch and parsing of Thredds server

import xml.etree.ElementTree as ET

from typing import Dict
from urllib.parse import urljoin, urlsplit
import pprint

from requests import HTTPError, Session

from libinsitu import parallel_map
from libinsitu.log import info

NS={
    "thredds" : "http://www.unidata.ucar.edu/namespaces/thredds/InvCatalog/v1.0",
    "xlink" : "http://www.w3.org/1999/xlink"}

XLINK = "{http://www.w3.org/1999/xlink}"


class AutoRepr :
    def __repr__(self):
        return pprint.pformat(self.__dict__)

class Dataset(AutoRepr) :
    def __init__(self, id, name, size) :
        self.id = id
        self.name = name
        self.size = size
        self.services = dict() # Dict of service type => URL

class Catalog(AutoRepr) :
    def __init__(self, id, name, description, url, link) :
        self.id = id
        self.name = name
        self.description = description
        self.url = url
        self.link = link
        self.authorized = None
        self.datasets : Dict[str, Dataset]= dict()
        self.catalogs : Dict[str, Catalog] = dict() # Dict of sub catalogs
        self.services = dict() # Dict of service type => URL

def parse_services(catalog, base):

    res = dict()
    for service in catalog.findall('.//thredds:service', NS):
        name = service.get("name")
        url = service.get("base")
        if url != "":
            res[name] = base + url
    return res

def parse_catalog(el, url, id=None, name=None) :
    """Parse catalog from 'Dataset' element of root catalog or datasetREf/metadata element """

    if id is None :
        name = el.attrib['name']
        id = el.attrib['ID']

    # find doc
    metadata = el.find('thredds:metadata', NS)  # Optionnal nested node "metadata"
    if metadata is None:
        metadata = el
    docs = metadata.findall('thredds:documentation', NS)
    description = None
    link = None
    for doc in docs:
        if doc.get("type") == "summary":
            description = doc.text
        else:
            link_ = doc.get('{%s}href' % NS["xlink"])
            if link_ is not None:
                link = link_
    return Catalog(id, name, description, url, link)

def extract_sub(url, subCatEl) :
    id = subCatEl.attrib[XLINK + "title"]
    href = subCatEl.attrib[XLINK + "href"]
    sub_url = urljoin(url, href)
    return (id, sub_url)

def fetch_catalog(url, session=None, recursive=True, parallel=True) :

    info("Fetching : %s" % url)

    if session is None :
        session = Session()

    base = base_url(url)
    xml = http_get(url, session)

    catalogEl = ET.fromstring(xml)
    datasetEl = catalogEl.find('thredds:dataset', NS)

    catalog = parse_catalog(datasetEl, url)
    catalog.services = parse_services(catalogEl, base)

    # Parse or fetch sub catalogs

    sub_elements = list(datasetEl.findall("thredds:catalogRef", NS))

    def fetch_rec(subCatEl) :
        id, sub_url = extract_sub(url, subCatEl)

        try:
            sub_catalog = fetch_catalog(sub_url, session, parallel=parallel)
            return (id, sub_catalog)
        except HTTPError as e:
            if e.response.status_code == 401:
                print("URL %s not authorized." % e.request.url)
            else:
                raise e

    if recursive :
        # Common loop for sequential of parallel fetch
        for id, sub_catalog in parallel_map(fetch_rec, sub_elements, parallel):
            catalog.catalogs[id] = sub_catalog
    else :
        for subCatEl in sub_elements :
            id, sub_url = extract_sub(url, subCatEl)
            catalog.catalogs[id] = parse_catalog(subCatEl, sub_url, id, id)

    # Datasets
    datasets = datasetEl.findall("thredds:dataset", NS)

    for dataset_el in datasets :

        uri = dataset_el.attrib["urlPath"]
        id = dataset_el.attrib["ID"]
        name = dataset_el.attrib["name"]
        size = float(dataset_el.find("thredds:dataSize", NS).text)

        dataset = Dataset(id, name, size)
        dataset.services = {key: base + uri for key, base in catalog.services.items()}

        catalog.datasets[dataset.name] = dataset

    return catalog

def base_url(url) :
    parts = urlsplit(url)
    return  "%s://%s" % (parts.scheme, parts.netloc)



def http_get(url, session) :

    #print("fetching : %s" % url)

    res = session.get(url)
    res.raise_for_status()

    res.encoding = res.apparent_encoding
    return res.text