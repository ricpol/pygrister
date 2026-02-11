"""
This is the Gry test suite.
===========================

Gry is a command line tool powered by Pygrister. Please refer to the ``test.py`` 
docstring for more info about the testing environment. 

In particular, Gry tests will use the same ``config_test.json`` configuration 
file used by Pygrister tests, meaning that both test suites will be run 
against the same instance of Grist (if you don't want this, run the tests 
separately, changing configuration in between).

Gry testing is very basic at the moment: we just verify that the command 
"works", ie. manages to post a call to the Grist Api, without considering 
the result. Mostly, we just check the exit code of the command to find out 
the outcome. In Gry, 
- 0 means that everything went well, 
- 1 means that a Gry (Python) error occurred, but of course this would be 
  a bug and we never plan for it!, 
- 2 means that the command was ill-formed, but this is Typer domain, so 
  we don't test for this,
- 3 means that the Grist API returned a bad Http code (which is still 
  fine from our point of view).
"""

import os
import time
import json
import unittest
from pathlib import Path
from typer.testing import CliRunner

from pygrister.api import GristApi

# standard config values used by cli tests
default_config = {
    "GRIST_SERVER_PROTOCOL": "https://",
    "GRIST_API_SERVER": "getgrist.com",
    "GRIST_API_ROOT": "api",
    "GRIST_RAISE_ERROR": "N",
    "GRIST_SAFEMODE": "N",
    "GRIST_WORKSPACE_ID": "0", # for now...
    "GRIST_DOC_ID": "_bogus_", # for now...
}
# now we factor in user's config_test.json
HERE = Path(__file__).absolute().parent
with open(HERE / 'config_test.json') as f:
    test_config = json.loads(f.read())
default_config.update(test_config)
# let's create a ws and a doc with pygrister first
g = GristApi(default_config)
now = str(time.time_ns())
st, ws_id = g.add_workspace('ws'+now)
assert st == 200, "Can't create test workspace"
st, doc_id = g.add_doc('doc'+now, ws_id=ws_id)
assert st == 200, "Can't create test document"
# and update config accordingly
default_config["GRIST_WORKSPACE_ID"] = str(ws_id)
default_config["GRIST_DOC_ID"] = doc_id
# since we can't directly instantiate the custom GristApi used by Gry, 
# we set configuration as env variables, which Gry will pick up at startup...
for k, v in default_config.items():
    os.environ[k] = v 
# ...and only now we can safely import the cli module
from pygrister.cli import app
# TODO this is ackward and maybe there's a better way. The rug here is that 
# in pygrister.cli the GristApi instance is created *at import time*, and 
# everything works well since we must re-load at every Gry command anyway. 
# In testing, however, we only import once... 

