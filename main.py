#!/usr/bin/env python3.5
__author__ = 'jnejati'

#import experiments
import json
import webDnsSetup
import network_emulator
import os
from urllib.parse import urlparse
import time
import urllib.request
import urllib.response
import io
import gzip
import subprocess
import logging
import timeit
import csv 
import sys

def _change_resolv_conf(ip):
    RESOLV_CONF = '/etc/resolv.conf'
    with open (RESOLV_CONF, 'w') as _f:
        _f.write('nameserver         '+str(ip)+'\n')


def main(input_file, runs, launchChrome = False):
    start = timeit.default_timer()
    _domains_dir = 'domains_list/'
    archive_file = '/home/savargas/DevRegions/data/02_26_18_Africa_sites/testbed/recordings/recording1/archive.wprgo'
    # archive_file = "/home/savargas/DevRegions/data/02_03_18_US_sites/testbed/recordings/recording1/archive.wprgo"
    config_file = 'confs/netProfiles.2g.json'
    _change_resolv_conf('127.0.0.1')
    with open(config_file, 'r') as f:
        default_net_profile = json.load(f)[0]
        _path =  os.path.join(default_net_profile['device_type'] + '_' + default_net_profile['name'])
        webDnsSetup.clear_folder(_path)
    with open(input_file) as _sites:
        # _sites = [x for x in _sites]
        for _site in _sites:
            _site = _site.strip()
            print('Navigating to: ' + _site)
            s1 = urlparse(_site)
            print(s1)
            _site_data_folder = os.path.join(_path, s1.netloc)
            if not os.path.isdir(_site_data_folder):
                os.mkdir(_site_data_folder)
                os.mkdir(os.path.join(_site_data_folder, 'dns'))
            with open(os.path.join(_domains_dir, s1.netloc + '.txt'), newline='') as f:
                _domains = csv.reader(f, delimiter=',')
                _domains = [x for x in _domains][0]
            _domains = [x.rstrip('.') for x in _domains if x[:-1]]    
            _domains.sort()
            ### ping Delays
            netp = webDnsSetup.ping_delays(_domains, default_net_profile)
            netns = network_emulator.NetworkEmulator('desktop', _domains, netp, default_net_profile)
            print('Setting up namespaces ...')
            netns.setup_namespace()
            print('Setting up link profiles ...')
            netns.set_profile()
            ### DNS delays
            time.sleep(5)
            dnsHandler = webDnsSetup.setup_dns(_domains)
            webDnsSetup.setup_replay(_domains, archive_file)
            time.sleep(30)
            for run_no in range(runs):
                _run_data_folder = os.path.join(_site_data_folder, 'run_' + str(run_no))
                if not os.path.isdir(_run_data_folder):
                    os.mkdir(_run_data_folder)
                    _subfolders = ['trace', 'screenshot', 'analysis', 'summary']
                    for folder in _subfolders:
                        os.mkdir(os.path.join(_run_data_folder, folder))
                print('Current profile: ' + default_net_profile['device_type'] + ' - ' + default_net_profile['name'] + ' run_no: ' + str(run_no) + ' site: ' + _site)
                time.sleep(15)

                _trace_folder = os.path.join(_run_data_folder, 'trace')
                _screenshot_folder = os.path.join(_run_data_folder, 'screenshot')
                _summary_folder = os.path.join(_run_data_folder, 'summary')
                _trace_file = os.path.join(_trace_folder, str(run_no) + '_' + s1.netloc)
                _screenshot_file = os.path.join(_screenshot_folder, str(run_no) + '_' + s1.netloc)
                _summary_file = os.path.join(_summary_folder, str(run_no) + '_' + s1.netloc)
                _launch_chrome = str(launchChrome)
                logging.info(_trace_file, _screenshot_file, _summary_file)
                time.sleep(5)
                try:
                    node = 'node'
                    _node_cmd = [node, 'chrome_launcher.js', _site,  _trace_file, _summary_file, _screenshot_file, _launch_chrome]
                    _cmd =  _node_cmd
                    # print("Node Command", _cmd)
                    subprocess.call(_cmd, timeout = 110)
                except subprocess.TimeoutExpired:
                    print("Timeout:  ", _site, run_no)
                    with open (os.path.join(_site_data_folder, 'log.txt'), 'w+') as _log:
                        _log.write("Timed out:  " +  _site + ' ' +  str(run_no) + '\n')
                finally:
                    os.system('pkill node')
            os.system('pkill wpr')
            dnsHandler.terminate()
            time.sleep(5)
    webDnsSetup.clear_ip_tables()
    stop = timeit.default_timer()
    logging.info(100*'-' + '\nTotal time: ' + str(stop -start))
    _change_resolv_conf('8.8.8.8')

if __name__ == '__main__':
    # Get command line arguments
    domains_file = sys.argv[1]
    runs = int(sys.argv[2])
    mobile_flag = sys.argv[3].lower() == "true"
    main(domains_file, runs, mobile_flag)
