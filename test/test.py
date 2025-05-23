# type: ignore
"""
This is the Pygrister test suite.
=================================

Before running the tests, you must set up a few things on the Grist side.
Either if you plan to run the tests against the standard SaaS Grist 
or against a self-managed instance of Grist, 
- find out or create your API key;
- create an empty team site - that is, only the "Home" workspace should 
  be present: in SaaS Grist, a free site will do;
  - (but, if you are running a self-managed "mono-site" Grist, then of course 
    the team site will be the one indicated by the ``GRIST_SINGLE_ORG`` 
    env variable that you will provide separately.)

If you are planning to run the tests many times against the standard SaaS Grist, 
in fact you may want to start with an entirely separate Grist account, to avoid 
cluttering your "home" db with bogus users data (see below).

Remember, the test suite *will not make use* of your regular configuration 
files (eg., ``~/.gristapi/config.json``). 
Everything *must* be provided in a separate ``config_test.json`` in the same 
directory as this file. Edit the already present json file as follows:
- "GRIST_API_KEY": your api key
- "GRIST_TEAM_SITE": your team site (you may ignore if running a mono-site Grist)
- "GRIST_SELF_MANAGED": set to "Y" if you are running a self-managed Grist
- "GRIST_SELF_MANAGED_HOME": the main url of your self-managed Grist
- "GRIST_SELF_MANAGED_SINGLE_ORG": "Y" if you are running the mono-team flavour 
- "GRIST_TEST_RUN_USER_TESTS": "N" to skip the tests that create users 
  (special, see below)
- "GRIST_TEST_RUN_SCIM_TESTS": "N" to skip all SCIM api tests (special, see below)
- "GRIST_TEST_RUN_EXT_ATTACH_TESTS": "N" to skip the tests that need an external 
  storage for attachments (special, see below)

Note: no other config key should be configured for the test suite. 

The test suite will leave several objects (workspaces and docs) in your 
team site. The objects created have unique names, so it should be safe 
re-running the test suite with the same sites: however, you may want 
to clean up eventually. 

Test users are a separate problem. A few tests will create new users in your 
test team site: even if you remove them manually in the "manage team" 
section of the GUI, you are only deleting the user-team association, but 
the user data will remain in your "home" database (which you currently cannot 
access in SaaS Grist). You really can't completely delete a user from the GUI 
and, in SaaS Grist, you can't use the SCIM apis (which are currently 
not enabled). It is normally not a problem to leave a few inactive users 
in the database. However, if you end up running the test suite hundreds of 
times, you may want to avoid the clutter. In a self-managed instance of Grist, 
you just throw the container away after a while. In SaaS Grist, you may want 
to activate a separate account to run the tests. 
To help you keep test users under control, we added a special configuration 
key, only useful when running the test suite: set "GRIST_TEST_RUN_USER_TESTS" 
to "N" to skip every test that may create a user. 

SCIM apis are a separate problem: SCIM tests are automatically skipped when you 
run the test suite against the regular Grist SaaS (because SCIM is not enabled 
there); but, even in self-hosted Grist, you have to enable SCIM first by 
setting the GRIST_ENABLE_SCIM env variable. If you are self-hosted, but you 
don't want to enable SCIM in your environment, set our special configuration key 
"GRIST_TEST_RUN_SCIM_TESTS" to "N" (in config_test.json file) to skip all SCIM 
tests altogether, so you don't get any spurious errors. 

Another separate problem is how to test the Apis that require an external storage 
for attachments. If your testing environment already supports external storage 
(that is, you have a bucket in place and a "GRIST_EXTERNAL_ATTACHMENTS_MODE" 
variable set to "snapshots") then you may set our special configuration key 
"GRIST_TEST_RUN_EXT_ATTACH_TESTS" to include the tests dealing with storages. 
If not, leave the key unset (the default) to skip those tests. 

A few object will also be downloaded in your current directory. Moreover, 
tests involving user/permission manipulation may trigger email notifications 
from Grist. 

Finally, please keep in mind that the purpose here is testing the Pygrister 
functions, not the underlying Grist api. Basically, we make sure that the 
api calls work as expected from our side of the business, but the calls 
themselves are always pretty basic. 

**Note**: if you are reading this file to learn how to use Pygrister, 
please note that all the function calls here always pass the "id params" 
(``team_id``, ``doc_id``...) explicitly. This is because we need to 
insulate the test suite from any external config file, but in real life 
Pygrister will pick up the missing parts from the configuration. 
So, whenever you see here a function call like 
``<grist>.add_records(<table>, records, doc_id=self.doc_id, team_id=self.team_id)``, 
in normal usage it's just ``<grist>.add_records(<table>, records)``.

"""

from pathlib import Path
import time
from datetime import datetime
import json
import unittest
from requests import HTTPError, ConnectTimeout

from pygrister import api
from pygrister import config
from pygrister.exceptions import *

# standard config values used by tests
default_config = {
    "GRIST_SERVER_PROTOCOL": "https://",
    "GRIST_API_SERVER": "getgrist.com",
    "GRIST_API_ROOT": "api",
    "GRIST_RAISE_ERROR": "Y",
    "GRIST_SAFEMODE": "N",
    "GRIST_WORKSPACE_ID": "1000000000000", # no test should ever hit this
    "GRIST_DOC_ID": "_bogus_",             # no test should ever hit this
}

HERE = Path(__file__).absolute().parent
with open(HERE / 'config_test.json') as f:
    TEST_CONFIGURATION = json.loads(f.read())
TEST_CONFIGURATION.update(default_config)

total_apicalls = [] # behold, the hack of the mutable global!
def tearDownModule():
    print('\nTotal api calls:', sum(total_apicalls))


# two helper functions to prepare playground worspaces and documents
def _make_ws(team_id):
    gristapi = api.GristApi(config=TEST_CONFIGURATION)
    name = 'ws'+str(time.time_ns())
    st, ws_id = gristapi.add_workspace(name, team_id)
    total_apicalls.append(gristapi.apicalls)
    return ws_id, name

def _make_doc(ws_id):
    gristapi = api.GristApi(config=TEST_CONFIGURATION)
    name = 'doc'+str(time.time_ns())
    st, doc_id = gristapi.add_doc(name, ws_id=ws_id)
    total_apicalls.append(gristapi.apicalls)
    return doc_id


class BaseTestPyGrister(unittest.TestCase):
    def setUp(self):
        self.g = api.GristApi(config=TEST_CONFIGURATION)
    
    def tearDown(self):
        total_apicalls.append(self.g.apicalls)


