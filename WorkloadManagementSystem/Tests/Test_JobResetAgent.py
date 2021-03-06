""" Test JobResetAgent """

import unittest

from datetime import datetime, timedelta
from mock import MagicMock, call

import ILCDIRAC.WorkloadManagementSystem.Agent.JobResetAgent as JRA
from ILCDIRAC.WorkloadManagementSystem.Agent.JobResetAgent import JobResetAgent

import DIRAC.Resources.Storage.StorageElement as SeModule
from DIRAC.RequestManagementSystem.Client.File import File
from DIRAC.RequestManagementSystem.Client.Request import Request
from DIRAC.RequestManagementSystem.Client.Operation import Operation

from DIRAC import S_OK, S_ERROR
from DIRAC import gLogger
import DIRAC

__RCSID__ = "$Id$"


class TestJobResetAgent(unittest.TestCase):
  """ TestJobResetAgent class """

  def setUp(self):
    self.agent = JRA
    self.agent.AgentModule = MagicMock()
    self.agent.JobDB = MagicMock(spec=DIRAC.WorkloadManagementSystem.DB.JobDB.JobDB)
    self.agent.JobMonitoringClient = MagicMock()
    self.agent.DataManager = MagicMock(spec=DIRAC.DataManagementSystem.Client.DataManager.DataManager)
    self.agent.ReqClient = MagicMock(spec=DIRAC.RequestManagementSystem.Client.ReqClient.ReqClient)
    self.agent.NotificationClient = MagicMock(spec=DIRAC.FrameworkSystem.Client.NotificationClient.NotificationClient)

    self.today = datetime(2018, 12, 25, 0, 0, 0, 0)
    self.agent.datetime = MagicMock()
    self.agent.datetime.now.return_value = self.today

    self.jobResetAgent = JobResetAgent()
    self.jobResetAgent.log = gLogger
    self.jobResetAgent.enabled = True
    self.fakeJobID = 1

    self.jobResetAgent.jobManagerClient = MagicMock()
    self.jobResetAgent.jobStateUpdateClient = MagicMock()

    self.doneRemoveRequest = self.createRequest(requestID=1, opType="RemoveFile",
                                                opStatus="Done", fileStatus="Done")
    self.doneReplicateRequest = self.createRequest(requestID=2, opType="ReplicateAndRegister",
                                                   opStatus="Done", fileStatus="Done")
    self.failedReplicateRequest = self.createRequest(requestID=3, opType="ReplicateAndRegister",
                                                     opStatus="Failed", fileStatus="Failed")
    self.failedRemoveRequest = self.createRequest(requestID=4, opType="RemoveFile",
                                                  opStatus="Failed", fileStatus="Failed")

  def tearDown(self):
    pass

  def test_init(self):
    self.assertIsInstance(self.jobResetAgent, JobResetAgent)
    self.assertIsInstance(self.jobResetAgent.jobMonClient, MagicMock)
    self.assertIsInstance(self.jobResetAgent.dataManager, MagicMock)
    self.assertIsInstance(self.jobResetAgent.reqClient, MagicMock)
    self.assertIsInstance(self.jobResetAgent.nClient, MagicMock)
    self.assertTrue(self.jobResetAgent.enabled)
    self.assertEquals(self.jobResetAgent.addressFrom, "ilcdirac-admin@cern.ch")
    self.assertEquals(self.jobResetAgent.userJobTypes, ['User'])
    self.assertEquals(self.jobResetAgent.prodJobTypes, ['MCGeneration', 'MCSimulation', 'MCReconstruction',
                                                        'MCReconstruction_Overlay', 'Split', 'MCSimulation_ILD',
                                                        'MCReconstruction_ILD', 'MCReconstruction_Overlay_ILD',
                                                        'Split_ILD'])

  def test_begin_execution(self):
    """ test for beginExecution function """

    self.jobResetAgent.accounting["Junk"].append("Funk")
    self.jobResetAgent.am_setOption = MagicMock()
    self.jobResetAgent.am_getOption = MagicMock()
    getOptionCalls = [call('EnableFlag', True),
                      call('MailTo', self.jobResetAgent.addressTo),
                      call('MailFrom', self.jobResetAgent.addressFrom),
                      call('UserJobs', self.jobResetAgent.userJobTypes),
                      call('ProdJobs', self.jobResetAgent.prodJobTypes)]

    self.jobResetAgent.beginExecution()
    self.jobResetAgent.am_getOption.assert_has_calls(getOptionCalls)
    # accounting dictionary should be cleared
    self.assertEquals(self.jobResetAgent.accounting, {})

  def test_get_jobs(self):
    """ test for getJobs function """
    jobStatus = "Done"
    jobType = "User"
    minorStatus = "Requests Done"
    attrDict = {"JobType": jobType,
                "MinorStatus": minorStatus,
                "Status": jobStatus}

    self.jobResetAgent.jobDB.selectJobs.return_value = S_ERROR()
    res = self.jobResetAgent.getJobs(jobStatus, jobType, minorStatus)
    self.assertFalse(res["OK"])

    self.jobResetAgent.jobDB.selectJobs.reset_mock()
    self.jobResetAgent.jobDB.selectJobs.return_value = S_OK(["1", "2", "3"])
    res = self.jobResetAgent.getJobs(jobStatus, jobType, minorStatus)
    self.assertEquals(res["Value"], [1, 2, 3])
    self.jobResetAgent.jobDB.selectJobs.assert_called_once_with(attrDict, older=self.today - timedelta(days=1))

  def test_treat_User_Job_With_No_Req(self):
    """ test for treatUserJobWithNoReq function """
    self.jobResetAgent.markJob = MagicMock()

    # case if getJobsMinorStatus function returns an error
    self.jobResetAgent.jobMonClient.getJobsMinorStatus.return_value = S_ERROR()
    res = self.jobResetAgent.treatUserJobWithNoReq(self.fakeJobID)
    self.assertFalse(res["OK"])
    self.jobResetAgent.jobMonClient.getJobsMinorStatus.called_once_with([self.fakeJobID])

    # case if getJobsMinorStatus executes successfully but getJobsApplicationStatus returns an error
    self.jobResetAgent.jobMonClient.getJobsMinorStatus.return_value = S_OK({self.fakeJobID: {'MinorStatus':
                                                                                             JRA.FINAL_MINOR_STATES[0],
                                                                                             'JobID': self.fakeJobID}})
    self.jobResetAgent.jobMonClient.getJobsApplicationStatus.return_value = S_ERROR()
    res = self.jobResetAgent.treatUserJobWithNoReq(self.fakeJobID)
    self.assertFalse(res["OK"])

    # mark job done if ApplicationStatus and MinorStatus are in Final States
    self.jobResetAgent.jobMonClient.getJobsApplicationStatus.return_value = S_OK({self.fakeJobID:
                                                                                  {'ApplicationStatus':
                                                                                   JRA.FINAL_APP_STATES[0],
                                                                                   'JobID': self.fakeJobID}})
    res = self.jobResetAgent.treatUserJobWithNoReq(self.fakeJobID)
    self.assertTrue(res["OK"])
    self.jobResetAgent.markJob.assert_called_once_with(self.fakeJobID, "Done")

    # dont do anything if ApplicationStatus and MinorStatus are not in Final States
    self.jobResetAgent.markJob.reset_mock()
    self.jobResetAgent.jobMonClient.getJobsMinorStatus.return_value = S_OK({self.fakeJobID:
                                                                            {'MinorStatus': 'other status',
                                                                             'JobID': self.fakeJobID}})
    self.jobResetAgent.jobMonClient.getJobsApplicationStatus.return_value = S_OK({self.fakeJobID:
                                                                                  {'ApplicationStatus': 'other status',
                                                                                   'JobID': self.fakeJobID}})
    res = self.jobResetAgent.treatUserJobWithNoReq(self.fakeJobID)
    self.assertTrue(res["OK"])
    self.jobResetAgent.markJob.assert_not_called()

  def test_treat_User_Job_With_Req(self):
    """ test for treatUserJobWithReq function """
    doneRequest = self.createRequest(requestID=1, opType="RemoveFile", opStatus="Done", fileStatus="Done")
    failedRequestID = 2
    failedRequest = self.createRequest(requestID=failedRequestID, opType="RemoveFile", opStatus="Failed",
                                       fileStatus="Failed")
    self.jobResetAgent.resetRequest = MagicMock()
    self.jobResetAgent.markJob = MagicMock()

    # if request status is 'Done' then job should also be marked 'Done'
    self.jobResetAgent.treatUserJobWithReq(self.fakeJobID, doneRequest)
    self.jobResetAgent.markJob.assert_called_once_with(self.fakeJobID, "Done")
    self.jobResetAgent.resetRequest.assert_not_called()

    # if request status is not 'Done' then reset request
    self.jobResetAgent.markJob.reset_mock()
    self.jobResetAgent.treatUserJobWithReq(self.fakeJobID, failedRequest)
    self.jobResetAgent.markJob.assert_not_called()
    self.jobResetAgent.resetRequest.assert_called_once_with(failedRequestID)

  @staticmethod
  def createRequest(requestID, opType, opStatus, fileStatus, lfnError=" "):
    req = Request({"RequestID": requestID})
    op = Operation({"Type": opType, "Status": opStatus})
    op.addFile(File({"LFN": "/ilc/fake/lfn", "Status": fileStatus, "Error": lfnError}))
    req.addOperation(op)
    return req

  def test_treat_Failed_Prod_With_Req(self):
    """ test for treatFailedProdWithReq function """
    self.jobResetAgent.markJob = MagicMock()
    self.jobResetAgent.resetRequest = MagicMock()
    self.jobResetAgent.dataManager.removeFile.reset_mock()

    # if request is done then job should be marked failed
    self.jobResetAgent.treatFailedProdWithReq(self.fakeJobID, self.doneRemoveRequest)
    self.jobResetAgent.markJob.assert_called_once_with(self.fakeJobID, "Failed")

    self.jobResetAgent.markJob.reset_mock()
    self.jobResetAgent.treatFailedProdWithReq(self.fakeJobID, self.doneReplicateRequest)
    self.jobResetAgent.markJob.assert_called_once_with(self.fakeJobID, "Failed")

    # failed requests with removeFile operation should be reset
    self.jobResetAgent.markJob.reset_mock()
    self.jobResetAgent.treatFailedProdWithReq(self.fakeJobID, self.failedRemoveRequest)
    fileLfn = self.failedRemoveRequest[0][0].LFN
    self.jobResetAgent.dataManager.removeFile.assert_called_once_with([fileLfn], force=True)
    self.jobResetAgent.resetRequest.assert_called_once_with(getattr(self.failedRemoveRequest, "RequestID"))
    self.jobResetAgent.markJob.asset_not_called()

    # failed requests with operations other than removeFile should not be reset
    self.jobResetAgent.resetRequest.reset_mock()
    self.jobResetAgent.dataManager.reset_mock()
    self.jobResetAgent.treatFailedProdWithReq(self.fakeJobID, self.failedReplicateRequest)
    self.jobResetAgent.dataManager.assert_not_called()
    self.jobResetAgent.resetRequest.assert_not_called()
    self.jobResetAgent.markJob.asset_not_called()

  def test_treat_Failed_Prod_With_No_Req(self):
    """ test for treatFailedProdWithNoReq function """
    self.jobResetAgent.markJob = MagicMock()
    self.jobResetAgent.treatFailedProdWithNoReq(self.fakeJobID)
    self.jobResetAgent.markJob.assert_called_once_with(self.fakeJobID, "Failed")

  def test_treat_Completed_Prod_With_Req(self):
    """ test for treatCompletedProdWithReq function """
    self.jobResetAgent.markJob = MagicMock()
    self.jobResetAgent.resetRequest = MagicMock()

    # if request is done then job should be marked Done
    self.jobResetAgent.treatCompletedProdWithReq(self.fakeJobID, self.doneRemoveRequest)
    self.jobResetAgent.markJob.assert_called_once_with(self.fakeJobID, "Done")

    self.jobResetAgent.markJob.reset_mock()
    self.jobResetAgent.treatCompletedProdWithReq(self.fakeJobID, self.doneReplicateRequest)
    self.jobResetAgent.markJob.assert_called_once_with(self.fakeJobID, "Done")

    # job with failed ReplicateAndRegister operation should be marked done if file does not exist
    self.jobResetAgent.markJob.reset_mock()
    request = self.createRequest(requestID=1, opType="RemoveFile", opStatus="Done",
                                 fileStatus="Done", lfnError="No such file")
    self.jobResetAgent.treatCompletedProdWithReq(self.fakeJobID, request)
    self.jobResetAgent.markJob.assert_called_once_with(self.fakeJobID, "Done")

    # failed requests with ReplicateAndRegister operation should be reset
    self.jobResetAgent.markJob.reset_mock()
    self.jobResetAgent.treatCompletedProdWithReq(self.fakeJobID, self.failedReplicateRequest)
    self.jobResetAgent.resetRequest.assert_called_once_with(getattr(self.failedReplicateRequest, "RequestID"))

    # failed Remove file request should not be reset
    self.jobResetAgent.resetRequest.reset_mock()
    self.jobResetAgent.treatCompletedProdWithReq(self.fakeJobID, self.failedRemoveRequest)
    self.jobResetAgent.markJob.assert_not_called()
    self.jobResetAgent.resetRequest.assert_not_called()

  def test_treat_Completed_Prod_With_No_Req(self):
    """ test for treatCompletedProdWithNoReq function """
    self.jobResetAgent.markJob = MagicMock()
    self.jobResetAgent.treatCompletedProdWithNoReq(self.fakeJobID)
    self.jobResetAgent.markJob.assert_called_once_with(self.fakeJobID, "Done")

  def test_check_jobs(self):
    """ test for checkJobs function """
    jobIDs = [1, 2]
    dummy_treatJobWithNoReq = MagicMock()
    dummy_treatJobWithReq = MagicMock()

    # if the readRequestsForJobs func returns error than checkJobs should exit and return an error
    self.jobResetAgent.reqClient.readRequestsForJobs.return_value = S_ERROR()
    res = self.jobResetAgent.checkJobs(jobIDs, treatJobWithNoReq=dummy_treatJobWithNoReq,
                                       treatJobWithReq=dummy_treatJobWithReq)
    self.assertFalse(res["OK"])

    # test if correct treatment functions are called
    self.jobResetAgent.reqClient.readRequestsForJobs.return_value = S_OK({'Successful': {},
                                                                          'Failed': {jobIDs[0]: 'Request not found'}})
    self.jobResetAgent.checkJobs(jobIDs, treatJobWithNoReq=dummy_treatJobWithNoReq,
                                 treatJobWithReq=dummy_treatJobWithReq)
    dummy_treatJobWithNoReq.assert_has_calls([call(jobIDs[0]), call(jobIDs[1])])
    dummy_treatJobWithReq.assert_not_called()

    dummy_treatJobWithNoReq.reset_mock()
    req1 = Request({"RequestID": 1})
    req2 = Request({"RequestID": 2})
    self.jobResetAgent.reqClient.readRequestsForJobs.return_value = S_OK({'Successful': {jobIDs[0]: req1,
                                                                                         jobIDs[1]: req2},
                                                                          'Failed': {}})
    self.jobResetAgent.checkJobs(jobIDs, treatJobWithNoReq=dummy_treatJobWithNoReq,
                                 treatJobWithReq=dummy_treatJobWithReq)
    dummy_treatJobWithNoReq.assert_not_called()
    dummy_treatJobWithReq.assert_has_calls([call(jobIDs[0], req1), call(jobIDs[1], req2)])

  def test_get_staged_files(self):
    """ test for getStagedFiles function """
    stagedFile = "/ilc/fake/lfn1/staged"
    nonStagedFile = "/ilc/fake/lfn2/nonStaged"
    lfns = [stagedFile, nonStagedFile]

    res = self.jobResetAgent.getStagedFiles([])
    self.assertTrue(res["OK"])

    SeModule.StorageElementItem.getFileMetadata = MagicMock(return_value=S_ERROR())
    res = self.jobResetAgent.getStagedFiles(lfns)
    self.assertFalse(res["OK"])

    SeModule.StorageElementItem.getFileMetadata.return_value = S_OK({'Successful': {stagedFile: {'Cached': 1},
                                                                                    nonStagedFile: {'Cached': 0}}})
    res = self.jobResetAgent.getStagedFiles(lfns)
    self.assertEquals(res["Value"], [stagedFile])

  def test_get_input_data_for_jobs(self):
    """ test for getInputDataForJobs function """
    jobIDs = [1, 2]
    lfn1 = "/ilc/fake/lfn1"
    lfn2 = "/ilc/fake/lfn2"
    self.jobResetAgent.jobMonClient.getInputData.return_value = S_ERROR()

    res = self.jobResetAgent.getInputDataForJobs(jobIDs)
    self.assertEquals(res["Value"], {})

    self.jobResetAgent.jobMonClient.getInputData.return_value = S_OK([lfn1, lfn2])
    res = self.jobResetAgent.getInputDataForJobs(jobIDs)
    self.assertEquals(res["Value"], {lfn1: jobIDs, lfn2: jobIDs})

  def test_reschedule_jobs(self):
    """ test for rescheduleJobs function """
    jobShouldFailToReset = 1
    jobShouldSuccessfullyReset = 2
    jobsToReschedule = [jobShouldFailToReset, jobShouldSuccessfullyReset]

    self.jobResetAgent.jobManagerClient.resetJob.side_effect = [S_ERROR(), S_OK()]
    res = self.jobResetAgent.rescheduleJobs(jobsToReschedule)
    self.assertTrue(res["OK"])
    self.assertEquals(res["Value"]["Successful"], [jobShouldSuccessfullyReset])
    self.assertEquals(res["Value"]["Failed"], [jobShouldFailToReset])

  def test_check_staging_jobs(self):
    """ test for checkStagingJobs function """
    jobShouldBeRescheduled = 1
    jobShouldNotBeResecheduled = 2
    stagedFile = "/ilc/file/staged"
    notStagedFile = "/ilc/file/notStaged"
    jobIDs = [jobShouldBeRescheduled, jobShouldNotBeResecheduled]

    self.jobResetAgent.getInputDataForJobs = MagicMock()
    self.jobResetAgent.getStagedFiles = MagicMock()
    self.jobResetAgent.rescheduleJobs = MagicMock()

    self.jobResetAgent.getInputDataForJobs.return_value = S_OK({})
    res = self.jobResetAgent.checkStagingJobs(jobIDs)
    self.assertTrue(res["OK"])
    self.jobResetAgent.getInputDataForJobs.assert_called_once_with(jobIDs)
    self.jobResetAgent.getStagedFiles.assert_not_called()

    jobsToReschedule = set()
    jobsToReschedule.add(jobShouldBeRescheduled)
    self.jobResetAgent.getInputDataForJobs.reset_mock()
    self.jobResetAgent.getInputDataForJobs.return_value = S_OK({stagedFile: jobShouldBeRescheduled,
                                                                notStagedFile: jobShouldNotBeResecheduled})
    self.jobResetAgent.getStagedFiles.return_value = S_OK([stagedFile])
    self.jobResetAgent.checkStagingJobs(jobIDs)
    self.jobResetAgent.rescheduleJobs.assert_called_once_with(jobsToReschedule)

  def test_reset_request(self):
    """ test for resetRequest function """
    fakeReqID = 1
    self.jobResetAgent.logError = MagicMock()
    self.jobResetAgent.reqClient.resetFailedRequest.return_value = S_ERROR()
    res = self.jobResetAgent.resetRequest(fakeReqID)
    self.jobResetAgent.logError.assert_called()
    self.assertFalse(res["OK"])

    self.jobResetAgent.logError.reset_mock()
    self.jobResetAgent.reqClient.resetFailedRequest.return_value = S_OK("Not reset")
    res = self.jobResetAgent.resetRequest(fakeReqID)
    self.assertFalse(res["OK"])
    self.jobResetAgent.logError.assert_called()

    self.jobResetAgent.logError.reset_mock()
    self.jobResetAgent.reqClient.resetFailedRequest.return_value = S_OK()
    res = self.jobResetAgent.resetRequest(fakeReqID)
    self.assertTrue(res["OK"])
    self.jobResetAgent.logError.assert_not_called()

  def test_mark_job(self):
    """ test for markJob function """
    fakeMinorStatus = "fakeMinorStatus"
    fakeApp = "fakeApp"
    fakeJobStatus = "Done"
    defaultMinorStatus = "Requests Done"
    defaultApplication = "CompletedJobChecker"

    # default minorStatus should be "Requests Done" and application should be "CompletedJobChecker"
    self.jobResetAgent.jobStateUpdateClient.setJobStatus = MagicMock(return_value=S_ERROR())
    res = self.jobResetAgent.markJob(self.fakeJobID, fakeJobStatus)
    self.assertFalse(res["OK"])
    self.jobResetAgent.jobStateUpdateClient.setJobStatus.assert_called_once_with(self.fakeJobID,
                                                                                 fakeJobStatus,
                                                                                 defaultMinorStatus,
                                                                                 defaultApplication)

    self.jobResetAgent.jobStateUpdateClient.setJobStatus.reset_mock()
    self.jobResetAgent.jobStateUpdateClient.setJobStatus.return_value = S_OK()
    res = self.jobResetAgent.markJob(self.fakeJobID, fakeJobStatus, minorStatus=fakeMinorStatus, application=fakeApp)
    self.assertTrue(res["OK"])
    self.jobResetAgent.jobStateUpdateClient.setJobStatus.assert_called_once_with(self.fakeJobID, fakeJobStatus,
                                                                                 fakeMinorStatus, fakeApp)

  def test_execute(self):
    """ test for execute function """
    jobIDs = [1, 2]
    self.jobResetAgent.getJobs = MagicMock()
    self.jobResetAgent.checkJobs = MagicMock()
    self.jobResetAgent.checkStagingJobs = MagicMock()

    self.jobResetAgent.getJobs.return_value = S_OK(jobIDs)
    self.jobResetAgent.execute()
    # check if checkJobs function is called with correct arguments
    completedProdJobCall = call(jobIDs=jobIDs, treatJobWithNoReq=self.jobResetAgent.treatCompletedProdWithNoReq,
                                treatJobWithReq=self.jobResetAgent.treatCompletedProdWithReq)
    failedProdJobCall = call(jobIDs=jobIDs, treatJobWithNoReq=self.jobResetAgent.treatFailedProdWithNoReq,
                             treatJobWithReq=self.jobResetAgent.treatFailedProdWithReq)
    completedUserJob = call(jobIDs=jobIDs, treatJobWithNoReq=self.jobResetAgent.treatUserJobWithNoReq,
                            treatJobWithReq=self.jobResetAgent.treatUserJobWithReq)
    calls = [completedProdJobCall, failedProdJobCall, completedUserJob]
    self.jobResetAgent.checkJobs.assert_has_calls(calls)
    self.jobResetAgent.checkStagingJobs.assert_called_once_with(jobIDs)

  def test_send_notification(self):
    """ test for sendNotification function """
    self.jobResetAgent.errors = []
    self.jobResetAgent.accounting = {}

    # send mail should not be called if there are no errors and accounting information
    self.jobResetAgent.sendNotification()
    self.jobResetAgent.nClient.sendMail.assert_not_called()

    # send mail should be called if there are errors but no accounting information
    self.jobResetAgent.errors = ["some error"]
    self.jobResetAgent.sendNotification()
    self.jobResetAgent.nClient.sendMail.assert_called()

    # send email should be called if there is accounting information but no errors
    self.jobResetAgent.nClient.sendMail.reset_mock()
    self.jobResetAgent.errors = []
    self.jobResetAgent.accounting = {"User": [{"JobID": 123, "JobStatus": "Failed", "Treatment": "reset request"}],
                                     "Prod": [{"JobID": 124, "JobStatus": "Failed", "Treatment": "reset request"}]}
    self.jobResetAgent.sendNotification()
    self.jobResetAgent.nClient.sendMail.assert_called()

    # try sending email to all addresses even if we get error for sending email to some address
    self.jobResetAgent.nClient.sendMail.reset_mock()
    self.jobResetAgent.errors = ["some error"]
    self.jobResetAgent.addressTo = ["name1@cern.ch", "name2@cern.ch"]
    self.jobResetAgent.nClient.sendMail.return_value = S_ERROR()
    self.jobResetAgent.sendNotification()
    self.assertEquals(len(self.jobResetAgent.nClient.sendMail.mock_calls),
                      len(self.jobResetAgent.addressTo))

    # accounting dict and errors list should be cleared after notification is sent
    self.assertEquals(self.jobResetAgent.accounting, {})
    self.assertEquals(self.jobResetAgent.errors, [])


if __name__ == "__main__":
  SUITE = unittest.defaultTestLoader.loadTestsFromTestCase(TestJobResetAgent)
  TESTRESULT = unittest.TextTestRunner(verbosity=3).run(SUITE)
