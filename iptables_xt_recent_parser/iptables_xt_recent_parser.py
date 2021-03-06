#!/usr/bin/env python

#~ Copyright 2017 Giuseppe De Marco <giuseppe.demarco@unical.it>
#~ 
#~ Permission is hereby granted, free of charge, to any person obtaining a 
#~ copy of this software and associated documentation files (the "Software"), 
#~ to deal in the Software without restriction, including without limitation 
#~ the rights to use, copy, modify, merge, publish, distribute, sublicense, 
#~ and/or sell copies of the Software, and to permit persons to whom the Software 
#~ is furnished to do so, subject to the following conditions:
#~ 
#~ The above copyright notice and this permission notice shall be included 
#~ in all copies or substantial portions of the Software.
#~ 
#~ THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS 
#~ OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, 
#~ FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL 
#~ THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER 
#~ LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING 
#~ FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER 
#~ DEALINGS IN THE SOFTWARE.

import re
import sys
import datetime
from copy import copy
import os
import subprocess

_debug = False
_fpath = '/proc/net/xt_recent/BLACKLIST'

# Modify to work with python 2.7.x
_kernel_config_path = '/boot/config-'+subprocess.check_output(['uname', '-r']).strip()

_datetime_format = '%Y-%m-%d %H:%M:%S'


class JiffyTimeConverter(object):
    def __init__(self, kernel_config_path=_kernel_config_path):
        
        self.hz = JiffyTimeConverter.system_hz(kernel_config_path=_kernel_config_path)
        self.jiffies = JiffyTimeConverter.system_jiffies()
        
    def seconds_ago(self, jiffies_timestamp):
        return ((JiffyTimeConverter.system_jiffies() - int(jiffies_timestamp) ) / self.hz )
    
    def minutes_ago(self, jiffies_timestamp):
        return self.seconds_ago / 60 
    
    def datetime(self, jiffies_timestamp):
        now = datetime.datetime.now()
        td = datetime.timedelta(seconds=self.seconds_ago(jiffies_timestamp))
        return now - td
    
    def convert_to_format(self, jiffy_timestamp, strftime=_datetime_format):
        return self.datetime(jiffy_timestamp).strftime(strftime)
    
    @staticmethod
    def check_system_jiffies():
        """
        It only prints 12 times how many jiffies runs in a second
        If kernel's CONFIG_HZ is 250 there will be 250 jiffies in a second
        It's funny to see that sometimes this value gets some oscillations (251,250,250,251...)
        """
        last_jiffies = 0
        hz = 0
        cnt = 0
        while cnt < 12:
            new_jiffies = JiffyTimeConverter.system_jiffies()
            hz = new_jiffies - last_jiffies
            last_jiffies = new_jiffies
            time.sleep(1)
            print(hz)
            print(new_jiffies)
            print('')
            cnt += 1
        return hz
    
    @staticmethod
    def system_uptime():
        """
        returns system uptime in seconds
        """
        from datetime import timedelta
        
        with open('/proc/uptime', 'r') as f:
            uptime_seconds = float(f.readline().split()[0])
            uptime_string = str(timedelta(seconds = uptime_seconds))
        
        return uptime_seconds
    
    @staticmethod
    def system_jiffies():
        """
        returns current system jiffies
        """
        _jiffies_pattern = r'(?:jiffies[ =:]*?)([0-9]+)'
        
        with open('/proc/timer_list') as f:
            q = re.search(_jiffies_pattern, f.read())
            if not q:
                 sys.exit('Cannot determine jiffies in /proc/timer_list.\n\
        Please check _jiffies_pattern\n\n')
            else:
                _jiffies = q.groups()[0]
        return float(_jiffies)
    
    @staticmethod
    def system_btime():
        """
        The "btime" line gives the time at which the system booted, in seconds since
        the Unix epoch.
        """
        _pattern = r'(?:btime[ =:]*?)([0-9]+)'
        
        with open('/proc/stat') as f:
            q = re.search(_pattern, f.read())
            if not q:
                 sys.exit('Cannot determine btime in /proc/stat.\n\
        Please check _jiffies_pattern\n\n')
            else:
                _btime = q.groups()[0]
        return float(_btime)
    
    @staticmethod
    def system_hz(kernel_config_path=_kernel_config_path):        
        # HZ defined how many ticks the internal timer interrupt in 
        # 1sec, which means the number of jiffies count in 1 sec.
        _HZ_pattern = r'(?:CONFIG_HZ[ =:]*?)([0-9]+)'
        
        with open(kernel_config_path) as f:
            q = re.search(_HZ_pattern, f.read())
            if not q:
                 sys.exit('Cannot determine kernel HZ freq\n\n')
            else:
                _hz = q.groups()[0]
        return float(_hz)   