class TestVarious(BaseTestPyGrister):
    @classmethod
    def setUpClass(cls):
        cls.team_id = TEST_CONFIGURATION['GRIST_TEAM_SITE']

    def test_raise_error(self):
        with self.assertRaises(HTTPError):
            self.g.list_workspaces('_bogus_team_id_')
        self.g.update_config({'GRIST_RAISE_ERROR': 'N'})
        st, res = self.g.list_workspaces('_bogus_team_id_')
        self.assertGreaterEqual(st, 300)

    def test_ok(self):
        try:
            st, res = self.g.see_workspace(1) # hopefully, not a valid ws id!
        except HTTPError:
            pass
        self.assertFalse(self.g.ok)
        st, res = self.g.see_team()
        self.assertTrue(self.g.ok)

    def test_custom_configurator(self):
        self.assertEqual(self.g.configurator.config['GRIST_RAISE_ERROR'], 'Y')
        c = config.Configurator(config={'GRIST_RAISE_ERROR': 'N'})
        old_c = self.g.configurator
        self.g.configurator = c
        self.assertEqual(self.g.configurator.config['GRIST_RAISE_ERROR'], 'N')
        self.g.configurator = old_c
        self.assertEqual(self.g.configurator.config['GRIST_RAISE_ERROR'], 'Y')
        g = api.GristApi(custom_configurator=c)
        self.assertEqual(g.configurator.config['GRIST_RAISE_ERROR'], 'N')
        with self.assertRaises(GristApiNotConfigured):
            g = api.GristApi(config={'foo':'bar'}, custom_configurator=c)

    def test_reconfig(self):
        self.assertEqual(self.g.configurator.config['GRIST_RAISE_ERROR'], 'Y')
        self.assertEqual(self.g.configurator.config['GRIST_SAFEMODE'], 'N')
        # update_config is for incremental changes
        self.g.update_config({'GRIST_SAFEMODE': 'Y'})
        self.assertEqual(self.g.configurator.config['GRIST_RAISE_ERROR'], 'Y')
        self.assertEqual(self.g.configurator.config['GRIST_SAFEMODE'], 'Y')
        self.g.update_config({'GRIST_RAISE_ERROR': 'N'})
        self.assertEqual(self.g.configurator.config['GRIST_RAISE_ERROR'], 'N')
        self.assertEqual(self.g.configurator.config['GRIST_SAFEMODE'], 'Y')
        # reconfig is for re-building from scratch
        self.g.reconfig({'GRIST_RAISE_ERROR': 'Y'})
        self.assertEqual(self.g.configurator.config['GRIST_RAISE_ERROR'], 'Y')
        self.assertEqual(self.g.configurator.config['GRIST_SAFEMODE'], 'N')

    def test_request_options(self):
        # as an example of extra-options, we test a timeout limit
        # let's make it so the server is 'http://10.255.255.1'
        self.g.update_config({'GRIST_SERVER_PROTOCOL': 'http://', 
                              'GRIST_TEAM_SITE': '10', 
                              'GRIST_API_SERVER': '255.255.1', 
                              # maybe we are self-managed instead
                              'GRIST_SELF_MANAGED_HOME': 'http://10.255.255.1'})
        # without this, test will take forever, before failing with ConnectTimeout
        self.g.request_options = {'timeout': 1}
        with self.assertRaises(ConnectTimeout):
            st, res = self.g.see_team()

    def test_request_session(self):
        self.g.open_session()
        # simple GET api
        st, res = self.g.see_team()
        self.assertEqual(st, 200)
        name = str(time.time_ns())
        # POST
        st, ws_id = self.g.add_workspace(name, self.team_id)
        self.assertEqual(st, 200)
        self.assertIn('Cookie', self.g.req_headers) # the session thing is working
        name = str(time.time_ns())
        st, doc_id = self.g.add_doc(name, ws_id=ws_id)
        self.assertEqual(st, 200)
        # GET in download mode
        st, res = self.g.download_csv(name+'.csv', table_id='Table1',
                                      doc_id=doc_id, team_id=self.team_id)
        self.assertEqual(st, 200)
        # POST in upload mode
        f = HERE / 'imgtest.jpg'
        st, res = self.g.upload_attachments([f], doc_id=doc_id, team_id=self.team_id)
        self.assertEqual(st, 200)
        # PATCH
        name = str(time.time_ns())
        st, res = self.g.update_workspace(name, ws_id=ws_id)
        self.assertEqual(st, 200)
        # DELETE
        st, res = self.g.delete_doc(doc_id)
        self.assertEqual(st, 200)
        self.g.close_session()

class TestUsersNoScim(BaseTestPyGrister):
    @classmethod
    def setUpClass(cls):
        cls.team_id = TEST_CONFIGURATION['GRIST_TEAM_SITE']

    def test_delete_myself(self):
        # this is not yet implemented
        with self.assertRaises(api.GristApiNotImplemented):
            self.g.delete_myself('bogus')

# note: to test scim ops, you need both GRIST_SELF_MANAGED here (because the 
# regular Grist SaaS does not support scim) and GRIST_ENABLE_SCIM on the server!
@unittest.skipIf(TEST_CONFIGURATION['GRIST_SELF_MANAGED'] == 'N', '')
@unittest.skipIf(TEST_CONFIGURATION['GRIST_TEST_RUN_SCIM_TESTS'] == 'N', '')
class TestUsersScim(BaseTestPyGrister):
    @classmethod
    def setUpClass(cls):
        cls.team_id = TEST_CONFIGURATION['GRIST_TEAM_SITE']
    
    def test_see_user_and_myself(self):
        st, res = self.g.see_myself()
        self.assertEqual(st, 200)
        myself_id = int(res['id']) 
        st, res = self.g.see_user(myself_id)
        self.assertEqual(st, 200)

    def test_list_users_raw(self):
        # this demonstrates using the "raw" api call, with manual pagination
        st, res = self.g.list_users_raw(1, 10)
        self.assertEqual(st, 200)
        id_first = res['Resources'][0]['id']
        id_second = res['Resources'][1]['id']
        st, res = self.g.list_users_raw(2, 10)
        self.assertEqual(st, 200)
        self.assertEqual(res['Resources'][0]['id'], id_second)
        # passing an out-of-range index results in returning the first
        # items anyway: I believe this is a mistake...
        st, res = self.g.list_users_raw(1000000, 10)
        self.assertEqual(st, 200)
        # if this fails, it means the issue has been fixed:
        self.assertEqual(res['Resources'][0]['id'], id_first)
        # and now for the filters! I can't make this work... 
        # note that the very same filter will work in the search api...
        # if this fails, it means it was a bug and it has been fixed:
        with self.assertRaises(HTTPError):
            st, res = self.g.list_users_raw(filter='userName co example')

    def test_list_users(self):
        # this demonstates using the fancy, auto-paginating api call
        for st, res in self.g.list_users(): 
            self.assertEqual(st, 200)
        # now let's iterate manually
        user_list = self.g.list_users()
        self.assertEqual(len(user_list), 0)
        st, chunk = next(user_list)
        self.assertEqual(st, 200)
        self.assertGreater(len(user_list), 0)
        # here we can fix the out-of-range issue:
        user_list = self.g.list_users(1000000, 10)
        with self.assertRaises(StopIteration):
            next(user_list)

    @unittest.skipIf(TEST_CONFIGURATION['GRIST_TEST_RUN_USER_TESTS'] == 'N', '')
    def test_add_update_delete_user(self):
        base_name = str(time.time_ns())
        usr, email = f'{base_name}', f'{base_name}@example.com'
        st, user_id = self.g.add_user(usr, [email])
        self.assertEqual(st, 201)
        # let's change the locale for this user
        ops = [{'op': 'replace', 'path': 'locale', 'value': 'es'}]
        st, res = self.g.update_user(user_id, ops)
        self.assertEqual(st, 200)
        st, usr = self.g.see_user(user_id)
        self.assertEqual(st, 200)
        self.assertEqual(usr['locale'], 'es')
        # now delete the user
        st, res = self.g.delete_user(user_id)
        self.assertEqual(st, 204)
        # if the following fails, it means Grist fixed the api,  
        # which now returns no response body at all
        self.assertIsNone(res)
        # now double-check that the user is gone
        self.g.update_config({'GRIST_RAISE_ERROR': 'N'})
        st, res = self.g.see_user(user_id)
        self.assertEqual(st, 404)

    def test_search_users_raw(self):
        # this demonstrates using the "raw" api call, with manual pagination
        st, res = self.g.search_users_raw(1, 10)
        self.assertEqual(st, 200)
        # and now for the filters... let's add a user first
        # (note: a bunch of "@getgrist" users should always be present)
        st, res = self.g.search_users_raw(filter='userName co getgrist')
        self.assertEqual(st, 200)

    def test_search_users(self):
        # this demonstates using the fancy, auto-paginating api call
        for st, res in self.g.search_users(): 
            self.assertEqual(st, 200)
        # now let's iterate manually
        user_list = self.g.search_users()
        self.assertEqual(len(user_list), 0)
        st, chunk = next(user_list)
        self.assertEqual(st, 200)
        self.assertGreater(len(user_list), 0)

    @unittest.skipIf(TEST_CONFIGURATION['GRIST_TEST_RUN_USER_TESTS'] == 'N', '')
    def test_bulk_users(self):
        # let's add a few users in bulk
        base_name = str(time.time_ns())
        users = [[f'{base_name}_01', f'{base_name}_01@example.com'],
                 [f'{base_name}_02', f'{base_name}_02@example.com'],
                 [f'{base_name}_03', f'{base_name}_03@example.com']]
        ops = [{'method': 'POST', 'path': '/scim/v2/Users', 
                'data': {'name': usr, 
                         'emails': {'value': eml, 'primary': True}}}
                for (usr, eml) in users]
        st, res = self.g.bulk_users(operations=ops)
        self.assertEqual(st, 200)
        # note: the api call should work, but each actual ops will fail with 
        # http 400, because the path is incorrect... can't figure out why, 
        # maybe a bug in the underlying Grist api
        self.assertEqual(res, [400, 400, 400]) # hoping this will fail some day!

    def test_see_scim_schemas(self):
        st, res = self.g.see_scim_schemas()
        self.assertEqual(st, 200)

    def test_see_scim_config(self):
        st, res = self.g.see_scim_config()
        self.assertEqual(st, 200)

    def test_see_scim_resources(self):
        st, res = self.g.see_scim_resources()
        self.assertEqual(st, 200)

