# =============================================================================
# Copyright [2013] [cloudnull]
# License Information :
# This software has no warranty, it is provided 'as is'. It is your
# responsibility to validate the behavior of the routines and its accuracy
# using the code provided. Consult the GNU General Public license for further
# details (see GNU General Public License).
# http://www.gnu.org/licenses/gpl.html
# =============================================================================


import logging

from novaclient.v1_1 import client as nova_client
from novaclient import shell


LOG = logging.getLogger(__name__)


class MissingCredentials(Exception):
    pass


class AuthPlugin(object):
    def __init__(self, password=False, key=False):
        """Craetes an authentication plugin for use with Rackspace."""

        self.user_password = password
        self.user_key = key
        print self.user_password, self.user_key
        self.auth_url = self.global_auth()

    def global_auth(self):
        """Return the Rackspace Cloud US Auth URL."""

        return "https://identity.api.rackspacecloud.com/v2.0/"

    def get_auth_url(self):
        """Return the Rackspace Cloud US Auth URL."""

        return self.global_auth()

    def _authenticate(self, cls, auth_url):
        """Authenticate against the Rackspace auth service."""

        if self.user_key is True:
            body = {
                "auth": {
                    "RAX-KSKEY:apiKeyCredentials": {
                        "username": cls.user,
                        "apiKey": cls.password,
                        "tenantName": cls.projectid
                    }
                }
            }
        elif self.user_password is True:
            body = {
                "auth": {
                    "passwordCredentials": {
                        "username": cls.user,
                        "password": cls.password,
                    }
                }
            }
        else:
            raise MissingCredentials('No Key or Password was provided.')

        return cls._authenticate(auth_url, body)

    def authenticate(self, cls, auth_url):
        """Authenticate against the Rackspace US auth service."""

        return self._authenticate(cls, auth_url)


class Creds(object):
    """Load Rackspace Credentials."""

    def __init__(self, user, region, key=None, password=None, tenant=None,
                 project_id=None, system='rackspace'):

        if any([key is not None, password is not None]):
            self.username = user
            if project_id is None:
                self.project_id = user
            else:
                self.project_id = project_id

            self.tenant_name = tenant
            self.api_key = key
            self.password = password
            self.region_name = region.upper()
            self.auth_system = system
            if self.password is not None:
                self.auth_plugin = AuthPlugin(password=True)
            elif self.api_key is not None:
                self.auth_plugin = AuthPlugin(key=True)
        else:
            raise MissingCredentials('No Key or Password was provided.')


class Clients(object):
    """Load in a Openstack client.

    Usage:
    >>> my_creds = rax_creds(
    ...     user='USERNAME',
    ...     region='RAX_REGION',
    ...     key='RAX_API_KEY',
    ...     password='RAX_PASSWROD' # Required for Swift Client
    ... )

    >>> auth = Clients(creds=my_creds)
    >>> novaclient = auth.get_client('novaclient')
    >>> servers = novaclient.servers.list()
    """

    def __init__(self, creds, args, insecure=False):
        self.args = args
        self.creds_dict = creds.__dict__
        self.creds_dict.update({'insecure': insecure,
                                'cacert': None})

    def nova(self):
        """Load the nova client."""

        creds_dict = {
            'username': self.creds_dict.get('username'),
            'project_id': self.creds_dict.get('project_id'),
            'tenant_id': self.creds_dict.get('tenant_name'),
            'region_name': self.creds_dict.get('region_name'),
            'insecure': self.creds_dict.get('insecure', False),
            'auth_system': self.creds_dict.get('auth_system'),
            'auth_plugin': self.creds_dict.get('auth_plugin')
        }

        if self.creds_dict.get('api_key') is not None:
            creds_dict['api_key'] = self.creds_dict.get('api_key')
        elif self.creds_dict.get('password') is not None:
            creds_dict['api_key'] = self.creds_dict.get('password')

        if self.args.get('debug') is True:
            shell.OpenStackComputeShell().setup_debugging(debug=True)
            creds_dict['http_log_debug'] = True

        LOG.debug(
            'novaclient connection created for "%s"' % creds_dict['username']
        )

        return nova_client.Client(**creds_dict)
