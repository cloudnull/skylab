# =============================================================================
# Copyright [2013] [Kevin Carter]
# License Information :
# This software has no warranty, it is provided 'as is'. It is your
# responsibility to validate the behavior of the routines and its accuracy
# using the code provided. Consult the GNU General Public license for further
# details (see GNU General Public License).
# http://www.gnu.org/licenses/gpl.html
# =============================================================================

import os
import json

import skylab as sk

from skylab import arguments
from skylab import osclients
from skylab import service_module as sm
from skylab import utils


def execute():
    """Execute the Tribble Application."""
    user_args = arguments.args()

    # Load the local DB for rebuilding
    user_args['db_path'] = sk.dbm_create(
        db_path=user_args.get('db_path'),
        db_name=user_args.get('db_name'),
        db_key=user_args.get('name')
    )

    Runner(args=user_args).run_method()


class Runner(object):
    """Run the application."""

    def __init__(self, args):
        """Run the application process from within the thread.

        :param args: parsed cli arguments.
        """

        self.client = None
        self.args = args

    def run_method(self):
        """Get action and run."""

        action = getattr(self, self.args.get('method'))
        if action is None:
            raise SystemExit('Died because something bad happened.')
        else:
            action()

    def build_lab(self):
        """Build the Openstack Lab."""

        queue = None

        # Load the Novaclient and Authenticate.
        creds = osclients.Creds(
            user=self.args.get('username'),
            region=self.args.get('region'),
            key=self.args.get('apikey'),
            password=self.args.get('password'),
            tenant=self.args.get('tenant_name'),
            project_id=self.args.get('project_id'),
        )

        clients = osclients.Clients(creds=creds, args=self.args)
        self.client = clients.nova()
        self.client.authenticate()

        # Set the tenant ID
        with utils.IndicatorThread(debug=self.args.get('debug')):
            tenant = self.client.client.tenant_id

            # Set the controller Flavor ID
            print('Finding Flavor Information')
            controller_flavor = sm.flavor_find(
                client=self.client, flavor_ram=self.args.get('controller_ram')
            )
            self.args['controller'] = {'flavor': controller_flavor}

            # Set the compute Flavor ID
            compute_flavor = sm.flavor_find(
                client=self.client, flavor_ram=self.args.get('compute_ram')
            )
            self.args['compute'] = {'flavor': compute_flavor}

            # Add up total purposed ram for the build
            con_ram = self.args.get('controller_ram')
            com_ram = self.args.get('compute_ram')
            t_ram = con_ram + com_ram

            print('Checking Build against Limits')
            in_limits = sm.check_limits(
                client=self.client,
                tenant_id=tenant,
                purposed_ram=t_ram
            )
            if in_limits is False:
                raise sk.NotEnoughRam(
                    'This build is not possible, your account does not'
                    ' have enough RAM available.'
                )

            print('Defining the Network')
            network = sm.skylab_network(
                client=self.client,
                name=self.args.get('name'),
                net_cidr=self.args.get('net_cidr'),
                net_id=self.args.get('net_id')
            )

            print('Checking for Image')
            image_id = sm.image_find(
                client=self.client,
                image=self.args.get('image')
            )
            nics = [
                {'net-id': "00000000-0000-0000-0000-000000000000"},
                {'net-id': network}
            ]
            if self.args.get('no_private') is False:
                nics.append(
                    {'net-id': "11111111-1111-1111-1111-111111111111"}
                )

            build_kwargs = {
                'image': image_id,
                'nics': nics
            }

            print('Defining the key')
            if self.args.get('admin_pass') is not None:
                build_kwargs['admin_pass'] = self.args['admin_pass']

            if self.args.get('key_name'):
                if not sm.client_key_find(self.client,
                                          key_name=self.args['key_name']):
                    key_path = os.path.expanduser(self.args['key_location'])
                    if os.path.exists(key_path):
                        with open(key_path, 'rb') as key:
                            sm.client_key_create(
                                self.client,
                                key_name=self.args['key_name'],
                                public_key=key.read()
                            )
                        build_kwargs['key_name'] = self.args['key_name']
                else:
                    build_kwargs['key_name'] = self.args['key_name']

            print('Loading Work Queue')
            if self.args['node_count'] < 3:
                raise sk.NotEnoughNodes(
                    'The node count is too low. You have set "%s" but it needs'
                    ' to be a minimum of "3".' % self.args['node_count']
                )
            else:
                # Load our queue
                queue = utils.basic_queue()
                self.args['compute'].update(build_kwargs)
                for c_node in range(self.args['node_count'] - 2):
                    c_node += 1
                    compute = {
                        'name': '%s_compute%s' % (self.args['name'], c_node)
                    }
                    compute.update(self.args['compute'])
                    queue.put(compute)

                self.args['controller'].update(build_kwargs)
                for c_node in range(2):
                    c_node += 1
                    controller = {
                        'name': '%s_controller%s' % (self.args['name'], c_node)
                    }
                    controller.update(self.args['controller'])
                    queue.put(controller)

        # Prep the threader
        proc_args = {'client': self.client,
                     'args': self.args,
                     'queue': queue,
                     'job_action': sm.bob_the_builder}
        with utils.IndicatorThread(work_q=queue, debug=self.args.get('debug')):
            print('Building "%s" nodes' % self.args['node_count'])
            utils.worker_proc(
                kwargs=proc_args
            )

        # Construct all the things.
        with utils.IndicatorThread(work_q=queue, debug=self.args.get('debug')):
            sm.construct_skylab(args=self.args)

    def db_show(self):
        with sk.Shelve(file_path=self.args['db_path']) as db:
            print(json.dumps(dict(db), indent=4))

    def lab_info(self):

        def get_addr(server, net_name):
            if 'addresses' in srv:
                addresses = server['addresses'].get(net_name)
                if addresses is not None:
                    for addr in addresses:
                        if addr.get('version') == 4:
                            return addr.get('addr')
                else:
                    return None

        name = self.args['name']
        with sk.Shelve(file_path=self.args['db_path']) as db:
            db_data = dict(db)
            info = [db_data[name][srv] for srv in db_data[name].keys()
                    if srv.startswith(name)]

            if self.args.get('server'):
                pass
            else:
                print_data = []
                skynet = '%s_address' % name
                for srv in info:
                    print_data.append({
                        'id': srv.get('id'),
                        'name': srv.get('name'),
                        skynet: get_addr(server=srv, net_name=name),
                        'public_net': get_addr(server=srv, net_name='public')
                    })

                sk.print_horiz_table(print_data)

    def scuttle_lab(self):
        with utils.IndicatorThread(debug=self.args.get('debug')):
            servers = [
                (server.id, server.name)
                for server in sm.client_list(self.client)
                if server.name.startswith(self.args['name'])
            ]

            with sk.Shelve(file_path=self.args['db_path']) as db:
                for server in servers:
                    if self.args['name'] in db:
                        lab_db = db[self.args['name']]
                        if lab_db.get(server[1]) is not None:
                            del lab_db[server[1]]
                            sm.client_delete(self.client, server_id=server[0])


if __name__ == '__main__':
    execute()