class TestTeamSites(BaseTestPyGrister):
    @classmethod
    def setUpClass(cls):
        cls.team_id = TEST_CONFIGURATION['GRIST_TEAM_SITE']
     
    def test_list_team_sites(self):
        st, res = self.g.list_team_sites()
        self.assertEqual(st, 200)
        self.assertIsInstance(res, list)
    
    def test_see_team(self):
        st, res = self.g.see_team(TestTeamSites.team_id)
        self.assertEqual(st, 200)
        self.assertIsInstance(res, dict)
        with self.assertRaises(HTTPError):
            st, res = self.g.see_team('bogus')

    def test_update_team(self):
        self.g.update_config({'GRIST_SAFEMODE': 'Y'})
        with self.assertRaises(api.GristApiInSafeMode):
            self.g.update_team('bogus', TestTeamSites.team_id)
        self.g.update_config({'GRIST_SAFEMODE': 'N'})
        st, res = self.g.update_team('apitestrenamed', TestTeamSites.team_id)
        self.assertEqual(st, 200)
        st, res = self.g.update_team('apitestteam', TestTeamSites.team_id)
        self.assertEqual(st, 200)
        self.assertIsNone(res)

    @unittest.skip
    def test_delete_team(self):
        # since there is no way to *create* a team in the first place, 
        # we won't test team deletion!
        pass

    def test_list_team_users(self):
        st, res = self.g.list_team_users(TestTeamSites.team_id)
        self.assertIsInstance(res, list)
        self.assertEqual(st, 200)

    @unittest.skipIf(TEST_CONFIGURATION['GRIST_TEST_RUN_USER_TESTS'] == 'N', '')
    def test_update_team_users(self):
        name = str(time.time_ns())[-5:]
        users = {f'u{name}a@example.com': 'editors', 
                 f'u{name}b@example.com': 'owners'}
        st, res = self.g.update_team_users(users, self.team_id)
        self.assertIsNone(res)
        self.assertEqual(st, 200)

class TestWorkspaces(BaseTestPyGrister):
    @classmethod
    def setUpClass(cls):
        cls.team_id = TEST_CONFIGURATION['GRIST_TEAM_SITE']
        gristapi = api.GristApi(config=TEST_CONFIGURATION)
        st, res = gristapi.list_workspaces(cls.team_id) # should work :)
        cls.workspace_id = res[0]['id']
        cls.workspace_name = res[0]['name']
        total_apicalls.append(gristapi.apicalls)

    def test_list_workspaces(self):
        st, res = self.g.list_workspaces(self.team_id)
        self.assertIsInstance(res, list)
        self.assertEqual(st, 200)

    def test_see_workspace(self):
        st, res = self.g.see_workspace(self.workspace_id)
        self.assertIsInstance(res, dict)
        self.assertEqual(st, 200)

    def test_add_delete_workspace(self):
        self.g.update_config({'GRIST_SAFEMODE': 'Y'})
        name = str(time.time_ns())
        with self.assertRaises(api.GristApiInSafeMode):
            self.g.add_workspace(name, self.team_id)
        self.g.update_config({'GRIST_SAFEMODE': 'N'})
        name = str(time.time_ns())
        st, ws_id = self.g.add_workspace(name, self.team_id)
        self.assertEqual(st, 200)
        st, res = self.g.delete_workspace(ws_id)
        self.assertIsNone(res)
        self.assertEqual(st, 200)
        
    def test_update_workspace(self):
        name = str(time.time_ns())
        st, res = self.g.update_workspace(name, self.workspace_id)
        self.assertIsNone(res)
        self.assertEqual(st, 200)
        st, res = self.g.update_workspace(self.workspace_name, self.workspace_id)
        self.assertIsNone(res)
        self.assertEqual(st, 200)

    def test_list_workspace_users(self):
        st, res = self.g.list_workspace_users(self.workspace_id)
        self.assertIsInstance(res, list)
        self.assertEqual(st, 200)
    
    @unittest.skipIf(TEST_CONFIGURATION['GRIST_TEST_RUN_USER_TESTS'] == 'N', '')
    def test_update_workspace_users(self):
        name = str(time.time_ns())[-5:]
        users = {f'u{name}a@example.com': 'editors', 
                 f'u{name}b@example.com': 'owners'}
        # note: must be added as team users first!
        st, res = self.g.update_team_users(users, self.team_id)
        self.assertIsNone(res)
        self.assertEqual(st, 200)
        st, res = self.g.update_workspace_users(users, self.workspace_id)
        self.assertIsNone(res)
        self.assertEqual(st, 200)

    def test_workspace_cross_site(self):
        # see/add workspace in our site "from" another site
        self.g.update_config({'GRIST_TEAM_SITE': 'docs'})
        st, res = self.g.see_workspace(self.workspace_id)
        self.assertIsInstance(res, dict)
        self.assertEqual(st, 200)
        name = str(time.time_ns())
        st, res = self.g.add_workspace(name, self.team_id)
        self.assertIsInstance(res, int)
        self.assertEqual(st, 200)

