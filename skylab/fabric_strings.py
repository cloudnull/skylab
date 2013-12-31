# =============================================================================
# Copyright [2013] [cloudnull]
# License Information :
# This software has no warranty, it is provided 'as is'. It is your
# responsibility to validate the behavior of the routines and its accuracy
# using the code provided. Consult the GNU General Public license for further
# details (see GNU General Public License).
# http://www.gnu.org/licenses/gpl.html
# =============================================================================


# CHECK_DISTRO = """
# if [ -f "/etc/redhat-release"  ];then
#   if [ "$(grep -i -e redhat -e centos /etc/redhat-release)" ];then
#     echo "redhat"
#   else
#     echo "NOT A RHEL VERSION WE SUPPORT..."
#     exit 1
#   fi
# elif [ -f "/etc/lsb-release" ];then
#   if [ "$(grep -i ubuntu /etc/lsb-release)" ];then
#     echo "ubuntu"
#   else
#     echo "NOT A DEBIAN VERSION WE SUPPORT..."
#     exit 1
#   fi
# else
#   echo "This is not a supported OS, So this script will not work."
#   exit 1
# fi
# """

BASE = """
if [ ! -d "/opt/" ];then
    mkdir -p /opt/
fi
if [ ! -d "/etc/chef/" ];then
    mkdir -p /etc/chef
fi
"""

KEY_MAKER = """
if [ ! -f "/root/.ssh/id_rsa" ];then
    ssh-keygen -t rsa -f /root/.ssh/id_rsa -N ''
    pushd /root/.ssh/
    cat id_rsa.pub | tee -a authorized_keys
    popd
fi
"""

SYSCONTROL_SETUP = """
sysctl net.ipv4.conf.default.rp_filter=0 | tee -a /etc/sysctl.conf
sysctl net.ipv4.conf.all.rp_filter=0 | tee -a /etc/sysctl.conf
sysctl net.ipv4.ip_forward=1 | tee -a /etc/sysctl.conf
"""

INSTALL_APT_PACKAGES = """
apt-get update
DEPS="python-dev python-pip git erlang erlang-nox erlang-dev curl lvm2"
apt-get install -y ${DEPS}
RABBIT_URL="http://www.rabbitmq.com"

RABBITMQ_KEY="${RABBIT_URL}/rabbitmq-signing-key-public.asc"
wget -O /tmp/rabbitmq.asc ${RABBITMQ_KEY};
apt-key add /tmp/rabbitmq.asc
RABBITMQPATH="releases/rabbitmq-server/v3.1.5/rabbitmq-server_3.1.5-1_all.deb"
RABBITMQ="${RABBIT_URL}/${RABBITMQPATH}"
wget -O /tmp/rabbitmq.deb ${RABBITMQ}
dpkg -i /tmp/rabbitmq.deb
rabbit_setup

CHEF="https://www.opscode.com/chef/download-server?p=ubuntu&pv=12.04&m=x86_64"
CHEF_SERVER_PACKAGE_URL=${CHEF}
wget -O /tmp/chef_server.deb ${CHEF_SERVER_PACKAGE_URL}
dpkg -i /tmp/chef_server.deb
"""

SWAP_SCRIPT = """
#!/usr/bin/env bash
SWAPPINESS=$(sysctl -a | grep vm.swappiness | awk -F' = ' '{print $2}')

if [ "${SWAPPINESS}" != 60 ];then
  sysctl vm.swappiness=60
fi

if [ ! "$(swapon -s | grep -v Filename)" ];then
  SWAPFILE="/SwapFile"
  if [ -f "${SWAPFILE}" ];then
    swapoff -a
    rm ${SWAPFILE}
  fi
  dd if=/dev/zero of=${SWAPFILE} bs=1M count=1024
  chmod 600 ${SWAPFILE}
  mkswap ${SWAPFILE}
  swapon ${SWAPFILE}
fi
"""

ENABLE_SWAP = """
chmod +x /opt/swap.sh
bash /opt/swap.sh
"""

