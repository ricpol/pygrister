# type: ignore
"""
This is the Pygrister test suite.
=================================

Before running the tests, you must set up a few things on the Grist side, 
then provide some env variables in your shell: 

- visit the Grist website and find out (or create) your API key;
- create an empty team site (that is, only the "Home" workspace should 
  be present): a free site will do;
- optionally, create a second empty team site;
- provide your api key as a ``GRIST_API_KEY`` env variable;
- set up a ``GRIST_TEAM_SITE`` env variable, with the name of your 
  team site in it (actually, it's the *url subdomain*: if you have 
  ``https://myteam.getgrist.com``, then it is ``myteam``).

Remember, the test suite *will not make use* of your regular configuration 
files (eg., ``~/.gristapi/config.json``): everything must be provided as 
environment variables. 

The test suite will leave several objects (workspaces and docs) in your 
team site. The objects created have unique names, so it should be safe 
re-running the test suite with the same sites: however, you may want 
to clean up eventually. 

A few object will also be downloaded in your current directory. Moreover, 
tests involving user/permission manipulation will trigger email notifications 
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

import os, os.path
import time
import unittest
from requests import HTTPError

from pygrister import api

# either provide the following 2 keys as env vars, 
# or de-comment these lines and fill in the values here:

# os.environ['GRIST_API_KEY'] = '<your api key here>'
# os.environ['GRIST_TEAM_SITE'] = '<your grist team ID here'

try:
    os.environ['GRIST_API_KEY']
except KeyError:
    raise AssertionError("Can't run tests: no GRIST_API_KEY env variable found.")
try:
    os.environ['GRIST_TEAM_SITE']
except KeyError:
    raise AssertionError("Can't run tests: no GRIST_TEAM_SITE env variable found.")

os.environ['GRIST_SERVER_PROTOCOL'] = 'https://'
os.environ['GRIST_API_SERVER'] = 'getgrist.com/api'
os.environ['GRIST_SAFEMODE'] = 'N'
os.environ['GRIST_RAISE_ERROR'] = 'Y'
# if we reach these two, something is wrong and we should fail
os.environ["GRIST_WORKSPACE_ID"] = "_bogus_default_ws_id_"
os.environ["GRIST_DOC_ID"] = "_bogus_default_doc_id_"

HERE = os.path.dirname(os.path.abspath(__file__))

total_apicalls = [] # behold, the hack of the mutable global!
def tearDownModule():
    print('\nTotal api calls:', sum(total_apicalls))


# two helper functions to prepare playground worspaces and documents
def _make_ws(team_id):
    gristapi = api.GristApi()
    name = 'ws'+str(time.time_ns())
    st, ws_id = gristapi.add_workspace(name, team_id)
    total_apicalls.append(gristapi.apicalls)
    return ws_id, name

def _make_doc(ws_id):
    gristapi = api.GristApi()
    name = 'doc'+str(time.time_ns())
    st, doc_id = gristapi.add_doc(name, ws_id=ws_id)
    total_apicalls.append(gristapi.apicalls)
    return doc_id


class BaseTestPyGrister(unittest.TestCase):
    def setUp(self):
        self.g = api.GristApi()
    
    def tearDown(self):
        total_apicalls.append(self.g.apicalls)


class TestVarious(BaseTestPyGrister):
    @classmethod
    def setUpClass(cls):
        cls.team_id = os.environ['GRIST_TEAM_SITE']

    def test_raise_error(self):
        with self.assertRaises(HTTPError):
            self.g.list_workspaces('_bogus_team_id_')
        self.g.reconfig({'GRIST_RAISE_ERROR': 'N'})
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


class TestTeamSites(BaseTestPyGrister):
    @classmethod
    def setUpClass(cls):
        cls.team_id = os.environ['GRIST_TEAM_SITE']
     
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
        self.g.reconfig({'GRIST_SAFEMODE': 'Y'})
        with self.assertRaises(api.GristApiInSafeMode):
            self.g.update_team('bogus', TestTeamSites.team_id)
        self.g.reconfig({'GRIST_SAFEMODE': 'N'})
        st, res = self.g.update_team('apitestrenamed', TestTeamSites.team_id)
        self.assertEqual(st, 200)
        st, res = self.g.update_team('apitestteam', TestTeamSites.team_id)
        self.assertEqual(st, 200)
        self.assertIsNone(res)

    def test_list_team_users(self):
        st, res = self.g.list_team_users(TestTeamSites.team_id)
        self.assertIsInstance(res, list)
        self.assertEqual(st, 200)

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
        cls.team_id = os.environ['GRIST_TEAM_SITE']
        gristapi = api.GristApi()
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
        self.g.reconfig({'GRIST_SAFEMODE': 'Y'})
        name = str(time.time_ns())
        with self.assertRaises(api.GristApiInSafeMode):
            self.g.add_workspace(name, self.team_id)
        self.g.reconfig({'GRIST_SAFEMODE': 'N'})
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
        self.g.reconfig({'GRIST_TEAM_SITE': 'docs'})
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
        cls.team_id = os.environ['GRIST_TEAM_SITE']
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
        self.g.reconfig({'GRIST_SAFEMODE': 'Y'})
        name = str(time.time_ns())
        with self.assertRaises(api.GristApiInSafeMode):
            self.g.add_doc(name, self.workspace_id)

    @unittest.expectedFailure
    def test_create_delete_doc_cross_site(self):
        # fun fact: cross-site doc creation is allowed...
        self.g.reconfig({'GRIST_TEAM_SITE': 'docs'})
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

    def test_list_doc_users(self):
        name = str(time.time_ns())
        st, doc_id = self.g.add_doc(name, ws_id=self.workspace_id)
        self.assertIsInstance(doc_id, str)
        self.assertEqual(st, 200)
        st, res = self.g.list_doc_users(doc_id, self.team_id)
        self.assertIsInstance(res, list)
        self.assertEqual(st, 200)

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
        st, res = self.g.download_sqlite(name+'.sqlite', 
            nohistory=True, template=True, doc_id=doc_id, team_id=self.team_id)
        self.assertIsNone(res)
        self.assertEqual(st, 200)

    def test_download_excel(self):
        name = str(time.time_ns())
        st, doc_id = self.g.add_doc(name, ws_id=self.workspace_id)
        self.assertIsInstance(doc_id, str)
        self.assertEqual(st, 200)
        st, res = self.g.download_excel(name+'.xls', table_id='Table1',
                                        doc_id=doc_id, team_id=self.team_id)
        self.assertIsNone(res)
        self.assertEqual(st, 200)
    
    def test_download_csv(self):
        name = str(time.time_ns())
        st, doc_id = self.g.add_doc(name, ws_id=self.workspace_id)
        self.assertIsInstance(doc_id, str)
        self.assertEqual(st, 200)
        st, res = self.g.download_csv(name+'.csv', table_id='Table1',
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
        st, res = self.g.download_schema('Table1', filename=name+'.json', 
                                         doc_id=doc_id, team_id=self.team_id)
        self.assertIsNone(res)
        self.assertEqual(st, 200)


class TestRecordAccess(BaseTestPyGrister): 
    # we test "/records", "/data" and "/sql" endpoints here
    @classmethod
    def setUpClass(cls):
        cls.team_id = os.environ['GRIST_TEAM_SITE']
        ws_id, name = _make_ws(cls.team_id)
        cls.doc_id = _make_doc(ws_id)
        cols = [{'id': 'Astr', 'fields': {'label': 'Astr', 'type': 'Text'}},
                {'id': 'Bnum', 'fields': {'label': 'Bnum', 'type': 'Numeric'}},
                {'id': 'Cint', 'fields': {'label': 'Cint', 'type': 'Int'}},
                {'id': 'Dbol', 'fields': {'label': 'Dbol', 'type': 'Bool'}},]
        tables = [{'id': 'T'+name, 'columns': cols}]
        gristapi = api.GristApi()
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


class TestTables(BaseTestPyGrister):
    @classmethod
    def setUpClass(cls):
        cls.team_id = os.environ['GRIST_TEAM_SITE']
        ws_id, name = _make_ws(cls.team_id)
        cls.doc_id = _make_doc(ws_id)

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
        # now, it *looks like* the same innocent payload as before, with 
        # only a minor edit... but this time, boom! the Grist api will go 
        # full http400 with a cryptic message like 
        # 'error': 'Invalid payload', 'details': 
        # {'userError': 'Error: body.tables[0] is not a RecordWithStringId; 
        #   body.tables[0].fields is missing'}
        # This will need a few more rounds of trial/error I'm afraid...
        # of course none of this is actually documented
        st, res = self.g.update_tables(tables, self.doc_id, self.team_id)
        self.assertIsNone(res)
        self.assertEqual(st, 200)


class TestCols(BaseTestPyGrister):
    @classmethod
    def setUpClass(cls):
        cls.team_id = os.environ['GRIST_TEAM_SITE']
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
        cls.team_id = os.environ['GRIST_TEAM_SITE']
        ws_id, name = _make_ws(cls.team_id)
        cls.doc_id = _make_doc(ws_id)

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
        f = os.path.join(HERE, 'imgtest.jpg')
        st, res = self.g.upload_attachment(f, doc_id=self.doc_id, 
                                           team_id=self.team_id)
        self.assertIsInstance(res, list)
        self.assertEqual(st, 200)
        name = 'att_'+str(time.time_ns())+'.jpg'
        st, res = self.g.download_attachment(name, 1, doc_id=self.doc_id, 
                                             team_id=self.team_id)
        self.assertIsNone(res)
        self.assertEqual(st, 200)

    def test_see_attachment(self):
        # make sure we have at least one attachment to see
        f = os.path.join(HERE, 'imgtest.jpg')
        st, res = self.g.upload_attachment(f, doc_id=self.doc_id, 
                                           team_id=self.team_id)
        self.assertIsInstance(res, list)
        self.assertEqual(st, 200)
        # maybe id=1 is not the one we just uploaded... 
        st, res = self.g.see_attachment(1, doc_id=self.doc_id, 
                                        team_id=self.team_id)
        self.assertIsInstance(res, dict)
        self.assertEqual(st, 200)


class TestWebhooks(BaseTestPyGrister):
    @classmethod
    def setUpClass(cls):
        cls.team_id = os.environ['GRIST_TEAM_SITE']
        ws_id, name = _make_ws(cls.team_id)
        cls.doc_id = _make_doc(ws_id)
        cls.table_id = 'Table1' # we trust this to be always present in new docs

    def test_list_webhooks(self):
        st, res = self.g.list_webhooks(doc_id=self.doc_id, team_id=self.team_id)
        self.assertIsInstance(res, list)
        self.assertEqual(st, 200)

    def test_add_update_delete_webhooks(self):
        name = 'wh'+str(time.time_ns())
        wh = {'fields': {'name': name, 'memo': 'memo!', 'url': 'https://example.com/',
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