class TestDocs(BaseTestPyGrister):
    @classmethod
    def setUpClass(cls):
        cls.team_id = TEST_CONFIGURATION['GRIST_TEAM_SITE']
        cls.workspace_id, cls.workspace_name = _make_ws(cls.team_id)

    def test_create_delete_doc(self):
        name = str(time.time_ns())
        st, doc_id = self.g.add_doc(name, ws_id=self.workspace_id)
        self.assertIsInstance(doc_id, str)
        self.assertEqual(st, 200)
        st, res = self.g.delete_doc(doc_id)
        self.assertIsNone(res)
        self.assertEqual(st, 200)
        # shouldn't be possible in safemode
        self.g.update_config({'GRIST_SAFEMODE': 'Y'})
        name = str(time.time_ns())
        with self.assertRaises(api.GristApiInSafeMode):
            self.g.add_doc(name, self.workspace_id)

    def test_delete_doc_history(self):
        name = str(time.time_ns())
        st, doc_id = self.g.add_doc(name, ws_id=self.workspace_id)
        self.assertIsInstance(doc_id, str)
        self.assertEqual(st, 200)
        st, res = self.g.delete_doc_history(0, doc_id)
        self.assertIsNone(res)
        self.assertEqual(st, 200)

    @unittest.expectedFailure
    def test_create_delete_doc_cross_site(self):
        # fun fact: cross-site doc creation is allowed...
        self.g.update_config({'GRIST_TEAM_SITE': 'docs'})
        name = str(time.time_ns())
        st, doc_id = self.g.add_doc(name, ws_id=self.workspace_id)
        self.assertIsInstance(doc_id, str)
        self.assertEqual(st, 200)
        # ...but deletion is not, EXCEPT when we operate from 'docs', apparently 
        # this should be investigated further, maybe 'docs' is a catch-all 
        # team id hosting "all" the docs? In the meantime, we mark this one 
        # as an expectedFailure
        with self.assertRaises(HTTPError):
            self.g.delete_doc(doc_id)

    def test_see_doc(self):
        name = str(time.time_ns())
        st, doc_id = self.g.add_doc(name, ws_id=self.workspace_id)
        self.assertIsInstance(doc_id, str)
        self.assertEqual(st, 200)
        st, res = self.g.see_doc(doc_id, self.team_id)
        self.assertIsInstance(res, dict)
        self.assertEqual(st, 200)

    def test_update_doc(self):
        name = str(time.time_ns())
        st, doc_id = self.g.add_doc(name, ws_id=self.workspace_id)
        self.assertIsInstance(doc_id, str)
        self.assertEqual(st, 200)
        st, res = self.g.update_doc('new'+name, doc_id=doc_id)
        self.assertIsNone(res)
        self.assertEqual(st, 200)
        st, res = self.g.update_doc(pinned=True, doc_id=doc_id)
        self.assertIsNone(res)
        self.assertEqual(st, 200)

    def test_move_doc(self):
        name = str(time.time_ns())
        st, doc_id = self.g.add_doc(name, ws_id=self.workspace_id)
        self.assertIsInstance(doc_id, str)
        self.assertEqual(st, 200)
        st, ws_id = self.g.add_workspace('ws'+name, self.team_id)
        self.assertIsInstance(ws_id, int)
        self.assertEqual(st, 200)
        st, res = self.g.move_doc(ws_id, doc_id, self.team_id)
        self.assertIsNone(res)
        self.assertEqual(st, 200)

    def test_reload_doc(self):
        name = str(time.time_ns())
        st, doc_id = self.g.add_doc(name, ws_id=self.workspace_id)
        self.assertIsInstance(doc_id, str)
        self.assertEqual(st, 200)
        st, res = self.g.reload_doc(doc_id)
        self.assertIsNone(res)
        self.assertEqual(st, 200)

    def test_list_doc_users(self):
        name = str(time.time_ns())
        st, doc_id = self.g.add_doc(name, ws_id=self.workspace_id)
        self.assertIsInstance(doc_id, str)
        self.assertEqual(st, 200)
        st, res = self.g.list_doc_users(doc_id, self.team_id)
        self.assertIsInstance(res, list)
        self.assertEqual(st, 200)

    @unittest.skipIf(TEST_CONFIGURATION['GRIST_TEST_RUN_USER_TESTS'] == 'N', '')
    def test_update_doc_users(self):
        name = str(time.time_ns())
        st, doc_id = self.g.add_doc(name, ws_id=self.workspace_id)
        self.assertIsInstance(doc_id, str)
        self.assertEqual(st, 200)
        users = {f'u{name[-5:]}a@example.com': 'editors', 
                 f'u{name[-5:]}b@example.com': 'owners'}
        # note: no need to add these to your team/workspace first
        st, res = self.g.update_doc_users(users, doc_id=doc_id, 
                                          team_id=self.team_id)
        self.assertIsNone(res)
        self.assertEqual(st, 200)

    def test_download_sqlite(self):
        name = str(time.time_ns())
        st, doc_id = self.g.add_doc(name, ws_id=self.workspace_id)
        self.assertIsInstance(doc_id, str)
        self.assertEqual(st, 200)
        st, res = self.g.download_sqlite(Path(f'{name}.sqlite'), 
            nohistory=True, template=True, doc_id=doc_id, team_id=self.team_id)
        self.assertIsNone(res)
        self.assertEqual(st, 200)

    def test_download_excel(self):
        name = str(time.time_ns())
        st, doc_id = self.g.add_doc(name, ws_id=self.workspace_id)
        self.assertIsInstance(doc_id, str)
        self.assertEqual(st, 200)
        st, res = self.g.download_excel(Path(f'{name}.xls'), table_id='Table1',
                                        doc_id=doc_id, team_id=self.team_id)
        self.assertIsNone(res)
        self.assertEqual(st, 200)
    
    def test_download_csv(self):
        name = str(time.time_ns())
        st, doc_id = self.g.add_doc(name, ws_id=self.workspace_id)
        self.assertIsInstance(doc_id, str)
        self.assertEqual(st, 200)
        st, res = self.g.download_csv(Path(f'{name}.csv'), table_id='Table1',
                                      doc_id=doc_id, team_id=self.team_id)
        self.assertIsNone(res)
        self.assertEqual(st, 200)

    def test_download_schema(self):
        name = str(time.time_ns())
        st, doc_id = self.g.add_doc(name, ws_id=self.workspace_id)
        self.assertIsInstance(doc_id, str)
        self.assertEqual(st, 200)
        st, res = self.g.download_schema('Table1', doc_id=doc_id, 
                                          team_id=self.team_id)
        self.assertIsInstance(res, dict)
        self.assertEqual(st, 200)
        st, res = self.g.download_schema('Table1', filename=Path(f'{name}.json'), 
                                         doc_id=doc_id, team_id=self.team_id)
        self.assertIsNone(res)
        self.assertEqual(st, 200)

