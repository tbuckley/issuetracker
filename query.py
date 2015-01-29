import httplib2
import copy
from urllib import urlencode
from urlparse import urlunsplit
import xml.etree.ElementTree as ET

def get_first_child_by_tag(page, tag):
    """Return the first child of `page` with the given tag."""
    for child in page:
        if child.tag.endswith(tag):
            return child

def count_for_page(page):
    """Get the count for the given page."""
    return int(get_first_child_by_tag(page, "totalResults").text)

def get_xml_tree_for_url(client, url):
    """Get the xml tree for the given url."""
    (_, content) = client.request(url, "GET")
    return ET.fromstring(content)

def get_next_page(client, page):
    """Get the next page of issues if one exists. Return None otherwise."""
    for child in page:
        if child.tag.endswith("link") and child.attrib["rel"] == "next":
            url = child.attrib["href"]
            return get_xml_tree_for_url(client, url)
    return None

def get_issues_from_page(page):
    """Return a list of the issues from the given page."""
    entries = []
    for child in page:
        if child.tag.endswith("entry"):
            entries.append(child)
    return entries

class IssuesQuery(object):
    """Query the Google Code issue tracker. Immutable query object."""

    def __init__(self, project, client=None, params=None):
        if client is None:
            client = httplib2.Http()

        self._project = project
        self._client = client
        self._params = params or {"can": "open"}

    def can(self, can):
        """Limit the query to a specific set of issues."""
        assert can in ["all", "open", "owned", "reported", "starred", "new", "to-verify"]
        params = copy.deepcopy(self._params)
        params["can"] = can
        return IssuesQuery(self._project, client=self._client, params=params)

    def label(self, label):
        """Limit the query to issues with the given label."""
        params = copy.deepcopy(self._params)
        params["label"] = label
        return IssuesQuery(self._project, client=self._client, params=params)

    def query(self, query):
        """Set the search string for the query."""
        params = copy.deepcopy(self._params)
        params["q"] = query
        return IssuesQuery(self._project, client=self._client, params=params)

    def fetch_page(self, offset=0, limit=25):
        """Fetch the results for the query using offset and limit."""
        params = copy.deepcopy(self._params)
        params["max-results"] = limit
        params["start-index"] = offset + 1  # 1-based indexing
        query = urlencode(params)
        path = "/feeds/issues/p/{project}/issues/full".format(project=self._project)
        url = urlunsplit(("https", "code.google.com", path, query, ""))
        return get_xml_tree_for_url(self._client, url)

    def fetch_all_issues(self, verbose=False):
        """Fetch all results for the query."""
        page = self.fetch_page()

        issues = []
        while page is not None:
            issues += get_issues_from_page(page)
            page = get_next_page(self._client, page)
        if verbose:
            print
        return issues

    def count(self):
        """Get the number of results for the query."""
        page = self.fetch_page()
        return count_for_page(page)
