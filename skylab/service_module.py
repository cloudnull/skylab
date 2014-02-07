# =============================================================================
# Copyright [2013] [cloudnull]
# License Information :
# This software has no warranty, it is provided 'as is'. It is your
# responsibility to validate the behavior of the routines and its accuracy
# using the code provided. Consult the GNU General Public license for further
# details (see GNU General Public License).
# http://www.gnu.org/licenses/gpl.html
# =============================================================================

import time
import random
import json

import skylab as sk

from skylab import fabric_strings as fs
from skylab import build_fabric as bf
from skylab import utils as ut


MAX_FAULTS = 10


def _builder(client, server_dict, queue):
    for rty in ut.retryloop(attempts=MAX_FAULTS, delay=5):
        instance = client_create(client, build_hash=server_dict, queue=queue)
        if instance is None:
            rty()
        else:
            return instance


def bob_the_builder(client, args, target, queue):
    """Build Instances."""

    def _write_db(data):
        if data:
            with sk.Shelve(args['db_path']) as db:
                db_entry = data.__dict__
                if 'manager' in db_entry:
                    db_entry.pop('manager')
                db[args['name']][target['name']] = db_entry

    # Build our instance
    instance = _builder(client=client, server_dict=target, queue=queue)
    _write_db(data=instance)

    # Wait until the instance reports active
    wait_for_active(client, target, queue, instance.id)
    instance = client_server_get(client=client, server_id=instance.id)
    if not instance:
        print('The build process failed, the system will retry.')
        _kill_server(
            client=client,
            server_id=instance.id,
            server_dict=target,
            work_queue=queue
        )
    else:
        _write_db(data=instance)


def _kill_server(client, server_id, server_dict, work_queue):
    work_queue.put(server_dict)
    time.sleep(1)
    client_delete(client=client, server_id=server_id)


def wait_for_active(client, server_dict, queue, sid, MAX_RETRY=100):
    """Wait for the instance to be active.

    :param client: Authenticated Nova Client
    :param server_dict: Dictionary of server information
    :param queue: Multiprocessing Queue
    :param sid: Server ID Number
    :param tries: Number of allowed tries before faulting
    """

    instance = None
    try:
        for rty in ut.retryloop(attempts=MAX_RETRY, delay=5):
            # Retrieve the instance again so the status field updates
            instance = client_server_get(client, server_id=sid)
            status = instance.status
            idnum = instance.id

            if status == 'ACTIVE':
                print('Instance ID %s Name %s is ACTIVE'
                      % (instance.id, instance.name))
            elif status == 'ERROR':
                print('%s is in ERROR and will be deleted. '
                      'The job for server will be requeued.'
                      % idnum)
                _kill_server(client, idnum, server_dict, queue)
            else:
                rty()
    except sk.RetryError:
        wait = MAX_RETRY * 5
        if instance is None:
            print('Failure building the instance after "%s" seconds' % wait)
        else:
            print('Instance %s Never went ACTIVE within "%s" seconds.'
                  ' The instance will be killed.' % (instance.name, wait))
            client_delete(client=client, server_id=instance.id)


def check_limits(client, tenant_id, purposed_ram):
    """check limits.

    :param client: pre-setup nova client
    :param tenant_id: tenant id for the user
    :param purposed_ram: RAM usage being purposed for the build.
    """

    all_limits = client.limits.get(tenant_id=tenant_id)
    limits = all_limits._info
    a_limits = limits.get('absolute', sk.LimitsUnavailable('No Limits Found.'))
    max_networks = a_limits.get('maxTotalPrivateNetworks', 0)

    used_networks = a_limits.get('totalPrivateNetworksUsed', 0)
    max_ram = a_limits.get('maxTotalRAMSize', 0)
    used_ram = a_limits.get('totalRAMUsed', 0)

    if any([max_networks == -1, (max_networks - used_networks <= 0)]):
        raise sk.NoNetworksAvailable('No Networks are available for use.')
    elif purposed_ram > (max_ram - used_ram):
        return False
    else:
        return True