class TestRecordAccess(BaseTestPyGrister): 
    # we test "/records", "/data" and "/sql" endpoints here (no converters)
    @classmethod
    def setUpClass(cls):
        cls.team_id = TEST_CONFIGURATION['GRIST_TEAM_SITE']
        ws_id, name = _make_ws(cls.team_id)
        cls.doc_id = _make_doc(ws_id)
        cols = [{'id': 'Astr', 'fields': {'label': 'Astr', 'type': 'Text'}},
                {'id': 'Bnum', 'fields': {'label': 'Bnum', 'type': 'Numeric'}},
                {'id': 'Cint', 'fields': {'label': 'Cint', 'type': 'Int'}},
                {'id': 'Dbol', 'fields': {'label': 'Dbol', 'type': 'Bool'}},]
        tables = [{'id': 'T'+name, 'columns': cols}]
        gristapi = api.GristApi(config=TEST_CONFIGURATION)
        st, res = gristapi.add_tables(tables, cls.doc_id, cls.team_id)
        cls.table_id = res[0]
        total_apicalls.append(gristapi.apicalls)
    
    def test_list_records(self):
        records = [{'Astr': 'test 1', 'Bnum': 1.1, 'Cint': 1, 'Dbol': True},
                   {'Astr': 'test 2', 'Bnum': 2.2, 'Cint': 2, 'Dbol': False}, 
                   {'Astr': 'test 3', 'Bnum': 3.3, 'Cint': 3, 'Dbol': False},
                   {'Astr': 'test 4', 'Bnum': 4.4, 'Cint': 4, 'Dbol': True},]
        st, res = self.g.add_records(self.table_id, records, 
                                     doc_id=self.doc_id, team_id=self.team_id)
        self.assertIsInstance(res, list)
        self.assertEqual(len(res), 4)
        self.assertEqual(st, 200)
        st, res = self.g.list_records(self.table_id, 
                                      doc_id=self.doc_id, team_id=self.team_id)
        self.assertIsInstance(res, list)
        self.assertEqual(st, 200)
        st, res = self.g.list_records(self.table_id, sort='-Cint', limit=2, 
                                      doc_id=self.doc_id, team_id=self.team_id)
        self.assertIsInstance(res, list)
        self.assertEqual(st, 200)
    
    def test_list_records_with_filter(self):
        st, res = self.g.list_records(self.table_id, filter={'Astr': ['test 3']}, 
                                      doc_id=self.doc_id, team_id=self.team_id)
        self.assertIsInstance(res, list)
        self.assertEqual(st, 200)

    def test_add_and_update_records(self):
        records = [{'Astr': 'test1', 'Bnum': 1.1, 'Cint': 1, 'Dbol': True},
                   {'Astr': 'test2', 'Bnum': 2.2, 'Cint': 2, 'Dbol': False}]
        st, res = self.g.add_records(self.table_id, records, 
                                     doc_id=self.doc_id, team_id=self.team_id)
        self.assertIsInstance(res, list)
        self.assertEqual(st, 200)
        records = [{'id': 1, 'Astr': 'modified', 'Bnum': 1.12},
                   {         'Astr': 'mod!!', 'Bnum': 2.22, 'id': 2}]
        st, res = self.g.update_records(self.table_id, records, 
                                        doc_id=self.doc_id, team_id=self.team_id)
        self.assertIsNone(res)
        self.assertEqual(st, 200)
    
    @unittest.skip  # not really our fault, I guess
    def test_add_records_noparse(self):
        # the "noparse" param is not enforced?
        records = [{'Cint': 'not a number'}]
        st, res = self.g.add_records(self.table_id, records, noparse=False,
                                     doc_id=self.doc_id, team_id=self.team_id)
        self.assertIsInstance(res, list)
        self.assertEqual(st, 200)
        st, res = self.g.add_records(self.table_id, records, noparse=True,
                                     doc_id=self.doc_id, team_id=self.team_id)
        self.assertIsInstance(res, list)
        self.assertEqual(st, 200)

    def test_add_update_records(self):
        records = [{'Astr': 'toupdate1', 'Bnum': 5.1, 'Cint': 5, 'Dbol': True},
                   {'Astr': 'toupdate2', 'Bnum': 6.2, 'Cint': 6, 'Dbol': False}]
        st, res = self.g.add_records(self.table_id, records, 
                                     doc_id=self.doc_id, team_id=self.team_id)
        self.assertIsInstance(res, list)
        self.assertEqual(st, 200)
        records = [{'require': {'Astr': 'toupdate1'}, 'fields': {'Cint': 55}}, 
                   {'require': {'Astr': 'toupdate2'}, 'fields': {'Bnum': 6.3}},
                   {'require': {'Astr': 'new rec'}, 'fields': {'Dbol': True}}]
        st, res = self.g.add_update_records(self.table_id, 
                        records, doc_id=self.doc_id, team_id=self.team_id)
        self.assertIsNone(res)
        self.assertEqual(st, 200)

    def test_data_delete(self): # the only non-deprecated /data endpoint
        records = [{'Astr': 'test1', 'Bnum': 1.1, 'Cint': 1, 'Dbol': True},
                   {'Astr': 'test2', 'Bnum': 2.2, 'Cint': 2, 'Dbol': False}, 
                   {'Astr': 'test3', 'Bnum': 3.3, 'Cint': 3, 'Dbol': False}]
        st, res = self.g.add_records(self.table_id, records, 
                                     doc_id=self.doc_id, team_id=self.team_id)
        self.assertIsInstance(res, list)
        self.assertEqual(st, 200)
        st, res = self.g.delete_rows(self.table_id, [1, 2], doc_id=self.doc_id, 
                                     team_id=self.team_id)
        self.assertIsNone(res)
        self.assertEqual(st, 200)

    def test_sql_and_sql_with_params(self): 
        records = [{'Astr': 'test sql1', 'Bnum': 1.1, 'Cint': 1, 'Dbol': True},
                   {'Astr': 'test sql2', 'Bnum': 2.2, 'Cint': 2, 'Dbol': False}, 
                   {'Astr': 'test sql3', 'Bnum': 3.3, 'Cint': 3, 'Dbol': False}]
        st, res = self.g.add_records(self.table_id, records, 
                                     doc_id=self.doc_id, team_id=self.team_id)
        self.assertEqual(st, 200)
        sql = f'select * from {self.table_id}'  # no trailing ";" !
        st, res = self.g.run_sql(sql, doc_id=self.doc_id, team_id=self.team_id)
        self.assertIsInstance(res, list)
        self.assertEqual(st, 200)
        sql = f'select * from {self.table_id} where Cint>?'
        qargs = [1]
        st, res = self.g.run_sql_with_args(sql, qargs, doc_id=self.doc_id, 
                                           team_id=self.team_id)
        self.assertIsInstance(res, list)
        self.assertEqual(st, 200)

