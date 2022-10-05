from sphinx_gitref.remote import Remote
import re

class PrivateGitlab(Remote):

    remote_match = [
        re.compile(r"^https://git.sophia.mines-paristech.fr/.*/(?P<repo>.+?)(\.git)?$"),
    ]
    url_pattern = "https://git.sophia.mines-paristech.fr/oie/{repo}/-/blob/{branch}/{filename}"
    url_pattern_line = "#L{line}"