CHEFSERVER_RECONFIGURE = """
RMQ_PW=%(rabbit_password)s
RMQ_IP=%(rabbit_ip)s

if [ ! "$(rabbitmqctl list_vhosts | grep -w '/chef')" ];then
  rabbitmqctl add_vhost /chef
fi

if [ "$(rabbitmqctl list_users | grep -w 'chef')" ];then
  rabbitmqctl delete_user chef
fi

rabbitmqctl add_user chef "${RMQ_PW}"
rabbitmqctl set_permissions -p /chef chef '.*' '.*' '.*'

mkdir -p /etc/chef-server
cat > /etc/chef-server/chef-server.rb <<EOF
erchef["s3_url_ttl"] = 3600
nginx["ssl_port"] = 4000
nginx["non_ssl_port"] = 4080
nginx["enable_non_ssl"] = true
rabbitmq["enable"] = false
rabbitmq["password"] = "${RMQ_PW}"
rabbitmq["vip"] = "${RMQ_IP}"
rabbitmq['node_ip_address'] = "${RMQ_IP}"
chef_server_webui["web_ui_admin_default_password"] = "THISisAdefaultPASSWORD"
bookshelf["url"] = "https://#{node['ipaddress']}:4000"
EOF

chef-server-ctl reconfigure
"""

CHEF_CLIENT = """
bash <(wget -O - http://opscode.com/chef/install.sh)
"""

KNIFE_CLIENT = """
SYS_IP="%(chef_server_ip)s"
export CHEF_SERVER_URL=https://${SYS_IP}:4000

# Configure Knife
mkdir -p /root/.chef
cat > /root/.chef/knife.rb <<EOF
log_level                :info
log_location             STDOUT
node_name                'admin'
client_key               '/etc/chef-server/admin.pem'
validation_client_name   'chef-validator'
validation_key           '/etc/chef-server/chef-validator.pem'
chef_server_url          "https://${SYS_IP}:4000"
cache_options( :path => '/root/.chef/checksums' )
cookbook_path            [ '/opt/chef-cookbooks/cookbooks' ]
EOF
"""

COOKBOOK_UPLOAD = """
if [ -d "/opt/chef-cookbooks" ];then
    rm -rf /opt/chef-cookbooks
fi

git clone https://github.com/rcbops/chef-cookbooks.git /opt/chef-cookbooks
pushd /opt/chef-cookbooks
git checkout %(cookbook_version)s
git submodule init
git submodule sync
git submodule update


# Get add-on Cookbooks
knife cookbook site download -f /tmp/cron.tar.gz cron 1.2.6
tar xf /tmp/cron.tar.gz -C /opt/chef-cookbooks/cookbooks

knife cookbook site download -f /tmp/chef-client.tar.gz chef-client 3.0.6
tar xf /tmp/chef-client.tar.gz -C /opt/chef-cookbooks/cookbooks

# Upload all of the RCBOPS Cookbooks
knife cookbook upload -o /opt/chef-cookbooks/cookbooks -a
knife role from file /opt/chef-cookbooks/roles/*.rb
popd
"""