class TestConverters(BaseTestPyGrister): 
    # we test converters for "/records" and "/sql" endpoints here
    @classmethod
    def setUpClass(cls):
        cls.team_id = TEST_CONFIGURATION['GRIST_TEAM_SITE']
        ws_id, name = _make_ws(cls.team_id)
        cls.doc_id = _make_doc(ws_id)
        cols = [{'id': 'Test', 'fields': {'label': 'Test', 'type': 'Text'}},
                {'id': 'Sort', 'fields': {'label': 'Sort', 'type': 'Text'}},
                {'id': 'Bnum', 'fields': {'label': 'Bnum', 'type': 'Numeric'}},
                {'id': 'Cint', 'fields': {'label': 'Cint', 'type': 'Int'}},
                {'id': 'Dbol', 'fields': {'label': 'Dbol', 'type': 'Bool'}},
                {'id': 'Edate', 'fields': {'label': 'Edate', 'type': 'Date'}},]
        tables = [{'id': 'T'+name, 'columns': cols}]
        gristapi = api.GristApi(config=TEST_CONFIGURATION)
        st, res = gristapi.add_tables(tables, cls.doc_id, cls.team_id)
        cls.table_id = res[0]
        total_apicalls.append(gristapi.apicalls)

    def test_list_records(self):
        records = [{'Test': 'list_records', 'Sort': 'a', 
                    'Bnum': 1.1, 'Edate': 1602280800},
                   {'Test': 'list_records', 'Sort': 'b', 
                    'Bnum': 2, 'Edate': None}, 
                   {'Test': 'list_records', 'Sort': 'c', 
                    'Bnum': 'hello', 'Edate': 'hello'},]
        st, res = self.g.add_records(self.table_id, records, 
                                     doc_id=self.doc_id, team_id=self.team_id)
        self.assertEqual(st, 200)
        # first we try without converters...
        st, res = self.g.list_records(self.table_id, 
                                      filter={'Test': ['list_records']}, sort='Sort',
                                      doc_id=self.doc_id, team_id=self.team_id)
        self.assertEqual(st, 200)
        self.assertEqual(res[0]['Bnum'], 1.1)
        self.assertEqual(res[1]['Bnum'], 2)
        self.assertEqual(res[2]['Bnum'], 'hello')
        self.assertEqual(res[0]['Edate'], 1602280800)
        self.assertEqual(res[1]['Edate'], None)
        self.assertEqual(res[2]['Edate'], 'hello')
        # now let's try converters:
        conv = {self.table_id: 
                    {'Bnum': lambda i: float(i),
                     'Edate': lambda i: datetime.fromtimestamp(i),}  # (1)
                }
        self.g.out_converter = conv
        st, res = self.g.list_records(self.table_id, 
                                      filter={'Test': ['list_records']}, sort='Sort',
                                      doc_id=self.doc_id, team_id=self.team_id)
        self.assertEqual(st, 200)
        self.assertEqual(res[0]['Bnum'], 1.1)
        self.assertEqual(res[1]['Bnum'], 2.0)
        self.assertEqual(res[2]['Bnum'], 'hello')
        self.assertEqual(res[0]['Edate'], datetime(2020, 10, 10))
        self.assertEqual(res[1]['Edate'], None)
        self.assertEqual(res[2]['Edate'], 'hello')

        # (1) note: this works here, but it's very naive: write timezone-aware 
        # converters in your real code! The Grist Api will silently compensate 
        # for your document (local) timezone when inserting/retrieving dates, 
        # so what ends up stored in the database will be different from the naive 
        # date that you have passed to the Api. For instance, at the time of this 
        # writing my Grist document was set at UTC+2, so while I passed 
        # timestamp "1602280800", the number stored in the database was 
        # "1602201600" (2 hours earlier) and, when I checked with the Grist GUI, 
        # the date diplayed was indeed "2020-10-09" instead of "2020-10-10" 
        # as I intended. 
        # See https://support.getgrist.com/dates/#time-zones and 
        # https://xkcd.com/1883/

    def test_add_records(self):
        conv = {self.table_id: 
                    {'Bnum': lambda i: float(i),
                     'Edate': lambda i: int(datetime.timestamp(i)),}  # (1) above
                }
        self.g.in_converter = conv
        # we add records with a converter
        records = [{'Test': 'add_records', 'Sort': 'a', 
                    'Bnum': 1.1, 'Edate': datetime(2020, 10, 10)},
                   {'Test': 'add_records', 'Sort': 'b', 
                    'Bnum': '2', 'Edate': datetime(2020, 10, 10)},]
        st, res = self.g.add_records(self.table_id, records, 
                                     doc_id=self.doc_id, team_id=self.team_id)
        self.assertEqual(st, 200)
        # now we retrieve them without any "out" converter set
        st, res = self.g.list_records(self.table_id, 
                                      filter={'Test': ['add_records']}, sort='Sort',
                                      doc_id=self.doc_id, team_id=self.team_id)
        self.assertEqual(st, 200)
        self.assertEqual(res[0]['Bnum'], 1.1)
        self.assertEqual(res[1]['Bnum'], 2.0)
        self.assertEqual(res[1]['Edate'], 1602280800)

    def test_add_records_weak_converter(self):
        # note: Pygrister will fix Value/TypeErrors for you for "outgoing"
        # converters only (ie, when retrieving data), 
        # but NOT for "ingoing" converters (when uploading data)
        conv = {self.table_id: {'Bnum': lambda i: float(i)}}
        self.g.in_converter = conv
        # this is a "weak" converter that ignores possible errors
        with self.assertRaises(ValueError):
            st, res = self.g.add_records(self.table_id, [{'Bnum': 'hello'}], 
                                         doc_id=self.doc_id, team_id=self.team_id)
        with self.assertRaises(TypeError):
            st, res = self.g.add_records(self.table_id, [{'Bnum': None}], 
                                         doc_id=self.doc_id, team_id=self.team_id)

    def test_add_update_records(self):
        records = [{'Test': 'add_update', 'Sort': 'to_update_a', 'Bnum': 1.1},
                   {'Test': 'add_update', 'Sort': 'to_update_b', 'Bnum': 2}]
        st, res = self.g.add_records(self.table_id, records, 
                                     doc_id=self.doc_id, team_id=self.team_id)
        self.assertEqual(st, 200)
        # let's add a converter...
        conv = {self.table_id: 
                    {'Bnum': lambda i: float(i),
                     'Edate': lambda i: int(datetime.timestamp(i)),} 
                }
        self.g.in_converter = conv
        records = [{'require': {'Sort': 'to_update_a'}, 
                    'fields': {'Bnum': '5'}}, 
                   {'require': {'Sort': 'to_update_b'}, 
                    'fields': {'Edate': datetime(2020, 10, 10)}},]
        st, res = self.g.add_update_records(self.table_id, 
                        records, doc_id=self.doc_id, team_id=self.team_id)
        self.assertEqual(st, 200)
        # now let's retrieve the records without a converter
        st, res = self.g.list_records(self.table_id, 
                                      filter={'Test': ['add_update']}, sort='Sort',
                                      doc_id=self.doc_id, team_id=self.team_id)
        self.assertEqual(st, 200)
        self.assertEqual(res[0]['Bnum'], 5.0)
        self.assertEqual(res[1]['Edate'], 1602280800)

    def test_sql(self):
        records = [{'Test': 'test_sql', 'Sort': 'a', 
                    'Bnum': 1.1, 'Edate': 1602280800},
                   {'Test': 'test_sql', 'Sort': 'b', 
                    'Bnum': 2, 'Edate': None}, 
                   {'Test': 'test_sql', 'Sort': 'c', 
                    'Bnum': 'hello', 'Edate': 'hello'},]
        st, res = self.g.add_records(self.table_id, records, 
                                     doc_id=self.doc_id, team_id=self.team_id)
        self.assertEqual(st, 200)
        # now we add an "out" converter:
        conv = {'sql': 
                    {'Bnum': lambda i: float(i),
                     'Edate': lambda i: datetime.fromtimestamp(i),}
                }
        self.g.out_converter = conv
        sql = f'select * from {self.table_id} where Test=? order by Sort' 
        qargs = ['test_sql']
        st, res = self.g.run_sql_with_args(sql, qargs, doc_id=self.doc_id, 
                                           team_id=self.team_id)
        self.assertEqual(st, 200)
        self.assertEqual(res[0]['Bnum'], 1.1)
        self.assertEqual(res[1]['Bnum'], 2.0)
        self.assertEqual(res[2]['Bnum'], 'hello')
        self.assertEqual(res[0]['Edate'], datetime(2020, 10, 10))
        self.assertEqual(res[1]['Edate'], None)
        self.assertEqual(res[2]['Edate'], 'hello')