def skylab_network(client, name, net_cidr=None, net_id=None):
    """Set Network

    :param client: pre-setup nova client
    :param name: naming convention
    :param net_cidr: Network CIDR
    :param net_id: Network ID
    """

    nets = client.networks._list('/os-networksv2', "networks")

    if net_id is not None:
        net = [net for net in nets if net.id == net_id]
    else:
        net = [net for net in nets if net.label == name]

    if net:
        if len(net) == 1:
            return net[0].id
        else:
            raise sk.TooManyNetworks(
                'You have more than one "skylab" network.'
            )
    else:
        body = {
            "network": {
                "label": "skylab",
                "cidr": net_cidr
            }
        }
        net = client.networks._create('/os-networksv2', body, 'network')
        return net.id


def flavor_find(client, flavor_ram=None):
    """Set Network

    :param novaclient: pre-setup nova client
    :param flavor_ram: Ram amount in Mega Bytes
    """

    flavors = client.flavors.list()
    flavor_id = [{'id': flv.id,
                  'rxtx': flv.rxtx_factor}
                 for flv in flavors
                 if flv.ram == flavor_ram]

    if len(flavor_id) >= 2:
        max_rx = max(flv['rxtx'] for flv in flavor_id)
        return [flv for flv in flavor_id if flv['rxtx'] == max_rx][0]['id']
    else:
        if flavor_id:
            return flavor_id[0]['id']
        else:
            print('Here are a list of all the flavors available.')
            sk.print_horiz_table(
                [{'id': flv.id, 'ram': flv.ram, 'name': flv.name}
                 for flv in flavors]
            )
            raise SystemExit(
                'A Flavor ID for "%s" RAM was not found.' % flavor_ram
            )


def image_find(client, image):
    """Find the image that we will be using.

    :param novaclient: pre-setup nova client
    :param image: Name or ID of cloud Image.
    """

    images = client.images.list()
    image_ids = [img.id for img in images
                 if image in img.name or image == img.id]
    if image_ids:
        if len(image_ids) > 1:
            raise SystemExit(
                'We found more than one image with id/name of "%s" You are'
                ' going to be more specific' % image
            )
        else:
            return image_ids[0]
    else:
        print('Here are a list of all the images available.')
        sk.print_horiz_table(
            [{'id': img.id, 'name': img.name} for img in images]
        )
        raise SystemExit(
            'Image id/name "%s" was not found. To try using the image name'
            ' instead of the ID' % image
        )


def client_list(client):
    """Return a list of Servers."""

    for rty in ut.retryloop(attempts=MAX_FAULTS, delay=5):
        try:
            servers = client.servers.list()
        except Exception as exc:
            print('Issues in getting Server list. EXCEPTION: %s' % exc)
            rty()
        else:
            if servers is not None:
                return servers
            else:
                rty()


def client_delete(client, server_id):
    """Delete a server."""

    for rty in ut.retryloop(attempts=MAX_FAULTS, delay=5):
        try:
            client.servers.delete(server_id)
        except Exception as (exc, tb):
            print('ERROR IN CLIENT DELETE: "%s", TRACEBACK: %s' % (exc, tb))
            rty()


def client_create(client, build_hash, queue):
    """Return a list of Servers."""

    # Import requests to trap connection error exception.
    import requests

    for rty in ut.retryloop(attempts=MAX_FAULTS, delay=5):
        server = None
        try:
            time.sleep(random.randrange(1, 5))
            server = client.servers.create(**build_hash)
            if server is None:
                raise ValueError('Server Created returned a None Value.')
        except requests.ConnectionError:
            rty()
        except Exception as exc:
            if server is not None:
                _kill_server(
                    client=client,
                    server_id=server.id,
                    server_dict=build_hash,
                    work_queue=queue
                )
            print('ERROR IN CLIENT CREATE: "%s"' % exc)
            rty()
        else:
            return server


def client_server_get(client, server_id):
    """Return a list of Servers."""

    for rty in ut.retryloop(attempts=MAX_FAULTS, delay=5):
        try:
            server = client.servers.get(server_id)
        except Exception as exc:
            print('ERROR IN CLIENT GET: "%s"' % exc)
            rty()
        else:
            if server is not None:
                return server
            else:
                rty()


def client_key_find(client, key_name):
    """See if a Key exists in Nova.

    :return True||False:
    """

    for rty in ut.retryloop(attempts=MAX_FAULTS, delay=5):
        try:
            key = client.keypairs.findall(name=key_name)
        except Exception as exc:
            print('ERROR IN CLIENT KEY NAME LOOKUP: "%s"' % exc)
            rty()
        else:
            return key


