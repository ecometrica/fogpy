#!/usr/bin/env python

import optparse

from fogpy.fogbugzapi import FogBugzAPI

settings = {
    'base_url': 'https://ecometrica.fogbugz.com/api.asp',
    'username': 'eric@ecometrica.org', 
    'password':'robEatEu'
}

API_BASE_URL = 'https://ecometrica.fogbugz.com/api.asp'

class TimeReporting(object):
    
    def __init__(self, base_url, username, password):
        self.fbapi = FogBugzAPI(API_BASE_URL, username, password)

    def list_intervals_for_bug(self, bugnum):
        resp = self.fbapi.call(cmd='listIntervals', ixPerson=1, dtBug=1107)
        return resp


if __name__=='__main__':
    tr = TimeReporting(settings['base_url'], settings['username'], 
                       settings['password'])
    resp = tr.list_intervals_for_bug(1231)


