import errno
import json
import pickle
import random
import sys
import subprocess
import os
import shutil
from urllib.parse import urlparse
import time
from OpenSSL import crypto, SSL
from socket import gethostname
from pprint import pprint
from time import gmtime, mktime
import tldextract
import dnsserver
from ripe.atlas.sagan import PingResult
from ripe.atlas.cousteau import Measurement, Probe
import ccTld
import genCert

class cd:
    """Context manager for changing the current working directory"""
    def __init__(self, newPath):
        self.newPath = os.path.expanduser(newPath)

    def __enter__(self):
        self.savedPath = os.getcwd()
        os.chdir(self.newPath)

    def __exit__(self, etype, value, traceback):
        os.chdir(self.savedPath)


def create_self_signed_cert(cert_dir, domain_name):
    genCert.gencert(domain_name)

def create_self_signed_cert_old(_cert_dir, _key_dir, domain_name):
    clear_folder(_cert_dir)
    clear_folder(_key_dir)
    SYSTEM_CERT_DIR = '/usr/local/share/ca-certificates'
    DOMAIN_SYS_DIR = os.path.join(SYSTEM_CERT_DIR, domain_name)
    CERT_FILE = domain_name + '.crt'
    KEY_FILE = domain_name + '.key'
    k = crypto.PKey()
    k.generate_key(crypto.TYPE_RSA, 1024)
    # create a self-signed cert
    cert = crypto.X509()
    cert.get_subject().C = "US"
    cert.get_subject().ST = "New York"
    cert.get_subject().L = "Stony Brook"
    cert.get_subject().O = "Computer Science"
    cert.get_subject().OU = "NetSys"
    cert.get_subject().CN = domain_name
    cert.set_serial_number(int(random.randint(0, 1000000000)))
    cert.gmtime_adj_notBefore(0)
    cert.gmtime_adj_notAfter(10*365*24*60*60)
    cert.set_issuer(cert.get_subject())
    cert.set_pubkey(k)
    cert.sign(k, 'sha1')
    #print(cert_dir, CERT_FILE, crypto.dump_certificate(crypto.FILETYPE_PEM, cert))
    open(os.path.join(_cert_dir, CERT_FILE), "wb").write(
        crypto.dump_certificate(crypto.FILETYPE_PEM, cert))
    open(os.path.join(_key_dir, KEY_FILE), "wb").write(
        crypto.dump_privatekey(crypto.FILETYPE_PEM, k))
    clear_folder(DOMAIN_SYS_DIR)
    system_cert_domain = os.path.join(DOMAIN_SYS_DIR, CERT_FILE)
    shutil.copy2(os.path.join(_cert_dir, CERT_FILE), system_cert_domain)
    #print(' '.join(['certutil', '-d', 'sql:/home/jnejati/.pki/nssdb','-A','-t', '"C,,"', '-n', domain_name, '-i', system_cert_domain]))
    #subprocess.call(['certutil', '-d', 'sql:/home/jnejati/.pki/nssdb','-D','-t', '"C,,"', '-n', domain_name, '-i', system_cert_domain])
    #subprocess.call(['certutil', '-d', 'sql:/home/jnejati/.pki/nssdb','-A','-t', '"C,,"', '-n', domain_name, '-i', system_cert_domain])
    os.system('certutil -d sql:/home/jnejati/.pki/nssdb -f password.txt -D -t "C,," -n ' + domain_name +  ' -i ' + system_cert_domain)
    os.system('certutil -d sql:/home/jnejati/.pki/nssdb -f password.txt -A -t "C,," -n ' + domain_name +  ' -i ' + system_cert_domain)

def clear_folder(folder):
    if os.path.isdir(folder):
            for root, dirs, l_files in os.walk(folder):
                for f in l_files:
                    os.unlink(os.path.join(root, f))
                for d in dirs:
                    shutil.rmtree(os.path.join(root, d))
    else:
        os.makedirs(folder)

def clear_ip_tables():
    subprocess.call(['iptables', '-t', 'nat', '-D', 'OUTPUT', '-p', 'tcp', '--dport', '80' , '-j', 'DNAT', '--to-destination', '127.0.0.1:8080'])
    subprocess.call(['iptables', '-t', 'nat', '-D', 'OUTPUT', '-p', 'tcp', '--dport', '443' , '-j', 'DNAT', '--to-destination', '127.0.0.1:8081'])

def copytree(src, dst, symlinks=False, ignore=None):
    for item in os.listdir(src):
        s = os.path.join(src, item)
        d = os.path.join(dst, item)
        if os.path.isdir(s):
            shutil.copytree(s, d, symlinks, ignore)
        else:
            shutil.copy2(s, d)

def copyanything(src, dst):
    try:
        copytree(src, dst)
    except OSError as exc: # python >2.5
        if exc.errno == errno.ENOTDIR:
            shutil.copy(src, dst)
        else: raise