def client_key_create(client, key_name, public_key):
    """Create a Public Key for Server injection in NOVA."""

    for rty in ut.retryloop(attempts=MAX_FAULTS, delay=5):
        try:
            client.keypairs.create(name=key_name, public_key=public_key)
        except Exception as exc:
            print('ERROR IN CLIENT KEY CREATE: "%s"' % exc)
            rty()


def construct_skylab(args):

    def first_boot_json(run_list):
        return json.dumps({'run_list': run_list}, indent=2)

    def get_addr(device, ip_type='public'):
        with sk.Shelve(args['db_path']) as db:
            try:
                dev = db[args['db_name']].get(device)
                addresses = dev.get('addresses')
                type_addresses = addresses.get(ip_type)
                for pa in type_addresses:
                    if pa.get('version') == 4:
                        return pa['addr']
                else:
                    raise sk.DeploymentFailure(
                        'No IPV4 addresss was found for Controller1'
                    )
            except AttributeError as exc:
                raise sk.DeploymentFailure(
                    'No IP address was found for Device: "%s". Exception "%s"'
                    % (device, exc)
                )

    def get_computes():
        compute_addrs = []
        with sk.Shelve(args['db_path']) as db:
            nodes = db[args['db_name']].keys()
            for node in nodes:
                name = '%s_compute' % args.get('name')
                if name in node:
                    compute_addrs.append(
                        get_addr(device=node, ip_type='public')
                    )
        return compute_addrs

    controller1_name = '%s_%s' % (args['name'], 'controller1')
    controller1_addr = get_addr(
        device=controller1_name
    )

    skylab_vips = get_addr(
        device=controller1_name,
        ip_type=args['name']
    )

    controller2_name = '%s_%s' % (args['name'], 'controller2')
    controller2_addr = get_addr(
        device=controller2_name
    )

    engine = bf.Engine(args=args)

    replacement_dict = {
        'chef_server_ip': controller1_addr,
        'cookbook_version': args['cookbook_version'],
        'name': args['name'],
        'rabbit_ip': skylab_vips,
        'rabbit_password': 'secrete',
        'vip_prefix': '.'.join(skylab_vips.split('.')[:-1]),
        'first_bt_json': '/etc/chef/first-boot.json',
        'client_loc': '/etc/chef/client.rb',
        'chef_env': args['name'],
    }

    compute_nodes = replacement_dict['compute_nodes'] = get_computes()

    cntrl1 = replacement_dict['controller1_runlist'] = [
        'role[ha-controller1]', 'role[single-network-node]'
    ]
    cntrl2 = replacement_dict['controller2_runlist'] = [
        'role[ha-controller2]', 'role[single-network-node]'
    ]
    compute = replacement_dict['compute_runlist'] = [
        'role[single-compute]'
    ]

    with sk.Shelve(args['db_path']) as db:
        db[args['db_name']].update(replacement_dict)

    # Controller1
    engine.run(
        name='Base Setup',
        string_obj=fs.BASE,
        target=controller1_addr
    )
    engine.run(
        name='keys',
        string_obj=fs.KEY_MAKER,
        target=controller1_addr
    )
    engine.put(
        name='Setting The Swap Script',
        string_obj=fs.SWAP_SCRIPT,
        remote_path='/opt/swap.sh',
        target=controller1_addr
    )
    engine.run(
        name='Enable Swap',
        string_obj=fs.ENABLE_SWAP,
        target=controller1_addr
    )
    engine.run(
        name='Apt Packages',
        string_obj=fs.INSTALL_APT_PACKAGES,
        target=controller1_addr
    )
    engine.run(
        name='Reconfigure Chef',
        string_obj=fs.CHEFSERVER_RECONFIGURE % replacement_dict,
        target=controller1_addr
    )
    engine.run(
        name='Setup Chef Client',
        string_obj=fs.CHEF_CLIENT,
        target=controller1_addr
    )
    engine.run(
        name='Setup Knife Client',
        string_obj=fs.KNIFE_CLIENT % replacement_dict,
        target=controller1_addr
    )
    engine.put(
        name='Settings Chef Client RB',
        string_obj=fs.CHEF_CLIENT_RB % replacement_dict,
        remote_path='/etc/chef/client.rb',
        target=controller1_addr
    )
    engine.run(
        name='Cookbook Upload',
        string_obj=fs.COOKBOOK_UPLOAD % replacement_dict,
        target=controller1_addr
    )
    replacement_dict['erlang_cookie'] = engine.get(
        name='erlang_cookie',
        string_obj='/var/lib/rabbitmq/.erlang.cookie',
        target=controller1_addr
    )
    replacement_dict['admin_pem'] = engine.get(
        name='admin_pem',
        string_obj='/etc/chef-server/admin.pem',
        target=controller1_addr
    )
    replacement_dict['chef_validator_pem'] = engine.get(
        name='chef_validator_pem',
        string_obj='/etc/chef-server/chef-validator.pem',
        target=controller1_addr
    )

    with sk.Shelve(args['db_path']) as db:
        db[args['db_name']].update(replacement_dict)

    engine.put(
        name='Environment File',
        string_obj=fs.ENVIRONMENT % replacement_dict,
        remote_path='/opt/base.env.json',
        target=controller1_addr
    )
    engine.run(
        name='Upload Environment',
        string_obj=fs.ENVIRONMENT_UPLOAD,
        target=controller1_addr
    )
    engine.put(
        name='First Boot JSON',
        string_obj=first_boot_json(cntrl1),
        remote_path=replacement_dict['first_bt_json'],
        target=controller1_addr
    )
    engine.put(
        name='chef_validator_pem',
        string_obj=replacement_dict['chef_validator_pem'],
        remote_path='/etc/chef/validation.pem',
        target=controller1_addr
    )
    engine.run(
        name='Bootstrap Controller1',
        string_obj=fs.RUN_CHEF_CLIENT % replacement_dict,
        target=controller1_addr
    )

    # Controller2
    engine.run(
        name='Base Setup',
        string_obj=fs.BASE,
        target=controller2_addr
    )
    engine.put(
        name='Setting The Swap Script',
        string_obj=fs.SWAP_SCRIPT,
        remote_path='/opt/swap.sh',
        target=controller2_addr
    )
    engine.run(
        name='Enable Swap',
        string_obj=fs.ENABLE_SWAP,
        target=controller2_addr
    )
    engine.run(
        name='Setup Chef Client',
        string_obj=fs.CHEF_CLIENT,
        target=controller2_addr
    )
    engine.put(
        name='First Boot JSON',
        string_obj=first_boot_json(cntrl2),
        remote_path='/etc/chef/first-boot.json',
        target=controller2_addr
    )
    engine.put(
        name='chef_validator_pem',
        string_obj=replacement_dict['chef_validator_pem'],
        remote_path='/etc/chef/validation.pem',
        target=controller2_addr
    )
    engine.put(
        name='Settings Chef Client RB',
        string_obj=fs.CHEF_CLIENT_RB % replacement_dict,
        remote_path='/etc/chef/client.rb',
        target=controller2_addr
    )
    engine.run(
        name='Bootstrap Controller2',
        string_obj=fs.RUN_CHEF_CLIENT % replacement_dict,
        target=controller2_addr
    )

    # Compute Nodes
    engine.parallel_run(
        name='Base Setup',
        string_obj=fs.BASE,
        target=compute_nodes
    )
    engine.parallel_put(
        name='Setting The Swap Script',
        string_obj=fs.SWAP_SCRIPT,
        remote_path='/opt/swap.sh',
        target=compute_nodes
    )
    engine.parallel_run(
        name='Enable Swap',
        string_obj=fs.ENABLE_SWAP,
        target=compute_nodes
    )
    engine.parallel_run(
        name='Setup Chef Client',
        string_obj=fs.CHEF_CLIENT,
        target=compute_nodes
    )
    engine.parallel_put(
        name='First Boot JSON',
        string_obj=first_boot_json(compute),
        remote_path='/etc/chef/first-boot.json',
        target=compute_nodes
    )
    engine.parallel_put(
        name='chef_validator_pem',
        string_obj=replacement_dict['chef_validator_pem'],
        remote_path='/etc/chef/validation.pem',
        target=compute_nodes
    )
    engine.parallel_run(
        name='Bootstrap Computer Node',
        string_obj=fs.RUN_CHEF_CLIENT % replacement_dict,
        target=compute_nodes
    )
