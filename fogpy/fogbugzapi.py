from cStringIO import StringIO
import logging
from lxml import etree
import threading
import urllib

l = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)

class NotLoggedOnError(Exception):
    def __init__(self, msg):
        self.msg = msg
    def __unicode__(self):
        return self.msg

class FogBugzAPI(object):
    def __init__(self, base_url, username, password):
        self.base_url = base_url
        self.username, self.password = username, password
        self.login(username, password)

    def login(self, username, password):
        resp = self.call('logon', notoken=True, email=username, 
                         password=password)
        self._token = resp.find('token').text
        l.info('%s logon successful'%username)

    def logout(self):
        resp = self.call('logoff')
        l.info('logged out')

    def call(self, *args, **kwargs):
        try:
            return self._call(*args, **kwargs)
        except NotLoggedOnError:
            self.login(self.username, self.password)
            return self._call(*args, **kwargs)

    def _call(self, cmd, notoken=False, **kwargs):
        url_args = kwargs.copy() 
        url_args['cmd'] = cmd
        if not notoken:
            url_args['token'] = self._token
        url = self.base_url + '?' + urllib.urlencode(url_args)
        l.debug('Calling ' + url)
        resp = urllib.urlopen(url)
        resp_txt = resp.read()
        xml_resp = etree.parse(StringIO(resp_txt))
        if resp.getcode() != 200:
            msg = "%d error trying to do %s"%(resp.getcode(), cmd)
            l.error(msg)
            raise RuntimeError(msg)
        elif xml_resp.find('error') is not None:
            msg = "%s error: %s"%(cmd, xml_resp.find('error').text)
            l.error(msg)
            l.debug(etree.tostring(xml_resp))
            if xml_resp.find('error').values()[0] == '3':
                raise NotLoggedOnError(msg)
            raise RuntimeError(msg)

        return xml_resp

class FBApiObject(object):
    """Base object for retrieving and saving stuff through the API"""
    def __init__(self, base_url=None, username=None, password=None):
        if base_url is None:
            # try to get it from a global login
            self._fbapi = thread.local().fbapi
        else:
            self._fbapi = FogBugzAPI(base_url, username, password)

    pass

class Bug(FBApiObject):
    pass

class Person(FBApiObject):
    pass

def login(base_url, username, password):
    """Login to API globally"""
    threading.local().fbapi = FogBugzAPI(base_url, username, password)