class TestTables(BaseTestPyGrister):
    @classmethod
    def setUpClass(cls):
        cls.team_id = TEST_CONFIGURATION['GRIST_TEAM_SITE']
        cls.ws_id, name = _make_ws(cls.team_id)
        cls.doc_id = _make_doc(cls.ws_id)

    def test_list_tables(self):
        st, res = self.g.list_tables(self.doc_id, self.team_id)
        self.assertIsInstance(res, list)
        self.assertEqual(st, 200)
    
    def test_add_tables(self):
        name = 'T'+str(time.time_ns())
        tables = [{'id': name, 'columns': 
                   [{'id': 'col1', 'fields': {'label': 'Col 1'}}]}]
        st, res = self.g.add_tables(tables, self.doc_id, self.team_id)
        self.assertIsInstance(res, list)
        self.assertEqual(st, 200)

    @unittest.expectedFailure
    def test_update_tables(self):
        name = 'T'+str(time.time_ns())
        tables = [{'id': name, 'columns': 
                   [{'id': 'col1', 'fields': {'label': 'Col 1'}}]}]
        st, res = self.g.add_tables(tables, self.doc_id, self.team_id)
        self.assertIsInstance(res, list)
        self.assertEqual(st, 200)
        tables = [{'id': name, 'columns': 
                   [{'id': 'col1', 'fields': {'label': 'Col 1bis'}}]}]
        # now, this *looks like* the same innocent payload as before, with 
        # only a minor edit... but this time, boom! the Grist api will go 
        # full http400 with a rather cryptic message like 
        # 'error': 'Invalid payload', 'details': 
        # {'userError': 'Error: body.tables[0] is not a RecordWithStringId; 
        #   body.tables[0].fields is missing'}
        # This will need a few more rounds of trial/error I'm afraid...
        st, res = self.g.update_tables(tables, self.doc_id, self.team_id)
        self.assertIsNone(res)
        self.assertEqual(st, 200)

class TestCols(BaseTestPyGrister):
    @classmethod
    def setUpClass(cls):
        cls.team_id = TEST_CONFIGURATION['GRIST_TEAM_SITE']
        ws_id, name = _make_ws(cls.team_id)
        cls.doc_id = _make_doc(ws_id)
        cls.table_id = 'Table1' # we trust this to be always present in new docs

    def test_list_cols(self):
        st, res = self.g.list_cols(self.table_id, doc_id=self.doc_id, 
                                   team_id=self.team_id)
        self.assertIsInstance(res, list)
        self.assertEqual(st, 200)
    
    def test_add_update_delete_cols(self):
        name = 'col'+str(time.time_ns())[-5:]
        cols = [{'id': name+'_a', 'fields': {'label': name+'_a'}},
                {'id': name+'_b', 'fields': {'label': name+'_b',
                                             'type': 'Int'}}]
        st, res = self.g.add_cols(self.table_id, cols=cols, 
                                  doc_id=self.doc_id, team_id=self.team_id)
        self.assertIsInstance(res, list)
        self.assertEqual(len(res), 2)
        self.assertEqual(st, 200)
        cols = [{'id': name+'_a', 'fields': {'label': name+'_newa'}},
                {'id': name+'_b', 'fields': {'label': name+'_newb'}}]
        st, res = self.g.update_cols(self.table_id, cols=cols, 
                                     doc_id=self.doc_id, team_id=self.team_id)
        self.assertIsNone(res)
        self.assertEqual(st, 200)
        st, res = self.g.delete_column(self.table_id, name+'_newa', 
                                       doc_id=self.doc_id, team_id=self.team_id)
        self.assertIsNone(res)
        self.assertEqual(st, 200)
    
    def test_add_cols_with_options(self):
        name = 'col'+str(time.time_ns())[-5:]
        # this is the example from the Grist api console
        cols = [{'id': name+'_opts', 
                 'fields': {
                    'label': name+'_opts',
                    'type': 'Choice', 
                    'widgetOptions': {
                        'choices': ['New', 'Old'],
                        'choiceOptions': {
                            'New': {
                                'fillColor': '#FF0000',
                                'textColor': '#FFFFFF'}}}}}]
        st, res = self.g.add_cols(self.table_id, cols=cols, 
                                  doc_id=self.doc_id, team_id=self.team_id)
        self.assertIsInstance(res, list)
        self.assertEqual(st, 200)

    def test_add_update_cols(self):
        name = 'col'+str(time.time_ns())[-5:]
        cols = [{'id': name+'_a', 'fields': {'label': name+'_a'}},
                {'id': name+'_b', 'fields': {'label': name+'_b',
                                             'type': 'Int'}}]
        st, res = self.g.add_cols(self.table_id, cols=cols, doc_id=self.doc_id, 
                                  team_id=self.team_id)
        self.assertIsInstance(res, list)
        self.assertEqual(st, 200)
        cols = [{'id': name+'_a', 'fields': {'label': name+'_newa'}}, # updated
                {'id': name+'_c', 'fields': {'label': name+'_c'}}]    # added
        st, res = self.g.add_update_cols(self.table_id, cols=cols, noadd=False, 
                                         noupdate=False, doc_id=self.doc_id, 
                                         team_id=self.team_id)
        self.assertIsNone(res)
        self.assertEqual(st, 200)