def setup_replay(domain_list, _archive):
    os.system('pkill go')
    #subprocess.call(['iptables', '-t', 'nat', '-A', 'OUTPUT', '-p', 'tcp', '--dport', '80' , '-j', 'DNAT', '--to-destination', '127.0.0.1:8080'])
    #subprocess.call(['iptables', '-t', 'nat', '-A', 'OUTPUT', '-p', 'tcp', '--dport', '443' , '-j', 'DNAT', '--to-destination', '127.0.0.1:8081'])
    replay_processes = []
    for i, domain in enumerate(domain_list):
        netns_b = 'netns-' + str(i + 1)
        #veth_b = 'veth-' + str((i * 2) + 1)
        #subprocess.call(['sysctl', '-w', 'net.ipv4.conf.' + veth_b + '.route_localnet=1'])
        print('Starting Web replay inside: {}: {}'.format(netns_b, domain))
        _go = '/usr/local/go/bin/go'
        _src = '/home/savargas/go/src/github.com/catapult-project/catapult/web_page_replay_go/src/'
        _cert ='--https_cert_file=/home/savargas/go/src/github.com/catapult-project/catapult/web_page_replay_go/wpr_cert.pem'
        _key='--https_key_file=/home/savargas/go/src/github.com/catapult-project/catapult/web_page_replay_go/wpr_key.pem'
        #_archive = '/home/savargas/archive.json'
        _host = '--host=10.10.' + str(i + 1) + '.2'#TODO remove iptables by changing port t default 80 and 443
        _host_ip = '10.10.' + str(i + 1) + '.2'#TODO remove iptables by changing port t default 80 and 443
        _http_port = '--http_port=80'
        _https_port = '--https_port=443'
        _inject = '--inject_scripts=/home/savargas/go/src/github.com/catapult-project/catapult/web_page_replay_go/deterministic.js'
        #subprocess.call(['ip', 'netns', 'exec', netns_b,'sysctl',  'net.ipv4.ip_forward=1'])
        #subprocess.call(['ip', 'netns', 'exec', netns_b,'sysctl',  'net.ipv4.ip_forward=1'])
        #subprocess.call(['ip', 'netns', 'exec', netns_b, 'iptables', '-t', 'nat', '-A', 'PREROUTING', '-p', 'tcp', '--dport', '80' , '-j', 'DNAT', '--to-destination', '127.0.0.1:80'])
        #subprocess.call(['ip', 'netns', 'exec', netns_b, 'iptables', '-t', 'nat', '-A', 'PREROUTING', '-p', 'tcp', '--dport', '443' , '-j', 'DNAT', '--to-destination', '127.0.0.1:443'])
        #subprocess.call(['ip', 'netns', 'exec', netns_b, 'iptables', '-t', 'nat', '-A', 'POSTROUTING', '-j', 'MASQUERADE'])
        #subprocess.call(['iptables', '-t', 'nat', '-A', 'POSTROUTING', '-p', 'tcp', '--dport', '80' , '-j', 'SNAT', '--to-source', _host_ip])
        #subprocess.call(['iptables', '-t', 'nat', '-A', 'POSTROUTING', '-p', 'tcp', '-d', '--dport', '443' , '-j', 'SNAT', '--to-source', _host_ip])
        
        # Create the unique archive for this domain
        # This is an optimization for RAM
        newArchive = 'archives/' + domain + '_archive.wprgo'
        # result = subprocess.run([_go, 'run', 'filterarchive.go', _archive, newArchive, domain])
        # if result.returncode:
        #     print('We have problems!!!')

        # Run the replay server
        replay_process = subprocess.Popen(['ip', 'netns', 'exec', netns_b, _go, 'run', _src + 'wpr.go', 'replay',_host,  _http_port, _https_port, _cert, _key, _inject, newArchive], shell=False)
        replay_processes.append(replay_process)
    print('Done.')
    return replay_processes
 
