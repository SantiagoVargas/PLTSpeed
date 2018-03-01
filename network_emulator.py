import subprocess
#import netifaces
import os

__author__ = 'jnejati'


class NetworkEmulator():

    def __init__(self, device_type, domain_list, domain_dict, default_net_profile):
        self.default = default_net_profile
        self._netns = domain_list
        self.device_type = device_type
        self.domain_dict = domain_dict
        for _d in domain_list:
            if _d not in self.domain_dict:
                self.domain_dict[_d] = {}
                for k, v in self.default.items():
                    # Todo: See which domains get default values
                    self.domain_dict[_d][k] = v

    def setup_namespace(self):
        subprocess.call(['ip', '-all', 'netns', 'delete'])
        for i in range(len(self._netns) + 1):
            subprocess.call(['ip', 'netns', 'add', 'netns-' + str(i)])
            subprocess.call(['ip', 'netns', 'exec', 'netns-' + str(i), 'ip', 'link', 'set', 'dev', 'lo', 'up'])

        for i in range(300):
            # TODO get the list of veth programattically
            veth_a = 'veth-' + str(i * 2)
            veth_b = 'veth-' + str((i * 2) + 1)
            subprocess.call(['ip', 'link', 'delete', veth_a])
            subprocess.call(['ip', 'link', 'delete', veth_b])
        for i, value in enumerate(self._netns):
            #netns_a = 'netns-0'
            netns_b = 'netns-' + str(i + 1)
            veth_a = 'veth-' + str(i * 2)
            veth_b = 'veth-' + str((i * 2) + 1)
            subprocess.call(['ip', 'link', 'add', veth_a, 'type', 'veth', 'peer', 'name', veth_b])
            #subprocess.call(['ip', 'link', 'set', veth_a, 'netns', netns_a])
            subprocess.call(['ip', 'link', 'set', veth_b, 'netns', netns_b])
            #subprocess.call(['ip', 'netns', 'exec', netns_a, 'ip', 'addr', 'add', '10.10.' + str(i + 1) + '.1/24', 'dev', veth_a])
            subprocess.call(['ip', 'addr', 'add', '10.10.' + str(i + 1) + '.1/24', 'dev', veth_a])
            subprocess.call(['ip', 'netns', 'exec', netns_b, 'ip', 'addr', 'add', '10.10.' + str(i + 1) + '.2/24', 'dev', veth_b])
            #subprocess.call(['ip', 'netns', 'exec', netns_a, 'ip', 'link', 'set', 'dev', veth_a, 'up'])
            subprocess.call(['ip', 'link', 'set', 'dev', veth_a, 'up'])
            subprocess.call(['ip', 'netns', 'exec', netns_b, 'ip', 'link', 'set', 'dev', veth_b, 'up'])
            # Build the hosts file

    def set_profile(self):
        if self.device_type == 'desktop':
            subprocess.call(['tc', 'qdisc', 'del', 'dev', 'enp1s0f0', 'root'])
            subprocess.call(['tc', 'qdisc', 'del', 'dev', 'lo', 'root'])
            #subprocess.call(['tc', 'qdisc', 'del', 'dev', 'usb0', 'root'])
            print('Removing all current disciplines')
            for i in range(len(self._netns)):
                netns_a = 'netns-0'
                netns_b = 'netns-' + str(i + 1)
                veth_a = 'veth-' + str(i * 2)
                veth_b = 'veth-' + str((i * 2) + 1)
                #subprocess.call(['ip', 'netns', 'exec', netns_a, 'tc', 'qdisc', 'del', 'dev', veth_a, 'root'])
                subprocess.call(['tc', 'qdisc', 'del', 'dev', veth_a, 'root'])
                subprocess.call(['ip', 'netns', 'exec', netns_b, 'tc', 'qdisc', 'del', 'dev', veth_b, 'root'])
            print('Setting queuing disciplines')
            for i, _domain in enumerate(self._netns):
                print('Adding netns')
                #netns_a = 'netns-0'
                netns_b = 'netns-' + str(i + 1)
                veth_a = 'veth-' + str(i * 2)
                veth_b = 'veth-' + str((i * 2) + 1)
                subprocess.call(['tc', 'qdisc', 'add', 'dev', veth_a, 'handle', '1:0', 'root', 'htb', 'default', '11'])
                subprocess.call(['tc', 'class', 'add', 'dev', veth_a, 'parent', '1:', 'classid', '1:1', 'htb', 'rate', '1000Mbps'])
                subprocess.call(['tc', 'class', 'add', 'dev', veth_a, 'parent', '1:1', 'classid', '1:11', 'htb', 'rate', self.domain_dict[_domain]['download_rate'], 'burst', '15K'])
                subprocess.call(['tc', 'qdisc', 'add', 'dev', veth_a, 'parent', '1:11', 'handle', '10', 'netem', 'delay', self.domain_dict[_domain]['download_delay'], 'loss', self.domain_dict[_domain]['download_loss']])

                subprocess.call(['ip', 'netns', 'exec', netns_b, 'tc', 'qdisc', 'add', 'dev', veth_b, 'handle', '1:', 'root', 'htb', 'default', '11'])
                subprocess.call(['ip', 'netns', 'exec', netns_b, 'tc', 'class', 'add', 'dev', veth_b, 'parent', '1:', 'classid', '1:1', 'htb', 'rate', '1000Mbps'])
                subprocess.call(['ip', 'netns', 'exec', netns_b, 'tc', 'class', 'add', 'dev', veth_b, 'parent', '1:1', 'classid', '1:11', 'htb', 'rate', self.domain_dict[_domain]['upload_rate'], 'burst', '15K'])
                subprocess.call(['ip', 'netns', 'exec', netns_b, 'tc', 'qdisc', 'add', 'dev', veth_b, 'parent', '1:11', 'handle', '10', 'netem', 'delay', self.domain_dict[_domain]['upload_delay'], 'loss', self.domain_dict[_domain]['upload_loss']])
                
                
        elif self.device_type == 'mobile':
                commands = [
                'tc' + ' ' + 'qdisc' + ' ' + 'del' + ' ' + 'dev' + ' ' + 'veth0' + ' ' + 'root'
                , 'tc' + ' ' + 'qdisc' + ' ' + 'del' + ' ' + 'dev' + ' ' + 'usb0' + ' ' + 'root'
                , 'tc' + ' ' + 'qdisc' + ' ' + 'del' + ' ' + 'dev' + ' ' + 'ifb0' + ' ' + 'root'
                , 'tc' + ' ' + 'qdisc' + ' ' + 'del' + ' ' + 'dev' + ' ' + 'enp1s0f0' + ' ' + 'ingress'
                , 'modprobe' + ' ' + 'ifb'
                , 'ip' + ' ' + 'link' + ' ' + 'set' + ' ' + 'dev' + ' ' + 'ifb0' + ' ' + 'up'
                , 'tc' + ' ' + 'qdisc' + ' ' + 'add' + ' ' + 'dev' + ' ' + 'usb0' + ' ' + 'ingress'
                , 'tc' + ' ' + 'filter' + ' ' + 'add' + ' ' + 'dev' + ' ' + 'usb0' + ' ' + 'parent' + ' ' + 'ffff:' + ' ' + 'protocol' + ' ' + 'ip' + ' ' + 'u32' + ' ' + 'match' + ' ' + 'u32' + ' ' + '0' + ' ' + '0' + ' ' + 'flowid' + ' ' + '1:1' + ' ' + 'action' + ' ' + 'mirred' + ' ' + 'egress' + ' ' + 'redirect' + ' ' + 'dev' + ' ' + 'ifb0'


                , 'tc'+ ' ' + 'qdisc' + ' ' + 'add' + ' ' + 'dev' + ' ' + 'ifb0' + ' '  + 'handle' + ' ' + '1:' + ' ' + 'root' + ' ' + 'htb' + ' ' + 'default' + ' ' + '11'
                , 'tc' + ' ' + 'class' + ' ' + 'add' + ' ' + 'dev' + ' ' + 'ifb0' + ' ' + 'parent' + ' ' + '1:' + ' ' + 'classid' + ' ' + '1:1' + ' ' + 'htb' + ' ' + 'rate' + ' ' + '1000Mbps'
                , 'tc' + ' ' + 'class' + ' ' + 'add' + ' ' + 'dev' + ' ' + 'ifb0' + ' ' + 'parent' + ' ' + '1:1' + ' ' + 'classid' + ' ' + '1:11' + ' ' + 'htb' + ' ' + 'rate' + ' ' +  self.domain_dict[_domain]['download_rate']
                , 'tc' + ' ' + 'qdisc' + ' ' + 'add' + ' ' + 'dev' + ' ' + 'ifb0' + ' ' + 'parent' + ' ' + '1:11' + ' ' + 'handle' + ' ' + '10:' + ' ' + 'netem' + ' ' + 'delay' + ' ' + self.domain_dict[_domain]['download_delay'] + ' ' + 'loss' + ' ' + self.domain_dict[_domain]['download_loss']
                , 'tc' + ' ' + 'qdisc' + ' ' + 'add' + ' ' + 'dev' + ' ' + 'usb0' + ' ' + 'handle' + ' ' + '1:' + ' ' + 'root' + ' ' + 'htb' + ' ' + 'default' + ' ' + '11'
                , 'tc' + ' ' + 'class' + ' ' + 'add' + ' ' + 'dev' + ' ' + 'usb0' + ' ' + 'parent' + ' ' + '1:' + ' ' + 'classid' + ' ' + '1:1' + ' ' + 'htb' + ' ' + 'rate' +' ' +  '1000Mbps'
                , 'tc' + ' ' + 'class' + ' ' + 'add' + ' ' + 'dev' + ' ' + 'usb0' + ' ' + 'parent' + ' ' + '1:1' + ' ' + 'classid' + ' ' + '1:11' + ' ' + 'htb' + ' ' + 'rate' +' ' +  self.domain_dict[_domain]['upload_rate']
                , 'tc' + ' ' + 'qdisc' + ' ' + 'add' + ' ' + 'dev' + ' ' + 'usb0' + ' ' + 'parent' + ' ' + '1:11' + ' ' + 'handle' + ' ' + '10:' + ' ' + 'netem' + ' ' + 'delay' + ' ' + self.domain_dict[_domain]['upload_delay'] + ' ' + 'loss' + ' ' + self.domain_dict[_domain]['upload_loss']
]


def main():
    net_profile =  {'download_rate':'10Mbit',
                  'download_delay':'50ms',
                  'download_loss':'0.0%',
                  'upload_rate':'10Mbit',
                  'upload_delay':'50ms',
                  'upload_loss':'0.0%'}
    path = '/home/jnejati/PLTSpeed/record/archive/www.bbc.com/'
    dirs = os.listdir(path)
    dirs.sort()
    netp = {}
    for _d in dirs:
        netp[_d] = net_profile 
    my_ne = NetworkEmulator('desktop', dirs, netp)
    my_ne.setup_namespace()
    my_ne.set_profile()


if __name__ == '__main__':
    main()            
