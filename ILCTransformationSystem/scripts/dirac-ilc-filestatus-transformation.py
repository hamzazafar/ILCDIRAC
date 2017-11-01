#!/bin/env python
"""

Example:

Options:

"""

__RCSID__ = "$Id$"

import importlib

from mock import MagicMock

from DIRAC.Core.Base import Script
from DIRAC import gLogger, S_OK, S_ERROR
from DIRAC import exit as dexit

from ILCDIRAC.ILCTransformationSystem.Agent.FileStatusTransformationAgent import FileStatusTransformationAgent

class _Params(object):
  """ parameters object """

  def __init__(self):
    self.transID = None
    self.enabled = False

  def setTransID(self, transID):
    self.transID = transID

  def registerSwitches(self):
    Script.registerSwitch( "E", "enabled", "perform delete operations on file catalog", self.enabled )
    Script.setUsageMessage("""%s <transformationID> -E""" % Script.scriptName)

  def checkSettings(self):
    """ parse arguments """

    args = Script.getPositionalArgs()
    if len(args) < 2:
      return S_ERROR()
    else:
      self.setTransID( args[0] )

    return S_OK()

def _runFSTAgent():
  """ read commands line params and run FST agent for a given transformation ID """
  params = _Params()
  params.registerSwitches()
  Script.parseCommandLine()
  if not params.checkSettings()['OK']:
    Script.showHelp()
    dExit(1)

  agent = importlib.import_module('ILCDIRAC.ILCTransformationSystem.Agent.FileStatusTransformationAgent')
  agent.AgentModule = MagicMock()
  fstAgent = FileStatusTransformationAgent()
  fstAgent.log = gLogger
  fstAgent.enabled = params.enabled

  res = fstAgent.processTransformation(params.transID)
  if not res["OK"]:
    dexit(1)

  dexit(0)

if __name__=="__main__":
  _runFSTAgent()
