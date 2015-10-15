#!/usr/bin/env python
'''
Download the production log files from the Log storage element
See the JDL of production jobs for the log file location

One can also download a full directory of log files

Example

  dirac-ilc-get-prod-log -F /ilc/prod/clic/..../1225_23.tar.gz

Options:
   -D, --LogFileDir lfnDirectory      Production log dir to download
   -F, --LogFile lfn                  Production log to download
   -O, --OutputDir localDir           Output directory (default ./)

:since: Mar 21, 2013
:author: Stephane Poss
'''
__RCSID__ = "$Id$"

from DIRAC.Core.Base import Script
from DIRAC import gLogger, S_OK, S_ERROR, exit as dexit

class _Params(object):
  """Parameter object"""
  def __init__(self):
    self.logD = ''
    self.logF = ''
    self.outputdir = './'
  def setLogFileD(self,opt):
    self.logD = opt
    return S_OK()
  def setLogFileF(self,opt):
    self.logF = opt
    return S_OK()
  def setOutputDir(self,opt):
    self.outputdir = opt
    return S_OK()
  def registerSwitch(self):
    """registers switches"""
    Script.registerSwitch('D:', 'LogFileDir=', 'Production log dir to download', self.setLogFileD)
    Script.registerSwitch('F:', 'LogFile=', 'Production log to download', self.setLogFileF)
    Script.registerSwitch('O:', 'OutputDir=', 'Output directory (default %s)' % self.outputdir, 
                          self.setOutputDir)
    Script.setUsageMessage('%s -F /ilc/prod/.../LOG/.../somefile' % Script.scriptName)


def _printErrorReport(res):
  """Print the failures for the call to getFile or Directory"""
  if res['Value'] and res['Value']['Failed']:
    for lfn in res['Value']['Failed']:
      gLogger.error("%s %s" % (lfn,res['Value']['Failed'][lfn]) )
      return S_ERROR()
  return S_OK()

def _getProdLogs():
  """get production log files from LogSE"""
  clip = _Params()
  clip.registerSwitch()
  Script.parseCommandLine()
  if not clip.logF and not clip.logD:
    Script.showHelp()
    dexit(1)
  from DIRAC.ConfigurationSystem.Client.Helpers.Operations import Operations
  ops = Operations()
  storageElementName = ops.getValue('/LogStorage/LogSE', 'LogSE')
  from DIRAC.Resources.Storage.StorageElement import StorageElementItem as StorageElement
  logSE = StorageElement(storageElementName)

  from DIRAC.Core.Utilities.PromptUser import promptUser
  if clip.logD:
    res = promptUser('Are you sure you want to get ALL the files in this directory?')
    if not res['OK']:
      dexit()
    choice = res['Value']
    if choice.lower()=='n':
      dexit(0)
    res = logSE.getDirectory(clip.logD, localPath=clip.outputdir)
    _printErrorReport(res)

  if clip.logF:
    res = logSE.getFile(clip.logF, localPath = clip.outputdir)
    _printErrorReport(res)

if __name__ == '__main__':
  _getProdLogs()
