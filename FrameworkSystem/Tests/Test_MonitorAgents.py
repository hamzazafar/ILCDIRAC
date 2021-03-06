""" Test MonitorAgents """

import unittest
from datetime import datetime, timedelta
from mock import MagicMock, call, patch
import psutil

import ILCDIRAC.FrameworkSystem.Agent.MonitorAgents as MAA
from ILCDIRAC.FrameworkSystem.Agent.MonitorAgents import MonitorAgents
from ILCDIRAC.Tests.Utilities.Mocks import rpcMock

from DIRAC import S_OK, S_ERROR
from DIRAC import gLogger
import DIRAC

__RCSID__ = "$Id$"


class TestMonitorAgents(unittest.TestCase):
  """ TestMonitorAgents class """

  def setUp(self):
    self.agent = MAA
    self.agent.AgentModule = MagicMock()
    self.agent.NotificationClient = MagicMock(spec=DIRAC.FrameworkSystem.Client.NotificationClient.NotificationClient)

    self.restartAgent = MonitorAgents()
    self.restartAgent.log = gLogger
    self.restartAgent.sysAdminClient = MagicMock()
    self.restartAgent.enabled = True
    self.restartAgent.restartAgents = True

  def tearDown(self):
    pass

  @staticmethod
  def getPSMock():
    psMock = MagicMock(name="psutil")
    procMock2 = MagicMock(name="process2kill")
    psMock.wait_procs.return_value = ("gone", [procMock2])
    procMock = MagicMock(name="process")
    procMock.children.return_value = []
    psMock.Process.return_value = procMock
    return psMock

  def test_init(self):
    self.assertIsInstance(self.restartAgent, MonitorAgents)
    self.assertIsInstance(self.restartAgent.nClient, MagicMock)
    self.assertIsInstance(self.restartAgent.sysAdminClient, MagicMock)
    self.assertTrue(self.restartAgent.enabled)
    self.assertEquals(self.restartAgent.addressFrom, "ilcdirac-admin@cern.ch")

  def test_begin_execution(self):
    """ test for beginExecution function """
    self.restartAgent.accounting["Junk"]["Funk"] = 1
    self.restartAgent.am_getOption = MagicMock()
    getOptionCalls = [call('Setup', self.restartAgent.setup),
                      call('EnableFlag', True),
                      call('MailTo', self.restartAgent.addressTo),
                      call('MailFrom', self.restartAgent.addressFrom)]

    self.restartAgent.getRunningInstances = MagicMock(return_value=S_OK())
    self.restartAgent.beginExecution()
    self.restartAgent.am_getOption.assert_has_calls(getOptionCalls, any_order=True)
    self.restartAgent.getRunningInstances.assert_called()

    # accounting dictionary should be cleared
    self.assertEquals(self.restartAgent.accounting, {})

  def test_send_notification(self):
    """ test for sendNotification function """
    self.restartAgent.errors = []
    self.restartAgent.accounting = {}

    # send mail should not be called if there are no errors and accounting information
    self.restartAgent.sendNotification()
    self.restartAgent.nClient.sendMail.assert_not_called()

    # send mail should be called if there are errors but no accounting information
    self.restartAgent.errors = ["some error"]
    self.restartAgent.sendNotification()
    self.restartAgent.nClient.sendMail.assert_called()

    # send email should be called if there is accounting information but no errors
    self.restartAgent.nClient.sendMail.reset_mock()
    self.restartAgent.errors = []
    self.restartAgent.accounting = {"Agent1": {"LogAge": 123, "Treatment": "Agent Restarted"}}
    self.restartAgent.sendNotification()
    self.restartAgent.nClient.sendMail.assert_called()

    # try sending email to all addresses even if we get error for sending email to some address
    self.restartAgent.nClient.sendMail.reset_mock()
    self.restartAgent.errors = ["some error"]
    self.restartAgent.addressTo = ["name1@cern.ch", "name2@cern.ch"]
    self.restartAgent.nClient.sendMail.return_value = S_ERROR()
    self.restartAgent.sendNotification()
    self.assertEquals(len(self.restartAgent.nClient.sendMail.mock_calls),
                      len(self.restartAgent.addressTo))

    # accounting dict and errors list should be cleared after notification is sent
    self.assertEquals(self.restartAgent.accounting, {})
    self.assertEquals(self.restartAgent.errors, [])

  def test_get_running_instances(self):
    """ test for getRunningInstances function """
    self.restartAgent.sysAdminClient.getOverallStatus = MagicMock()
    self.restartAgent.sysAdminClient.getOverallStatus.return_value = S_ERROR()

    res = self.restartAgent.getRunningInstances(instanceType='Agents')
    self.assertFalse(res["OK"])

    agents = {'Agents': {'DataManagement': {'FTS3Agent': {'MEM': '0.3', 'Setup': True, 'PID': '18128',
                                                          'RunitStatus': 'Run', 'Module': 'CleanFTSDBAgent',
                                                          'Installed': True, 'VSZ': '375576', 'Timeup': '29841',
                                                          'CPU': '0.0', 'RSS': '55452'}},
                         'Framework': {'ErrorMessageMonitor': {'MEM': '0.3', 'Setup': True, 'PID': '2303',
                                                               'RunitStatus': 'Run', 'Module': 'ErrorMessageMonitor',
                                                               'Installed': True, 'VSZ': '380392', 'Timeup': '3380292',
                                                               'CPU': '0.0', 'RSS': '56172'}}}}
    agents['Agents']['DataManagement']['FTSAgent'] = {'Setup': False, 'PID': 0, 'RunitStatus': 'Unknown',
                                                      'Module': 'FTSAgent', 'Installed': False, 'Timeup': 0}

    self.restartAgent.sysAdminClient.getOverallStatus.return_value = S_OK(agents)
    res = self.restartAgent.getRunningInstances(instanceType='Agents')

    # only insalled agents with RunitStatus RUN should be returned
    self.assertTrue('FTSAgent' not in res["Value"])
    self.assertTrue('FTS3Agent' in res["Value"])
    self.assertTrue('ErrorMessageMonitor' in res["Value"])
    for agent in res["Value"]:
      self.assertTrue('PollingTime' in res["Value"][agent])
      self.assertTrue('LogFileLocation' in res["Value"][agent])
      self.assertTrue('PID' in res["Value"][agent])

  def test_execute(self):
    """ test for execute function """
    self.restartAgent.sendNotification = MagicMock()

    agentOne = 'FTS3Agent'
    agentTwo = 'FTSAgent'
    agentOnePollingTime = 100
    agentTwoPollingTime = 200
    agentOneLogLoc = '/fake/loc1'
    agentTwoLogLoc = '/fake/loc2'
    agentOnePID = '12345'
    agentTwoPID = '54321'

    self.restartAgent.agents = {agentOne: {'PollingTime': agentOnePollingTime,
                                           'LogFileLocation': agentOneLogLoc,
                                           'PID': agentOnePID},
                                agentTwo: {'PollingTime': agentTwoPollingTime,
                                           'LogFileLocation': agentTwoLogLoc,
                                           'PID': agentTwoPID}}

    self.restartAgent.checkAgent = MagicMock(side_effect=[S_OK(), S_ERROR()])

    res = self.restartAgent.execute()
    self.assertFalse(res["OK"])
    calls = [call(agentOne, agentOnePollingTime, agentOneLogLoc, agentOnePID),
             call(agentTwo, agentTwoPollingTime, agentTwoLogLoc, agentTwoPID)]

    self.restartAgent.checkAgent.assert_has_calls(calls, any_order=True)

    # email notification should be sent at the end of every agent cycle
    self.restartAgent.sendNotification.assert_called()

  def test_check_agent(self):
    """ test for checkAgent function """
    self.restartAgent.getLastAccessTime = MagicMock()
    self.restartAgent.restartInstance = MagicMock(return_value=S_OK())

    agentName = 'agentX'
    pollingTime = MAA.HOUR
    currentLogLocation = '/fake/log/file'
    pid = '12345'

    self.restartAgent.getLastAccessTime.return_value = S_ERROR()
    res = self.restartAgent.checkAgent(agentName, pollingTime, currentLogLocation, pid)
    self.assertFalse(res["OK"])

    # agents with log file age less than max(pollingTime+Hour, 2 Hour) should not be restarted
    logAge = timedelta(hours=1)
    self.restartAgent.getLastAccessTime.return_value = S_OK(logAge)
    res = self.restartAgent.checkAgent(agentName, pollingTime, currentLogLocation, pid)
    self.assertTrue(res["OK"])
    self.restartAgent.restartInstance.assert_not_called()

    # agents with log file age of more than max(pollingTime+Hour, 2 Hour) should be restarted
    logAge = timedelta(hours=3)
    self.restartAgent.restartAgents = False
    self.restartAgent.getLastAccessTime.return_value = S_OK(logAge)
    res = self.restartAgent.checkAgent(agentName, pollingTime, currentLogLocation, pid)
    self.assertTrue(res["OK"])
    self.restartAgent.restartInstance.assert_called_once_with(int(pid), agentName, False)

  def test_check_executors(self):
    """Test the checkExecutor function."""
    self.restartAgent.getLastAccessTime = MagicMock()
    self.restartAgent.restartInstance = MagicMock(return_value=S_OK())
    self.restartAgent.checkForCheckingJobs = MagicMock()
    self.restartAgent.restartExecutors = True

    agentName = 'executorX'
    currentLogLocation = '/fake/log/file'
    pid = '12345'
    options = dict(PID=pid, LogFileLocation=currentLogLocation)
    self.restartAgent.getLastAccessTime.return_value = S_ERROR()
    res = self.restartAgent.checkExecutor(agentName, options)
    self.assertFalse(res["OK"])

    # log file ok
    logAge = timedelta(hours=1)
    self.restartAgent.getLastAccessTime.return_value = S_OK(logAge)
    res = self.restartAgent.checkExecutor(agentName, options)
    self.assertTrue(res["OK"])
    self.restartAgent.restartInstance.assert_not_called()

    # log file too old, no checking jobs
    logAge = timedelta(hours=3)
    self.restartAgent.getLastAccessTime.return_value = S_OK(logAge)
    self.restartAgent.checkForCheckingJobs.return_value = S_OK('NO_CHECKING_JOBS')
    res = self.restartAgent.checkExecutor(agentName, options)
    self.assertTrue(res["OK"])
    self.restartAgent.restartInstance.assert_not_called()

    # log file too old, checking jobs failed
    logAge = timedelta(hours=3)
    self.restartAgent.getLastAccessTime.return_value = S_OK(logAge)
    self.restartAgent.checkForCheckingJobs.return_value = S_ERROR()
    res = self.restartAgent.checkExecutor(agentName, options)
    self.assertFalse(res["OK"])
    self.restartAgent.restartInstance.assert_not_called()

    # log file too old, checking jobs OK
    logAge = timedelta(hours=3)
    self.restartAgent.getLastAccessTime.return_value = S_OK(logAge)
    self.restartAgent.checkForCheckingJobs.return_value = S_OK('CHECKING_JOBS')
    res = self.restartAgent.checkExecutor(agentName, options)
    self.assertTrue(res["OK"])
    self.restartAgent.restartInstance.assert_called_once_with(int(pid), agentName, True)

    # log file too old, checking jobs OK, restart failed
    self.restartAgent.restartInstance = MagicMock(return_value=S_ERROR())
    logAge = timedelta(hours=3)
    self.restartAgent.getLastAccessTime.return_value = S_OK(logAge)
    self.restartAgent.checkForCheckingJobs.return_value = S_OK('CHECKING_JOBS')
    res = self.restartAgent.checkExecutor(agentName, options)
    self.assertFalse(res["OK"])
    self.restartAgent.restartInstance.assert_called_once_with(int(pid), agentName, True)

    # log file too old, checking jobs OK, restart disabled
    self.restartAgent.restartExecutors = False
    self.restartAgent.restartInstance = MagicMock(return_value=S_OK('NO_RESTART'))
    logAge = timedelta(hours=3)
    self.restartAgent.getLastAccessTime.return_value = S_OK(logAge)
    self.restartAgent.checkForCheckingJobs.return_value = S_OK('CHECKING_JOBS')
    res = self.restartAgent.checkExecutor(agentName, options)
    self.assertTrue(res["OK"])
    self.restartAgent.restartInstance.assert_called_once_with(int(pid), agentName, False)

  def test_check_services(self):
    """Test for checkServices function."""
    self.restartAgent.getLastAccessTime = MagicMock()
    self.restartAgent.restartInstance = MagicMock(return_value=S_OK())

    agentName = 'serviceX'
    pid = '12345'
    options = dict(PID=pid, System='Skynet', Port=999)
    self.restartAgent.restartServices = False

    # service responds ok
    with patch("ILCDIRAC.FrameworkSystem.Agent.MonitorAgents.RPCClient", new=rpcMock(S_OK())):
      res = self.restartAgent.checkService(agentName, options)
    self.assertTrue(res["OK"])
    self.restartAgent.restartInstance.assert_not_called()

    # service responds not ok
    with patch("ILCDIRAC.FrameworkSystem.Agent.MonitorAgents.RPCClient", new=rpcMock(S_ERROR())):
      res = self.restartAgent.checkService(agentName, options)
    self.assertTrue(res["OK"])
    self.restartAgent.restartInstance.assert_called_once_with(int(pid), agentName, False)

    # service responds not ok
    self.restartAgent.restartInstance.reset_mock()
    self.restartAgent.restartInstance.return_value = S_OK('NO_RESTART')
    self.restartAgent.restartServices = False
    with patch("ILCDIRAC.FrameworkSystem.Agent.MonitorAgents.RPCClient", new=rpcMock(S_ERROR())):
      res = self.restartAgent.checkService(agentName, options)
    self.assertTrue(res["OK"])
    self.restartAgent.restartInstance.assert_called_once_with(int(pid), agentName, False)

    # service responds not ok, restart Failed
    self.restartAgent.restartInstance.reset_mock()
    self.restartAgent.restartServices = True
    self.restartAgent.restartInstance.return_value = S_ERROR()
    with patch("ILCDIRAC.FrameworkSystem.Agent.MonitorAgents.RPCClient", new=rpcMock(S_ERROR())):
      res = self.restartAgent.checkService(agentName, options)
    self.assertFalse(res["OK"])
    self.restartAgent.restartInstance.assert_called_once_with(int(pid), agentName, True)

  def test_get_last_access_time(self):
    """ test for getLastAccessTime function """
    self.agent.os.path.getmtime = MagicMock()
    self.agent.datetime = MagicMock()
    self.agent.datetime.now = MagicMock()
    self.agent.datetime.fromtimestamp = MagicMock()

    now = datetime.now()
    self.agent.datetime.now.return_value = now
    self.agent.datetime.fromtimestamp.return_value = now - timedelta(hours=1)

    res = self.restartAgent.getLastAccessTime('/fake/file')
    self.assertTrue(res["OK"])
    self.assertIsInstance(res["Value"], timedelta)
    self.assertEquals(res["Value"].seconds, 3600)

  def test_restartInstance(self):
    """Test restartInstance function."""
    with patch("ILCDIRAC.FrameworkSystem.Agent.MonitorAgents.psutil", new=self.getPSMock()):
      res = self.restartAgent.restartInstance(12345, "agentX", True)
    self.assertTrue(res['OK'])

    psMock = self.getPSMock()
    psMock.Process = MagicMock("RaisingProc")
    psMock.Error = psutil.Error
    psMock.Process.side_effect = psutil.Error()
    with patch("ILCDIRAC.FrameworkSystem.Agent.MonitorAgents.psutil", new=psMock):
      res = self.restartAgent.restartInstance(12345, "agentX", True)
    self.assertFalse(res['OK'])

  def test_checkingJobs(self):
    """Test checkForCheckingJobs function."""
    self.restartAgent.jobMonClient = MagicMock()

    # failed to get jobs
    self.restartAgent.jobMonClient.getJobs.return_value = S_ERROR()
    self.assertFalse(self.restartAgent.checkForCheckingJobs('executor')['OK'])

    # No checking jobs
    self.restartAgent.jobMonClient.getJobs.return_value = S_OK(0)
    self.assertTrue(self.restartAgent.checkForCheckingJobs('executor')['OK'])
    self.assertEqual(self.restartAgent.checkForCheckingJobs('executor')['Value'], 'NO_CHECKING_JOBS')

    # checking jobs
    self.restartAgent.jobMonClient.getJobs.return_value = S_OK({1: 1, 2: 2})
    self.assertTrue(self.restartAgent.checkForCheckingJobs('executor')['OK'])
    self.assertEqual(self.restartAgent.checkForCheckingJobs('executor')['Value'], 'CHECKING_JOBS')

if __name__ == "__main__":
  SUITE = unittest.defaultTestLoader.loadTestsFromTestCase(TestMonitorAgents)
  TESTRESULT = unittest.TextTestRunner(verbosity=3).run(SUITE)
