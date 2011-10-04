from cStringIO import StringIO
from lxml import etree
import urllib

class FogBugzAPI(object):
    def __init__(self, base_url, username, password):
        self.base_url = base_url
        self.login(username, password)

    def login(self, username, password):
        resp = self.call('logon', notoken=True, email=username, 
                         password=password)
        self._token = resp.find('token').text

    def call(self, cmd, notoken=False, **kwargs):
        url_args = kwargs.copy() 
        url_args['cmd'] = cmd
        if not notoken:
            url_args['token'] = self._token
        url = self.base_url + '?' + urllib.urlencode(url_args)
        resp = urllib.urlopen(url).read()
        xml_resp = etree.parse(StringIO(resp))
        return xml_resp

