#!/usr/bin/env python
r"""Create FogBugz time reports in CSV format

Usage: %prog [options] arg1 arg2

example:
    %prog -u foo@bar.com -p mypassword -o /tmp/out.xls \
            -b https://ecometrica.fogbugz.com/api.asp \
            2011-10-29T00:00:00Z 2011-11-30T00:00:00Z

You can also create a file called local_settings.py in the same folder
as %prog, and define base_url, username and password in there instead
of specifying -u, -p and -b.
"""

import codecs
from collections import defaultdict, namedtuple
from cStringIO import StringIO
import datetime as dt
import iso8601
import logging
from lxml import etree
from optparse import OptionParser
import sys
import urllib
import urllib2

from fogpy.fogbugzapi import FogBugzAPI

l = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)

settings = {
}

try:
    import local_settings
    for k, v in local_settings.__dict__.iteritems():
        if not k.startswith('__'):
            settings[k] = v
except ImportError:
    pass

class DefaultDictForKey(defaultdict):
    def __init__(self, default_factory):
        self._default_factory = default_factory

    def __missing__(self, key):
        return self._default_factory(key)

class TimeReporting(object):
    
    def __init__(self, username, password, base_url, 
                 start_date=None, end_date=None, prefetch=False):
        self.fbapi = FogBugzAPI(base_url, username, password)
        self.bugs = DefaultDictForKey(self.get_buginfo)
        self.devs = DefaultDictForKey(self.get_devinfo)
        self.hours_perdev = DefaultDictForKey(self.get_hours_for_dev)
        self.start_date, self.end_date = start_date, end_date
        self.all_tags = set()
        self.bugs_with_no_tags = set()
        self.base_url = base_url
        if prefetch:
            self.get_buginfo('all')

    def logout(self):
        self.fbapi.logout()
    
    def url_for_bug(self, bug_id):
        url_elements = list(urllib2.urlparse.urlsplit(self.base_url))
        url_elements[2] = '/?%d' % bug_id
        url_elements[3] = ''
        url_elements[4] = ''
        return urllib2.urlparse.urlunsplit(url_elements)

    def fb_filter_for_bugs(self, bug_id_list):
        return ('OrderBy:Project ' + ' OR '.join('ixbug:%s'%b 
                                                 for b in bug_id_list))

    def get_devinfo(self, dev_id):
        """Actually just gets info for all devs at once"""
        resp = self.fbapi.call('listPeople')
        for p in resp.find('people').iterfind('person'):
            dev_id = int(p.find('ixPerson').text)
            self.devs[dev_id] = {
                'name': p.find('sFullName').text,
                'email': p.find('sEmail').text
            }
        return self.devs[dev_id]

    def get_buginfo(self, bug_list):
        """Fill in info for one or more bugs, or 'all' bugs"""
        if bug_list == 'all':
            query = '""'
        elif isinstance(bug_list, (int, long)):
            query = 'ixBug:%d' % bug_list
        else:
            query = ' or '.join('ixBug:%d' % bug_id for bug_id in bug_list)
        resp = self.fbapi.call('search', q=query, 
                               cols='tags,sTitle,ixBug,sProject,dtResolved')
        for c in resp.find('cases').findall('case'):
            bug_id = int(c.find('ixBug').text)
            project = c.find('sProject').text
            self.bugs[bug_id] = {
                'title': c.find('sTitle').text,
                'tags': ['%s-%s'%(project, t.text) 
                         for t in c.find('tags').findall('tag')],
                'project': project,
                'resolved': c.find('dtResolved').text
            }
        return self.bugs[bug_id]

    def get_hours_for_dev(self, dev_name):
        self.get_all_hours_per_tag_per_dev(self.start_date, self.end_date)
        return self.hours_perdev[dev_name]

    def get_all_hours_per_tag_per_dev(self, start=None, end=None):
        if start is None: start = self.start_date
        if end is None: end = self.end_date
        self.hours_perdev = defaultdict(lambda: defaultdict(int))

        # Find all timesheet hours
        intervals = self._get_intervals_in_daterange(start, end)
        for i in intervals:
            try:
                self._parse_interval(i)
            except Exception, e:
                l.error('Problem with interval: ' + etree.tostring(i))
                raise e

        # now add non-timesheet elapsed time for bugs resolved in that
        # period, using resolvedby as dev
        resp = self.fbapi.call(
            'search', q='resolved:"%s..%s"'%(start.strftime('%m/%d/%Y'),
                                             end.strftime('%m/%d/%Y')),
            cols=('ixBug,ixPerson,hrsElapsedExtra,tags,sProject,'
                  'ixPersonResolvedBy'),
        )
        for b in resp.find('cases').iterfind('case'):
            bug_id = int(b.find('ixBug').text)
            dev_name = self.devs[int(b.find('ixPersonResolvedBy').text)]['name']
            hours = float(b.find('hrsElapsedExtra').text)
            tags = self.bugs[bug_id]['tags']
            project = self.bugs[bug_id]['project']
            for t in tags:
                self.hours_perdev[dev_name]['%s-%s'%(project, t)] += hours
            if not tags:
                self.hours_perdev[dev_name]['None'] += hours
            self.hours_perdev[dev_name]['total'] += hours
            self.hours_perdev[dev_name]['non-timesheet'] += hours
            if tags:
                self.all_tags.update(tags)
            else:
                self.bugs_with_no_tags.add(bug_id)

        if self.bugs_with_no_tags:
            l.warning(u"Some bugs covered by this timesheet have no "
                      u"associated tags: " 
                      + ', '.join(`b` for b in self.bugs_with_no_tags))
        return self.hours_perdev
    
    def get_hours_details(self, start=None, end=None):
        if start is None: start = self.start_date
        if end is None: end = self.end_date

        TimeEntry = namedtuple('TimeEntry', 
                               ('date', 'bug_num', 'title', 'dev_name', 'hours', 
                                'project', 'tag', 'url', 'type'))
        entries = []
        # Find all timesheet hours
        intervals = self._get_intervals_in_daterange(start, end)
        for i in intervals:
            hours = (
                iso8601.parse_date(i.find('dtEnd').text)
                - iso8601.parse_date(i.find('dtStart').text) 
            ).total_seconds() / 3600.
            dev_name = self.devs[int(i.find('ixPerson').text)]['name']
            bug_id = int(i.find('ixBug').text)
            b = self.bugs[bug_id]
            tags = b['tags'] or ['None', ]
            for t in tags:
                entries.append(
                    TimeEntry(i.find('dtEnd').text, bug_id, b['title'], 
                              dev_name, hours, b['project'], t, 
                              self.url_for_bug(bug_id), 'timesheet')
                )
            self.all_tags.update(b['tags'])
            if not b['tags']:
                self.bugs_with_no_tags.add(bug_id)

        # now add non-timesheet elapsed time for bugs resolved in that
        # period, using resolvedby as dev
        resp = self.fbapi.call(
            'search', q='resolved:"%s..%s"'%(start.strftime('%m/%d/%Y'),
                                             end.strftime('%m/%d/%Y')),
            cols=('ixBug,ixPerson,hrsElapsedExtra,tags,sProject,'
                  'ixPersonResolvedBy'),
        )
        for b in resp.find('cases').iterfind('case'):
            bug_id = int(b.find('ixBug').text)
            dev_name = self.devs[int(b.find('ixPersonResolvedBy').text)]['name']
            hours = float(b.find('hrsElapsedExtra').text)
            bug = self.bugs[bug_id]
            tags = bug['tags'] or ['None', ]
            for t in tags:
                entries.append(
                    TimeEntry(bug['resolved'], bug_id, bug['title'], dev_name, hours, 
                              bug['project'], t, self.url_for_bug(bug_id), 
                              'elapsed')
                )
            self.all_tags.update(bug['tags'])
            if not bug['tags']:
                self.bugs_with_no_tags.add(bug_id)

        if self.bugs_with_no_tags:
            l.warning(u"Some bugs covered by this timesheet have no "
                      u"associated tags: " 
                      + ', '.join(`b` for b in self.bugs_with_no_tags))
        self.hours_details = entries
        return entries
    
    def _parse_interval(self, i):
        hours = (
            iso8601.parse_date(i.find('dtEnd').text)
            - iso8601.parse_date(i.find('dtStart').text) 
        ).total_seconds() / 3600.
        dev_name = self.devs[int(i.find('ixPerson').text)]['name']
        bug_id = int(i.find('ixBug').text)
        tags = self.bugs[bug_id]['tags']
        self.all_tags.update(tags)
        for t in tags:
            self.hours_perdev[dev_name][t] += hours
        if not tags:
            self.hours_perdev[dev_name]['None'] += hours
            self.bugs_with_no_tags.add(bug_id)
        self.hours_perdev[dev_name]['total'] += hours

    def _get_intervals_in_daterange(self, start, end):
        resp = self.fbapi.call(cmd='listIntervals', ixPerson=1, 
                               dtStart=start.isoformat()+'Z', 
                               dtEnd=end.isoformat()+'Z')
        return resp.find('intervals').iterfind('interval')
    
    def csv_cumulative_hours(self):
        if not self.hours_perdev:
            self.get_all_hours_per_tag_per_dev()

        # we want to show the columns in tag alphabetical order, with 
        # none as the first column, and total as the last
        tags = sorted(self.all_tags.copy())
        if 'None' in tags: tags.remove('None')
        tags.insert(0, 'None')
        if 'total' in tags: tags.remove('total')
        tags.append('total')
        if 'non-timesheet' in tags: tags.remove('non-timesheet')
        tags.append('non-timesheet')
        lines = []
        lines.append('dev name\t' + '\t'.join(tags) + '\n')
        for k, v in self.hours_perdev.iteritems():
            lines.append(k + '\t' + '\t'.join(`v[t]` for t in tags))

        lines.append('')
        if self.bugs_with_no_tags:
            lines.append('Bugs with no tags:' + '\t' 
                         + ' '.join(`b` for b in self.bugs_with_no_tags))
            fb_filter = self.fb_filter_for_bugs(self.bugs_with_no_tags)
            lines.append('Equivalent fogbugz filter:' + fb_filter)
            l.info("No tags fb filter: " + fb_filter)
        else:
            lines.append('Bugs with no tags:\tnone' )
        lines.append('')
        lines.append('Notes')
        lines.append("\tDon't count non-timesheet time")
        lines.append("\tSome hours count in multiple tags, so total is less "
                     "than the sum of tags")
        return '\n'.join(lines)
    
    def csv_detailed_hours(self):
        lines = []
        lines.append("Hours details for %s-%s\n" % (self.start_date, self.end_date))
        if self.bugs_with_no_tags:
            lines.append('Bugs with no tags:' + '\t' 
                         + ' '.join(`b` for b in self.bugs_with_no_tags))
            fb_filter = self.fb_filter_for_bugs(self.bugs_with_no_tags)
            lines.append('Equivalent fogbugz filter:\t' + fb_filter)
            l.info("No tags fb filter: " + fb_filter)
        else:
            lines.append('Bugs with no tags:\tnone' )
        lines.append('date\tbug_num\ttitle\tdev_name\thours\tproject\ttag\turl\ttype')
        for entry in self.hours_details:
            lines.append('\t'.join('%s'%i for i in entry))

        return '\n'.join(lines)