class TestAttachments(BaseTestPyGrister):
    @classmethod
    def setUpClass(cls):
        cls.team_id = TEST_CONFIGURATION['GRIST_TEAM_SITE']
        cls.ws_id, name = _make_ws(cls.team_id)
        cls.doc_id = _make_doc(cls.ws_id)

    def test_list_attachments(self):
        st, res = self.g.list_attachments(doc_id=self.doc_id, team_id=self.team_id)
        self.assertIsInstance(res, list)
        self.assertEqual(st, 200)
    
    def test_list_attachment_with_filter(self):
        filter = {'fileName': ['cat', 'dog']}
        st, res = self.g.list_attachments(filter=filter, doc_id=self.doc_id, 
                                          team_id=self.team_id)
        self.assertIsInstance(res, list)
        self.assertEqual(st, 200)

    def test_upload_download_attachments(self):
        f = HERE / 'imgtest.jpg'
        st, res = self.g.upload_attachments([f], doc_id=self.doc_id, 
                                            team_id=self.team_id)
        self.assertIsInstance(res, list)
        self.assertEqual(len(res), 1)
        self.assertEqual(st, 200)
        # upload multiple attachments
        st, res = self.g.upload_attachments([f, f, f], doc_id=self.doc_id, 
                                            team_id=self.team_id)
        self.assertIsInstance(res, list)
        self.assertEqual(len(res), 3)
        self.assertEqual(st, 200)
        name = Path(f'att_{time.time_ns()}.jpg')
        st, res = self.g.download_attachment(name, 1, doc_id=self.doc_id, 
                                             team_id=self.team_id)
        self.assertIsNone(res)
        self.assertEqual(st, 200)
    
    def test_download_restore_attachments(self):
        # this is for the download/upload "archive" apis
        f = HERE / 'imgtest.jpg'
        st, res = self.g.upload_attachments([f], doc_id=self.doc_id, 
                                            team_id=self.team_id)
        self.assertEqual(st, 200)
        name = Path(f'downloaded_atts_{time.time_ns()}.tar')
        st, res = self.g.download_attachments(name, doc_id=self.doc_id, 
                                              team_id=self.team_id)
        self.assertEqual(st, 200)
        self.assertIsNone(res)
        self.assertTrue(name.is_file())
        # now we re-upload the tar file
        st, res = self.g.upload_restore_attachments(name, doc_id=self.doc_id, 
                                                    team_id=self.team_id)
        self.assertEqual(st, 200)
        self.assertDictEqual(res, {'added': 0, 'errored': 0, 'unused': 1})
        # downloading should work even if no attachments are present
        doc_id = _make_doc(self.ws_id)
        st, res = self.g.download_attachments(doc_id=doc_id, 
                                              team_id=self.team_id)
        self.assertEqual(st, 200)

    def test_see_attachment(self):
        # make sure we have at least one attachment to see
        f = HERE / 'imgtest.jpg'
        st, res = self.g.upload_attachments([f], doc_id=self.doc_id, 
                                            team_id=self.team_id)
        self.assertIsInstance(res, list)
        self.assertEqual(st, 200)
        # note that id=1 could not be the one we just uploaded... 
        st, res = self.g.see_attachment(1, doc_id=self.doc_id, 
                                        team_id=self.team_id)
        self.assertIsInstance(res, dict)
        self.assertEqual(st, 200)

# to test external attachments, you must run a self-hosted instance of Grist 
# with "GRIST_EXTERNAL_ATTACHMENTS_MODE=snapshots", and a S3-compatible bucket 
@unittest.skipIf(TEST_CONFIGURATION['GRIST_TEST_RUN_EXT_ATTACH_TESTS'] == 'N', '')
class TestExternalAttachments(BaseTestPyGrister):
    @classmethod
    def setUpClass(cls):
        cls.team_id = TEST_CONFIGURATION['GRIST_TEAM_SITE']
        ws_id, name = _make_ws(cls.team_id)
        cls.doc_id = _make_doc(ws_id)

    def test_store(self):
        # this is for the various "store" apis (see, update, settings)
        st, res = self.g.see_attachment_store(doc_id=self.doc_id, 
                                              team_id=self.team_id)
        self.assertEqual(res, 'internal')
        st, res = self.g.update_attachment_store(internal_store=False, 
                            doc_id=self.doc_id, team_id=self.team_id)
        self.assertIsNone(res)
        st, res = self.g.see_attachment_store(doc_id=self.doc_id, 
                                              team_id=self.team_id)
        self.assertEqual(res, 'external')
        st, res = self.g.list_store_settings(doc_id=self.doc_id, 
                                             team_id=self.team_id)
        self.assertEqual(st, 200) # not really much to verify here... 

    def test_transfer(self):
        # this is for the transfering files apis, between external/internal store
        st, res = self.g.update_attachment_store(doc_id=self.doc_id, 
                                                 team_id=self.team_id)
        st, res = self.g.see_attachment_store(doc_id=self.doc_id, 
                                              team_id=self.team_id)
        self.assertEqual(res, 'internal')
        f = HERE / 'imgtest.jpg'
        st, res = self.g.upload_attachments([f, f, f], doc_id=self.doc_id, 
                                            team_id=self.team_id)
        st, res = self.g.update_attachment_store(internal_store=False, 
                            doc_id=self.doc_id, team_id=self.team_id)
        st, res = self.g.see_attachment_store(doc_id=self.doc_id, 
                                              team_id=self.team_id)
        self.assertEqual(res, 'external')
        # now we should have some attachments to transfer
        st, res = self.g.transfer_attachments(doc_id=self.doc_id, 
                                              team_id=self.team_id)
        self.assertTrue(res['status']['isRunning'])
        # "see_transfer_status" return depends on when we call it... 
        st, res = self.g.see_transfer_status(doc_id=self.doc_id, 
                                             team_id=self.team_id)
        self.assertEqual(st, 200) # little we can test


class TestWebhooks(BaseTestPyGrister):
    @classmethod
    def setUpClass(cls):
        cls.team_id = TEST_CONFIGURATION['GRIST_TEAM_SITE']
        ws_id, name = _make_ws(cls.team_id)
        cls.doc_id = _make_doc(ws_id)
        cls.table_id = 'Table1' # we trust this to be always present in new docs

    def test_list_webhooks(self):
        st, res = self.g.list_webhooks(doc_id=self.doc_id, team_id=self.team_id)
        self.assertIsInstance(res, list)
        self.assertEqual(st, 200)

    @unittest.skipIf(TEST_CONFIGURATION['GRIST_SELF_MANAGED'] == 'Y', '')
    def test_add_update_delete_webhooks(self):
        # with my basic self-managed setup, this will fail with an Http 403
        # it's problably just a matter of proper configuration of the container...
        name = 'wh'+str(time.time_ns())
        wh = {'fields': {'name': name, 'memo': 'memo!', 
              'url': 'https://www.example.com',
              'enabled': True, 'eventTypes': ['add'], 'isReadyColumn': None, 
              'tableId': 'Table1'}}
        st, res = self.g.add_webhooks(webhooks=[wh], doc_id=self.doc_id, 
                                      team_id=self.team_id)
        self.assertIsInstance(res, list)
        self.assertEqual(st, 200)
        wh_id = res[0]
        wh['fields']['memo'] = 'memo updated!'
        st, res = self.g.update_webhook(wh_id, wh, doc_id=self.doc_id, 
                                        team_id=self.team_id)
        self.assertIsNone(res)
        self.assertEqual(st, 200)
        st, res = self.g.delete_webhook(wh_id, doc_id=self.doc_id, 
                                        team_id=self.team_id)
        self.assertIsNone(res)
        self.assertEqual(st, 200)

    def test_empty_payloads_queue(self):
        st, res = self.g.empty_payloads_queue(doc_id=self.doc_id, 
                                              team_id=self.team_id)
        self.assertIsNone(res)
        self.assertEqual(st, 200)


if __name__ == '__main__':
    unittest.main()
