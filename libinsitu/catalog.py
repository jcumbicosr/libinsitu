from siphon.catalog import TDSCatalog
from concurrent.futures import ThreadPoolExecutor
from libinsitu.log import info
from itertools import zip_longest
import re

def match_part(pattern, value) :
    if not "*" in pattern :
        return pattern == value

    pattern = pattern.replace("*", ".*")
    return re.match(pattern, value) is not None


def pattern_matches(url, base_url, pattern):

    if pattern is None :
        return True

    relative_url = url.replace(base_url, "").replace("catalog.xml", "").strip("/")
    pattern = pattern.strip("/")

    info("Matching pattern:{} rel_url:{}".format(pattern, relative_url))

    for pattern_part, path_part in zip_longest(pattern.split("/"), relative_url.split("/")) :
        if path_part is None :
            continue
        if pattern_part is None: # Path longer than pattern ?
            return False

        if not match_part(pattern_part, path_part):
            return False

    return True


def _list_dataset_urls_rec(current_url, base_url, pattern=None, service="OpenDAP"):
    """Recursive / parallel fetch of OpenDap dataset URLs from Thredds catalog.xml"""

    info(f"Loading catalog {current_url}")

    catalog = TDSCatalog(current_url)


    # List datasets of requested service
    ds_urls = list(url for dataset in catalog.datasets.values() for serv, url in dataset.access_urls.items() if serv == service)

    if len(ds_urls) > 0 :
        info(f"Found datasets : \n {ds_urls}")

    # Catalog ref
    catalog_ref_urls = list(ref.href for ref in catalog.catalog_refs.values() if pattern_matches(ref.href, base_url, pattern))

    def rec_func(url) :
        return _list_dataset_urls_rec(url, base_url=base_url, pattern=pattern, service=service)

    # Recursive call on catalog refs
    with ThreadPoolExecutor() as executor:
        for other_urls in executor.map(rec_func, catalog_ref_urls) :
            ds_urls += other_urls

    return ds_urls


def list_dataset_urls(base_url, pattern=None, service="OpenDAP"):
    return _list_dataset_urls_rec(current_url=base_url, base_url=base_url, pattern=pattern, service=service)