ENVIRONMENT = """
{
    "chef_type": "environment",
    "default_attributes": {},
    "name": "%(name)s",
    "override_attributes": {
        "monitoring": {
            "procmon_provider": "monit",
            "metric_provider": "collectd"
        },
        "enable_monit": true,
        "osops_networks": {
            "management": "%(vip_prefix)s.0/24",
            "swift": "%(vip_prefix)s.0/24",
            "public": "%(vip_prefix)s.0/24",
            "nova": "%(vip_prefix)s.0/24"
        },
        "nova": {
            "config": {
                "resume_guests_state_on_host_boot": false,
                "use_single_default_gateway": false,
                "ram_allocation_ratio": 1.0,
                "cpu_allocation_ratio": 2.0,
                "disk_allocation_ratio": 1.0
            },
            "network": {
                "provider": "neutron"
            },
            "scheduler": {
                "default_filters": [
                    "AvailabilityZoneFilter",
                    "ComputeFilter",
                    "RetryFilter"
                ]
            },
            "libvirt": {
                "vncserver_listen": "0.0.0.0",
                "virt_type": "qemu"
            }
        },
        "keystone": {
            "pki": {
                "enabled": false
            },
            "tenants": [
                "service",
                "admin",
                "demo",
                "demo2"
            ],
            "users": {
                "admin": {
                    "password": "secrete",
                    "roles": {
                        "admin": [
                            "admin"
                        ]
                    }
                },
                "demo": {
                    "password": "secrete",
                    "default_tenant": "demo",
                    "roles": {
                        "Member": [
                            "demo2",
                            "demo"
                        ]
                    }
                },
                "demo2": {
                    "password": "secrete",
                    "default_tenant": "demo2",
                    "roles": {
                        "Member": [
                            "demo2",
                            "demo"
                        ]
                    }
                }
            },
            "admin_user": "admin"
        },
        "rabbitmq": {
            "cluster": true,
            "erlang_cookie": "%(erlang_cookie)s"
        },
        "mysql": {
            "root_network_acl": "127.0.0.1",
            "allow_remote_root": true,
            "tunable": {
                "log_queries_not_using_index": false
            }
        },
        "developer_mode": false,
        "vips": {
            "horizon-dash": "%(vip_prefix)s.156",
            "heat-api-cloudwatch": "%(vip_prefix)s.156",
            "keystone-service-api": "%(vip_prefix)s.156",
            "keystone-admin-api": "%(vip_prefix)s.156",
            "nova-xvpvnc-proxy": "%(vip_prefix)s.156",
            "nova-api": "%(vip_prefix)s.156",
            "cinder-api": "%(vip_prefix)s.156",
            "nova-ec2-public": "%(vip_prefix)s.156",
            "rabbitmq-queue": "%(vip_prefix)s.155",
            "ceilometer-api": "%(vip_prefix)s.156",
            "nova-novnc-proxy": "%(vip_prefix)s.156",
            "heat-api-cfn": "%(vip_prefix)s.156",
            "mysql-db": "%(vip_prefix)s.154",
            "glance-api": "%(vip_prefix)s.156",
            "keystone-internal-api": "%(vip_prefix)s.156",
            "horizon-dash_ssl": "%(vip_prefix)s.156",
            "neutron-api": "%(vip_prefix)s.156",
            "glance-registry": "%(vip_prefix)s.156",
            "config": {
                "%(vip_prefix)s.155": {
                    "vrid": 11,
                    "network": "public"
                },
                "%(vip_prefix)s.154": {
                    "vrid": 10,
                    "network": "public"
                },
                "%(vip_prefix)s.156": {
                    "vrid": 12,
                    "network": "public"
                }
            },
            "heat-api": "%(vip_prefix)s.156",
            "ceilometer-central-agent": "%(vip_prefix)s.156"
        },
        "glance": {
            "images": [],
            "image": {},
            "image_upload": false
        },
        "osops": {
            "do_package_upgrades": false,
            "apply_patches": false
        },
        "neutron": {
            "ovs": {
                "network_type": "gre",
                "provider_networks": [
                    {
                        "bridge": "br-eth1",
                        "vlans": "1024:1024",
                        "label": "ph-eth1"
                    }
                ]
            }
        }
    },
    "cookbook_versions": {},
    "json_class": "Chef::Environment",
    "description": "Openstack Private Cloud on the Rackspace Public Cloud"
}
"""

ENVIRONMENT_UPLOAD = """
knife environment from file /opt/base.env.json
"""

CHEF_CLIENT_RB = """
log_level        :auto
log_location     STDOUT
chef_server_url  "https://%(chef_server_ip)s:4000"
validation_client_name "chef-validator"
"""

RUN_CHEF_CLIENT = """
chef-client -j %(first_bt_json)s \
            -c %(client_loc)s \
            -E %(chef_env)s \
            -L /var/log/chef-client.log
"""