class XtRecentRow(object):
    def __init__(self, row, debug=False):
        """
        where row is:
        src=151.54.175.212 ttl: 49 last_seen: 5610057758 
        oldest_pkt: 11 5610048214, 5610048235, 5610048281, [...]
        """
        # regexp
        _src_pattern = r'(?:src\=)(?P<src>[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3})'
        _ttl_pattern = r'(?:ttl\:\ )(?P<ttl>[0-9]+)'
        _last_seen_pattern = r'(?:last_seen\:\ )(?P<last_seen>[0-9]+)'
        _hitcount_pattern = r'(?:hitcount\:\ )(?P<hitcount>[0-9]+)'
        _oldest_pkt_pattern = r'(?:oldest_pkt\:\ )(?P<oldest_pkt>[0-9]+)'
        _timestamps_pattern = r'(?:oldest_pkt\:\ [0-9]*)(?P<timestamps>[0-9 ,]+)'
        #
        d = {}
        d.update(re.search( _src_pattern, row ).groupdict())
        #~ self.hitcount   = d.update(re.search( _hitcount_pattern, row ).groupdict())
        d.update(re.search( _ttl_pattern, row ).groupdict())
        d.update(re.search( _last_seen_pattern, row ).groupdict())
        d.update(re.search( _oldest_pkt_pattern, row ).groupdict())
        
        for i in d:
            setattr(self, i, d[i])
        self.raw_history    = re.search( _timestamps_pattern, row ).groups()[0] #.replace(' ', '').split(',')
        self.history = [ i.strip() for i in self.raw_history.split(',')]
        
        if debug: 
            print(d)
            print(self.history)
            print('')
        
    def convert_jiffies(self):
        """
        converts jiffies value in datetime object
        then returns a copy of self with all the jiffies converted
        """
        d = copy(self)
        jt = JiffyTimeConverter()
        d.last_seen = jt.datetime(d.last_seen)
        d.oldest_pkt = jt.datetime(d.oldest_pkt)

        d.history = [ jt.datetime(i) for i in self.history]
        return d

    def format_jiffies(self, strftime_format=_datetime_format):
        """
        displays datetime values in a preferred datetime string format
        returns a copy of the object
        """
        d = self.convert_jiffies()
        jt = JiffyTimeConverter()
        
        d.last_seen = jt.convert_to_format(d.last_seen, strftime_format)
        d.oldest_pkt = jt.convert_to_format(d.oldest_pkt, strftime_format)
        
        d.history = [ jt.convert_to_format(i, strftime_format) for i in self.history]
        return d

    def __repr__(self):
        return '%s, last seen: %s after %s connections' % ( self.src, self.last_seen.strftime(_datetime_format), len(self.history))
        

class XtRecentTable(object):
    def __init__(self, fpath=None):
        if fpath:
            self.fpath = fpath
        else:
            self.fpath = _fpath
        
        self.xt_recent = []
        self.rows      = []
        
    def parse(self, debug=False):
        """
        do parse of xt_recent file
        for every row it create a XtRecentRow object
        """
        # flush it first
        self.rows = []
        self.xt_recent = []
        with open(self.fpath) as f:
            self.rows = f.readlines()
        for i in self.rows:
            if i.strip():
                if debug:
                    print('Parsing: %s' % i.replace('\n', ''))
                row = XtRecentRow(i, debug=_debug)
                row_dt = row.convert_jiffies()
                # raw datetime in jiffies format!
                # self.xt_recent.append( row )            
                # datetime format
                self.xt_recent.append( row_dt )                
                if debug:
                    print(row_dt)                    
                    for e in row_dt.history:
                        print(r)
    
    def csv(self):
        self.parse()
        print(';'.join(('ip_src','last_seen','connections','deltas_mean', 'delta_seconds')))
        for row in self.xt_recent:
            deltas = []
            dt_cnt = 1
            if len(row.history) > 1:
                for hi in row.history:
                    try:
                        #~ print(row.history[dt_cnt], hi, )
                        dt = row.history[dt_cnt] - hi
                        #~ print(dt)
                        deltas.append(dt)
                    except Exception as e:
                        pass
                    dt_cnt += 1
            
            if len(deltas):
                d_mean = sum([ d.seconds for d in deltas]) / len(deltas)
            else:
                d_mean = 0
            
            prow = (row.src, 
                    str(row.last_seen), 
                    str(len(row.history)), 
                    str(d_mean),
                    ','.join([ str(d.seconds) for d in deltas]))
            print( ';'.join(prow))

    def view(self):
        """
        prints in stdout the XtRecentRow object's representation
        for all the rows in xt_recent
        """
        self.parse()
        for row in self.xt_recent:
            print(row)


if __name__ == '__main__':
    print('XT_RECENT python parser\n<giuseppe.demarco@unical.it>\n')
    import argparse
    parser = argparse.ArgumentParser()

    # An int is an explicit number of arguments to accept.
    parser.add_argument('-f', required=False,
                        default=_fpath,
                        help="custom xt_recent path, default if omitted is: /proc/net/xt_recent/BLACKLIST")
    parser.add_argument('-txt', action="store_true", help="print it in human readable format")
    parser.add_argument('-csv', action="store_true", help="print it in CSV format")
    args = parser.parse_args()

    if len(sys.argv)==1:
        parser.print_help()
        sys.exit(1)

    if args.f:    
        _fpath = args.f
    
    print('Parsing file: {}'.format(_fpath))
    
    xt = XtRecentTable(fpath=_fpath)

    if args.txt:
        xt.view()

    if args.csv:
        xt.csv()