class BaseTestCli(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()

class TestBasicOptions(BaseTestCli):
    def test_verbosity(self):
        res = self.runner.invoke(app, ['team', 'see'])
        self.assertEqual(res.exit_code, 0)
        self.assertIn('key', res.output) # the formatted column header we use
        res = self.runner.invoke(app, ['team', 'see', '-v'])
        self.assertEqual(res.exit_code, 0)
        self.assertIn('billingAccount', res.output) 
        res = self.runner.invoke(app, ['team', 'see', '-vv'])
        self.assertEqual(res.exit_code, 0)
        # TODO self.assertNotIn('\n', res.output[:-1]) # should be a one-liner
    
    def test_quiet(self):
        res = self.runner.invoke(app, ['team', 'see', '-q'])
        self.assertEqual(res.exit_code, 0)
        self.assertEqual('', res.output)
        res = self.runner.invoke(app, ['team', 'see', '-qvi'])
        self.assertEqual(res.exit_code, 0)
        self.assertEqual('', res.output)
    
    def test_inspect(self):
        res = self.runner.invoke(app, ['team', 'see', '-i'])
        self.assertEqual(res.exit_code, 0)
        self.assertIn('GRIST_API_KEY', res.output)
    
    def _test_conf(self):
        #TODO this is beyond me, but including this simple test will make 
        # ALL tests fail, just like that... no time for this nonsense now. 
        res = self.runner.invoke(app, ['conf'])
        self.assertEqual(res.exit_code, 0)
        self.assertIn('GRIST_API_KEY', res.output)

@unittest.skipIf(os.environ['GRIST_TEST_RUN_SERV_ACCOUNT_TESTS'] == 'N', '')
class TestServiceAccount(BaseTestCli):
    def test_list(self):
        res = self.runner.invoke(app, ['sacc', 'list'])
        self.assertEqual(res.exit_code, 0)

    def test_see(self):
        res = self.runner.invoke(app, ['sacc', 'see', '1000000000'])
        self.assertEqual(res.exit_code, 3)
    
    def test_new(self):
        res = self.runner.invoke(app, ['sacc', 'new', '2050-01-01'])
        self.assertEqual(res.exit_code, 0)
        res = self.runner.invoke(app, ['sacc', 'new', 'bogus'])
        self.assertEqual(res.exit_code, 3)
    
    def test_update(self):
        res = self.runner.invoke(app, ['sacc', 'update', '10000000000'])
        self.assertEqual(res.exit_code, 3)
    
    def test_delete(self):
        res = self.runner.invoke(app, ['sacc', 'delete', '10000000000'])
        self.assertEqual(res.exit_code, 3)
    
    def test_new_key(self):
        res = self.runner.invoke(app, ['sacc', 'new-key', '10000000000'])
        self.assertEqual(res.exit_code, 3)
    
    def test_delete_key(self):
        res = self.runner.invoke(app, ['sacc', 'delete-key', '10000000000'])
        self.assertEqual(res.exit_code, 3)

@unittest.skipIf(os.environ['GRIST_SELF_MANAGED'] == 'N', '')
@unittest.skipIf(os.environ['GRIST_TEST_RUN_SCIM_TESTS'] == 'N', '')
class TestUser(BaseTestCli):
    def test_list(self):
        res = self.runner.invoke(app, ['user', 'list'])
        self.assertEqual(res.exit_code, 0)
    
    def test_me(self):
        res = self.runner.invoke(app, ['user', 'me'])
        self.assertEqual(res.exit_code, 0)

    def test_see(self):
        res = self.runner.invoke(app, ['user', 'see', '5']) # usually 5 is "me"
        self.assertEqual(res.exit_code, 0)

    @unittest.skipIf(os.environ['GRIST_TEST_RUN_USER_TESTS'] == 'N', '')
    def test_new(self):
        now = str(time.time_ns())
        user = f'grytestuser_{now}'
        email = f'{now}@test.com'
        res = self.runner.invoke(app, ['user', 'new', user, email])
        self.assertEqual(res.exit_code, 0)

    def test_update(self):
        res = self.runner.invoke(app, ['user', 'update', '10000000000', 
                                       'locale', 'es'])
        self.assertEqual(res.exit_code, 3)

    def test_delete(self):
        res = self.runner.invoke(app, ['user', 'delete', '10000000000'])
        self.assertEqual(res.exit_code, 3)

    def test_enable(self):
        res = self.runner.invoke(app, ['user', 'enable', '666666666666666'])
        self.assertEqual(res.exit_code, 3)

class TestTeams(BaseTestCli):
    def test_list_team(self):
        res = self.runner.invoke(app, ['team', 'list'])
        self.assertEqual(res.exit_code, 0)

    def test_see_team(self):
        res = self.runner.invoke(app, ['team', 'see'])
        self.assertEqual(res.exit_code, 0)
        res = self.runner.invoke(app, ['team', 'see', '-t', 'bogus_team'])
        self.assertEqual(res.exit_code, 3)

    def test_usage_team(self):
        res = self.runner.invoke(app, ['team', 'usage'])
        self.assertEqual(res.exit_code, 0)
        res = self.runner.invoke(app, ['team', 'usage', '-t', 'bogus_team'])
        self.assertEqual(res.exit_code, 3)

    def test_update_team(self):
        res = self.runner.invoke(app, ['team', 'update', 'newname', 
                                       '-t', 'bogus_team'])
        self.assertEqual(res.exit_code, 3)

    def test_delete_team(self):
        res = self.runner.invoke(app, ['team', 'delete', '-t', 'bogus_team'])
        self.assertEqual(res.exit_code, 3)

    def test_users_team(self):
        res = self.runner.invoke(app, ['team', 'users'])
        self.assertEqual(res.exit_code, 0)
    
    def test_useraccess_team(self):
        res = self.runner.invoke(app, ['team', 'user-access', 
                                       '5', # should be the "me" user
                                       '-a', 'bogus_access'])
        self.assertEqual(res.exit_code, 2) # Typer should fail
        res = self.runner.invoke(app, ['team', 'user-access', '5', 
                                       '-t', 'bogus_team', '-a', 'editors'])
        self.assertEqual(res.exit_code, 3) # Grist should fail
    
class TestWorkspaces(BaseTestCli):
    def test_list_ws(self):
        res = self.runner.invoke(app, ['ws', 'list'])
        self.assertEqual(res.exit_code, 0)
    
    def test_see_ws(self):
        res = self.runner.invoke(app, ['ws', 'see'])
        self.assertEqual(res.exit_code, 0)
    
    def test_new_ws(self):
        res = self.runner.invoke(app, ['ws', 'new', 'myws', '-t', 'bogus_team'])
        self.assertEqual(res.exit_code, 3)
    
    def test_update_ws(self):
        res = self.runner.invoke(app, ['ws', 'update', 'newname'])
        self.assertEqual(res.exit_code, 0)
        res = self.runner.invoke(app, ['ws', 'update', 'myws', '-w', '10000000'])
        self.assertEqual(res.exit_code, 3)

    def test_delete_ws(self):
        res = self.runner.invoke(app, ['ws', 'delete', '-w', '10000000'])
        self.assertEqual(res.exit_code, 3)

    def test_trash(self):
        res = self.runner.invoke(app, ['ws', 'trash', '-w', '10000000'])
        self.assertEqual(res.exit_code, 3)

    def test_users_ws(self):
        res = self.runner.invoke(app, ['ws', 'users'])
        self.assertEqual(res.exit_code, 0)
    
    def test_useracces_ws(self):
        res = self.runner.invoke(app, ['ws', 'user-access', 
                                       '5', # should be the "me" user
                                       '-a', 'bogus_access'])
        self.assertEqual(res.exit_code, 2) # Typer should fail
        #TODO this won't work in SaaS Grist bc there's no user #5...
        #res = self.runner.invoke(app, ['ws', 'user-access', '5', 
        #                               '-a', 'editors', '-w', '0'])
        #self.assertEqual(res.exit_code, 3) # Grist should fail

class TestDoc(BaseTestCli):
    def test_doc_see(self):
        res = self.runner.invoke(app, ['doc', 'see'])
        self.assertEqual(res.exit_code, 0)
    
    def test_doc_new(self):
        res = self.runner.invoke(app, ['doc', 'new', 'newname', 
                                       '-w', '100000000'])
        self.assertEqual(res.exit_code, 3)
    
    def test_update_doc(self):
        res = self.runner.invoke(app, ['doc', 'update', 'newname', 
                                       '-d', 'bogus_doc'])
        self.assertEqual(res.exit_code, 3)
    
    def test_move_doc(self):
        res = self.runner.invoke(app, ['doc', 'move', '10000000'])
        self.assertEqual(res.exit_code, 3)

    def test_copy_doc(self):
        res = self.runner.invoke(app, ['doc', 'copy', '10000000', 'bogus'])
        self.assertEqual(res.exit_code, 3)

    def test_delete_doc(self):
        res = self.runner.invoke(app, ['doc', 'delete', '-d', 'bogus_doc'])
        self.assertEqual(res.exit_code, 3)
    
    def test_purge_history_doc(self):
        res = self.runner.invoke(app, ['doc', 'purge-history'])
        self.assertEqual(res.exit_code, 0)
    
    def test_reload_doc(self):
        res = self.runner.invoke(app, ['doc', 'reload'])
        self.assertEqual(res.exit_code, 0)
    
    def test_enable_doc(self):
        res = self.runner.invoke(app, ['doc', 'enable', '--disable'])
        self.assertEqual(res.exit_code, 0)
        res = self.runner.invoke(app, ['doc', 'enable'])
        self.assertEqual(res.exit_code, 0)
    
    def test_recovery_doc(self):
        res = self.runner.invoke(app, ['doc', 'recovery', '-d', 'bogus_doc'])
        self.assertEqual(res.exit_code, 3)

    def test_download_doc(self):
        res = self.runner.invoke(app, ['doc', 'download', 'fname', 
                                       '-d', 'bogus_doc'])
        self.assertEqual(res.exit_code, 3)
    
    def test_upload_doc(self):
        # we skip this for now as it involves creating at least a stub file.
        pass
    
    def test_users_doc(self):
        res = self.runner.invoke(app, ['doc', 'users'])
        self.assertEqual(res.exit_code, 0)
    
    def test_useraccess_doc(self):
        res = self.runner.invoke(app, ['doc', 'user-access', '5',
                                       '-a', 'editors', '-d', 'bogus_doc'])
        self.assertEqual(res.exit_code, 3)

class TestTable(BaseTestCli):
    def test_list_table(self):
        res = self.runner.invoke(app, ['table', 'list'])
        self.assertEqual(res.exit_code, 0)
    
    def test_new_table(self):
        res = self.runner.invoke(app, ['table', 'new', 'a:Text:a', 
                                       '-b', 'tname', '-d', 'bogus_doc'])
        self.assertEqual(res.exit_code, 3)
    
    def test_update_table(self):
        res = self.runner.invoke(app, ['table', 'update', '-b', 'bogus_table'])
        self.assertEqual(res.exit_code, 3)
    
    def test_download_table(self):
        res = self.runner.invoke(app, ['table', 'download', 'fname', 
                                       '-b', 'bogus_table'])
        self.assertEqual(res.exit_code, 3)

class TestCol(BaseTestCli):
    def test_list_col(self):
        res = self.runner.invoke(app, ['col', 'list', '-b', 'Table1'])
        self.assertEqual(res.exit_code, 0)
    
    def test_new_col(self):
        res = self.runner.invoke(app, ['col', 'new', 'name:Text:Name', 
                                       '-b', 'bogus_table'])
        self.assertEqual(res.exit_code, 3)
    
    def test_update_col(self):
        res = self.runner.invoke(app, ['col', 'update', 'name:Text:Name', 
                                       '-b', 'bogus_table'])
        self.assertEqual(res.exit_code, 3)
    
    def test_delete_col(self):
        res = self.runner.invoke(app, ['col', 'delete', 'bogus_col', 
                                       '-b', 'bogus_table'])
        self.assertEqual(res.exit_code, 3)

class TestRec(BaseTestCli):
    def test_list_rec(self):
        res = self.runner.invoke(app, ['rec', 'list', '-b', 'Table1'])
        self.assertEqual(res.exit_code, 0)
    
    def test_new_rec(self):
        res = self.runner.invoke(app, ['rec', 'new', 'a:b', '-b', 'bogus'])
        self.assertEqual(res.exit_code, 3)
    
    def test_update_rec(self):
        res = self.runner.invoke(app, ['rec', 'update', 'id:1', 'a:b', 
                                       '-b', 'bogus'])
        self.assertEqual(res.exit_code, 3)
    
    def test_delete_rec(self):
        res = self.runner.invoke(app, ['rec', 'delete', '1', '-b', 'bogus'])
        self.assertEqual(res.exit_code, 3)

class TestAtt(BaseTestCli): pass

class TestHook(BaseTestCli):
    def test_list_hook(self):
        res = self.runner.invoke(app, ['hook', 'list'])
        self.assertEqual(res.exit_code, 0)
    
    def test_new_hook(self):
        res = self.runner.invoke(app, ['hook', 'new', 'hname', 'hurl',
                                       '-b', 'bogus_table'])
        self.assertEqual(res.exit_code, 3)
    
    def test_update_hook(self):
        res = self.runner.invoke(app, ['hook', 'update', 'bogus_hook'])
        self.assertEqual(res.exit_code, 3)
    
    def test_delete_hook(self):
        res = self.runner.invoke(app, ['hook', 'delete', 'bogus_hook'])
        self.assertEqual(res.exit_code, 3)
    
    def test_emptyqueue_hook(self):
        res = self.runner.invoke(app, ['hook', 'empty-queue'])
        self.assertEqual(res.exit_code, 0)

@unittest.skipIf(os.environ['GRIST_TEST_RUN_SCIM_TESTS'] == 'N', '')
class TestScim(BaseTestCli):
    def test_schemas(self):
        res = self.runner.invoke(app, ['scim', 'schemas'])
        self.assertEqual(res.exit_code, 0)

    def test_config(self):
        res = self.runner.invoke(app, ['scim', 'config'])
        self.assertEqual(res.exit_code, 0)

    def test_resources(self):
        res = self.runner.invoke(app, ['scim', 'resources'])
        self.assertEqual(res.exit_code, 0)

class TestSql(BaseTestCli):
    def test_sql(self):
        res = self.runner.invoke(app, ['sql', 'select * from Table1'])
        self.assertEqual(res.exit_code, 0)


if __name__ == '__main__':
    unittest.main()