def setup_webserver(domain_list, _src):
    os.system('pkill nginx')
    _dest = '/var/www/'
    clear_folder(_dest)
    copyanything(_src, _dest)
    for i, domain in enumerate(domain_list):
        netns_b = 'netns-' + str(i + 1)
        print(domain, netns_b)
        servername = domain
        try:
            #create_self_signed_cert('/home/jnejati/PLTSpeed/certs', '/home/jnejati/PLTSpeed/keys', domain)
            create_self_signed_cert('certs', domain)
            print('Seting Web server for ', domain)
            out = """user  nginx;
            worker_processes  1;
            error_log  /var/log/nginx/error-%s.log warn;
            pid        /var/run/nginx-%s.pid;

            events {
                worker_connections  1024;
            }

            http {
                include       /etc/nginx/mime.types;
                default_type  application/octet-stream;
                log_format  main  '$remote_addr - $remote_user [$time_local] "$request" '
                                  '$status $body_bytes_sent "$http_referer" '
                                  '"$http_user_agent" "$http_x_forwarded_for"';
                sendfile        on;
                keepalive_timeout  65;
              server {
                listen              80;
                listen              443 ssl;
                server_name         %s;
                ssl_certificate     domains/%s.cert;
                ssl_certificate_key domains/%s.key;
                access_log  /var/log/nginx/%s.access.log  main;
                location / {
                    root   /var/www/%s;
                    index  index.html index.htm;
                 }
               }
            }""" % (servername, servername, servername, servername, servername, servername, servername)
        except:
            print('SSL cert generation failed', domain)
            exit()
            print('Seting Web server for ', domain)
            out = """user  nginx;
                        worker_processes  1;
                        error_log  /var/log/nginx/error-%s.log warn;
                        pid        /var/run/nginx-%s.pid;

                        events {
                            worker_connections  1024;
                        }

                        http {
                            include       /etc/nginx/mime.types;
                            default_type  application/octet-stream;
                            log_format  main  '$remote_addr - $remote_user [$time_local] "$request" '
                                              '$status $body_bytes_sent "$http_referer" '
                                              '"$http_user_agent" "$http_x_forwarded_for"';
                            sendfile        on;
                            keepalive_timeout  65;
                          server {
                            listen              80;
                            server_name         %s;
                            access_log  /var/log/nginx/%s.access.log  main;
                            location / {
                                root   /var/www/%s;
                                index  index.html index.htm;
                             }
                           }
                        }""" % (servername, servername, servername, servername, servername)

        target = open('./conf/%s.conf' % servername, 'w')
        target.write(out)
        target.close()
        print('Start Web server inside: {}: {}'.format(netns_b, domain))
        subprocess.call(['ip', 'netns', 'exec', netns_b, '/usr/sbin/nginx', '-c', 'conf/%s.conf' % servername])
        print('Done.')

def ping_delays(domains, net_profile):
    f = open("ripe/ping_data", "rb")
    netp = {}
    try:
        unpickler = pickle.Unpickler(f)
        ping_dict = unpickler.load()
    except EOFError:
        pass    
    # Todo: Remove this from being hardcoded
    _probeId = 13805 #AO

    for _d in domains:
        _ext = tldextract.extract(_d)
        _subdomain = _ext.subdomain
        _domain = _ext.domain
        _suffix = _ext.suffix
        if _domain in ping_dict:
            for _sd_dict in ping_dict[_domain]:
                _sd = list(_sd_dict.keys())[0]
                netp[_sd] = {}
                for k, v in net_profile.items():
                    netp[_sd][k] = v
                res = _sd_dict[_sd][_probeId]
                if res.rtt_median:
                    netp[_sd]['download_delay'] = str(int(res.rtt_median/2)) + 'ms'
                    netp[_sd]['upload_delay'] = str(int(res.rtt_median/2)) + 'ms'
                    print('Set ping info')
                else:
                    print('Using default ping info')
        else:
            pass
    f.close()
    return netp

def populate_zone_file(_d_ip_dict):
    _dest = 'zones/zones.txt'
    zone_f = open(_dest, 'w')
    for _domain, sd_ip in _d_ip_dict.items():
       zone_f.write(_domain + '\t' + 'SOA\t' + 'ns1.' + _domain + '\n')
       zone_f.write(_domain + '\tNS\t' + 'ns1.' + _domain + '.\n') 
       for _subdomain_ip in sd_ip:
           for _subdomain, _ip in _subdomain_ip.items():
               #print(_subdomain, _domain, _ip)
               if _subdomain == '*':
                    zone_f.write(_domain + '\tA\t' + '\t' + _ip + '\n')
               zone_f.write(_subdomain + '.' + _domain + '\tA\t' + '\t' + _ip + '\n')
    zone_f.close()

def extract_domains(domains):
    _d_ip_dict = {}
    for i, _d in enumerate(domains):
        if not _d == 'trace' and not _d =='screenshot':
            _ext = tldextract.extract(_d)
            _subdomain = _ext.subdomain
            _domain = _ext.domain
            _suffix = _ext.suffix
            _ip = '10.10.' + str(i + 1) + '.2'
            if not _subdomain == '':
                _d_ip_dict.setdefault(_domain + '.' +  _suffix, []).append({_subdomain:_ip})
            else:
                _d_ip_dict.setdefault(_domain + '.' +  _suffix, []).append({'*':_ip})
    return _d_ip_dict 
 
def setup_dns(domains):
    domains_dump_file = 'zones/domains.pickle'
    _d_ip_dict = extract_domains(domains)
    populate_zone_file(_d_ip_dict) 
    print(domains, type(domains))
    with open(domains_dump_file, 'wb') as df:
        pickle.dump(domains, df, pickle.HIGHEST_PROTOCOL)
    #Start the DNS server
    dnsHandler = subprocess.Popen(['./dnsserver.py'], shell=False)
    return dnsHandler

def setup_dns_recorder():
    #Start the DNS recorder
    dnsHandler = subprocess.Popen(['./dns_recorder.py'], shell=False)
    return dnsHandler