if __name__=='__main__':
    usage = __doc__
    parser = OptionParser(usage=usage)
    parser.add_option("-u", "--username", dest="username",
                      help="username to log into fogbugz [%default]",
                      default=settings.get('username', ''))
    parser.add_option("-p", "--password", dest="password",
                      help="password to log into fogbugz[%default] ",
                      default=settings.get('password', ''))
    parser.add_option("-o", "--output", dest="outfile", metavar="FILE",
                      help="output TSV data to file instead of stdout")
    parser.add_option("-b", "--baseurl", dest="base_url",
                      help="Base URL for FogBugz API [%default]",
                      default=settings.get('base_url', ''))
    parser.add_option("-l", "--long", dest="long", default=False,
                      action='store_true', 
                      help="Dumps highly detailed logs of timesheet data.")
    parser.add_option("-f", "--prefetch", dest="prefetch", default=False,
                      action='store_true', 
                      help="Prefetch info about all bugs (useful for big reports).")

    (options, args) = parser.parse_args()

    errors = 0
    if len(args) < 2:
        l.error("You need to provide start and end date, in iso8601 format")
        parser.print_help
        errors += 1
    if options.username is None:
        l.error("No username given")
        errors += 1
    if options.password is None:
        l.error("No password given")
        errors += 1
    if errors:
        parser.print_help()
        sys.exit(1)

    start_date = iso8601.parse_date(args[0])
    end_date = iso8601.parse_date(args[1])

    #import ipdb; ipdb.set_trace()
    tr = TimeReporting(options.username, options.password,
                       options.base_url, start_date, end_date, 
                       prefetch=options.prefetch)
    try:
        if options.long:
            hours = tr.get_hours_details()
            csv_hours = tr.csv_detailed_hours()
        else:
            hours = tr.get_all_hours_per_tag_per_dev()
            csv_hours = tr.csv_cumulative_hours()
    finally:
        tr.logout()

    if options.outfile:
        codecs.open(options.outfile, 'w', 'utf8').write(csv_hours)
    else:
        print hours


