# =============================================================================
# Copyright [2013] [cloudnull]
# License Information :
# This software has no warranty, it is provided 'as is'. It is your
# responsibility to validate the behavior of the routines and its accuracy
# using the code provided. Consult the GNU General Public license for further
# details (see GNU General Public License).
# http://www.gnu.org/licenses/gpl.html
# =============================================================================


try:
    import argparse
except ImportError:
    raise SystemExit('Python module "argparse" not Found for import.')
import os

from skylab import info


def args():
    """Parse the Command Line Arguments."""

    par = argparse.ArgumentParser(
        usage='%(prog)s',
        description=info.__description__,
        epilog='GPLv3 Licensed.'
    )
    par.add_argument('--debug',
                     help='Enable Debug Mode',
                     action='store_true',
                     default=False)

    dba = par.add_argument_group('Local Database Options')
    dba.add_argument('--db-path',
                     metavar='',
                     help='Data base Path, Default: %(default)s',
                     default=os.environ.get('HOME'))
    dba.add_argument('--db-name',
                     metavar='',
                     help='Data Name',
                     default='skylab')

    key = par.add_argument_group('SSH Options')
    key.add_argument('--key-name',
                     metavar='',
                     help=('Name of key to be injected into your Servers. If'
                           ' the key name is not found and the key-location'
                           ' is, a key will be created for you in NOVA and'
                           ' injected.'),
                     default='skylab')
    key.add_argument('--key-location',
                     metavar='',
                     help=('Location of the public key to be saved into'
                           ' nova for key injection into your servers.'
                           ' If your key-name does not exists and this'
                           ' variables file path is found the key will be'
                           ' created for you, DEFAULT: "%(default)s"'),
                     default='~/.ssh/id_rsa.pub')

    aut = par.add_argument_group('Openstack Auth Options')
    key_types = aut.add_mutually_exclusive_group(required=True)
    key_types.add_argument('-P',
                           '--password',
                           metavar='',
                           help='Your Cloud account Password',
                           default=None)
    key_types.add_argument('-A',
                           '--apikey',
                           metavar='',
                           help='Your Cloud account API Key',
                           default=None)

    aut.add_argument('-U',
                     '--username',
                     metavar='',
                     help='Your Username',
                     required=True,
                     default=None)
    aut.add_argument('-R',
                     '--region',
                     metavar='',
                     help='Your Region, use commas to separate regions',
                     required=True,
                     default=None)
    aut.add_argument('--tenant-name',
                     metavar='',
                     help='Your Tenant Name, (Optional)',
                     required=False,
                     default=None)
    aut.add_argument('--project-id',
                     metavar='',
                     help='Project ID, DEFAULT: "%(default)s"',
                     default=None)
    # Add a subparser
    subpar = par.add_subparsers()
    lin = subpar.add_parser('lab-info',
                            help='Show Lab Data')
    lin.set_defaults(method='lab_info')
    lin.add_argument('-n',
                     '--name',
                     metavar='',
                     help='Naming convention for all nodes',
                     default='skylab')

    dbi = subpar.add_parser('db-show',
                            help='Show the local database information')
    dbi.set_defaults(method='db_show')
    dbi.add_argument('-n',
                     '--name',
                     metavar='',
                     help='Naming convention for all nodes',
                     default='skylab')

    skl = subpar.add_parser('scuttle-lab',
                            help='Show the local database information')
    skl.set_defaults(method='scuttle_lab')
    skl.add_argument('-n',
                     '--name',
                     metavar='',
                     help='Naming convention for all nodes',
                     default='skylab')

    bld = subpar.add_parser('build-lab',
                            help='Build a Rackspace Private Cloud Lab')
    bld.set_defaults(method='build_lab')

    net_data = bld.add_mutually_exclusive_group()
    net_data.add_argument('--net-id',
                          metavar='',
                          help='Id Number of the network you want to use.',
                          default=None)
    net_data.add_argument('--net-cidr',
                          metavar='',
                          help='CIDR for the Skylab Network',
                          default='172.16.51.0/24')

    bld.add_argument('--no-private',
                     help='Disable the default Private Network',
                     action='store_true',
                     default=False)
    bld.add_argument('-n',
                     '--name',
                     metavar='',
                     help='Naming convention for all nodes',
                     default='skylab')
    bld.add_argument('-i',
                     '--image',
                     metavar='',
                     help='The servers Image Name or ID, DEFAULT: %(default)s',
                     default='Ubuntu 12.04 LTS (Precise Pangolin)')
    bld.add_argument('--node-count',
                     metavar='',
                     type=int,
                     help='Number of servers in the lab, DEFAULT: %(default)s',
                     default=3)
    bld.add_argument('--controller-ram',
                     metavar='',
                     type=int,
                     help='Compute Node Ram, DEFAULT: %(default)s MB',
                     default=2048)
    bld.add_argument('--compute-ram',
                     metavar='',
                     type=int,
                     help='Control Node Ram, DEFAULT: %(default)s MB',
                     default=2048)
    bld.add_argument('-a',
                     '--admin-pass',
                     metavar='',
                     help=('Admin password for servers.'
                           ' DEFAULT: "%(default)s"'),
                     default=None)
    bld.add_argument('--ssh-port',
                     metavar='',
                     help=('SSH port to use for connection.'
                           ' DEFAULT: "%(default)s"'),
                     type=int,
                     default=22)
    bld.add_argument('--ssh-user',
                     metavar='',
                     help=('SSH username.'
                           ' DEFAULT: "%(default)s"'),
                     default='root')

    return vars(par.parse_args())