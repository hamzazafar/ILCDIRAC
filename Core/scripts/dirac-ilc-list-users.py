#!/bin/env python
""" List the VO members
"""

__RCSID__ = "$Id$"

from DIRAC import S_OK, S_ERROR, gLogger, exit as dexit
from DIRAC.Core.Base import Script

##Check if suds exists and print information how to install it
try:
  import suds #pylint: disable=W0611
except ImportError:
  print "Run [sudo] easy_install suds"
  raise

class Params(object):
  """Parameter Object"""
  def __init__(self):
    self.username = ''
    self.voName = 'ilc'
    self.adminUrl = "https://grid-voms.desy.de:8443/voms/%s/services/VOMSAdmin"
    self.attributeUrl = "https://grid-voms.desy.de:8443/voms/%s/services/VOMSAttributes"
    self.addPrint = False
  def registerSwitches(self):
    Script.registerSwitch("u:", "UserName=", "Family name of the user", self.setUser)
    Script.registerSwitch("v:", "VO=", "VO to print or search: [ilc|calice]", self.setVO)
    Script.registerSwitch("A", "addUser:", "print output as input for dirac-ilc-add-user", self.setAddPrint)
    Script.setUsageMessage("""%s -U <username> [-v ilc|calice] [-A]""" % Script.scriptName)
  def setUser(self, opt):
    self.username = opt
    return S_OK()
  def setVO(self, opt):
    if opt not in ['ilc', 'calice']:
      return S_ERROR("Unknown VO %s: ilc or calice only" % opt)
    self.voName = opt
    return S_OK()

  def setAddPrint(self, dummy=False):
    """Set the flag to print user strings as input for dirac-ilc-add-user"""
    self.addPrint = True
    return S_OK()
    
  def setURLs(self):
    """Set the proper urls based on the vo"""
    self.adminUrl = self.adminUrl % self.voName
    self.attributeUrl = self.attributeUrl % self.voName


def printUser(user, addPrint):
  """print user information"""
  if addPrint:
    gLogger.notice("-D\"%s\" -C\"%s\" -E\"%s\"" % (user['DN'], user['CA'], user['mail']))
  else:
    gLogger.notice("%s, %s, %s" % (user['DN'], user['CA'], user['mail']))

    
def printUsers():
  """Print the list of users in the VO"""
  clip = Params()
  clip.registerSwitches()
  Script.parseCommandLine()
  clip.setURLs()
  
  from DIRAC.Core.Security.VOMSService import VOMSService
  voms = VOMSService( vo=clip.voName, adminUrl=clip.adminUrl, attributesUrl=clip.attributeUrl )
  res = voms.admListMembers()
  if not res['OK']:
    gLogger.error(res['Message'])
    dexit(1)
  users = res['Value']
  for user in users:
    if not clip.username:
      printUser(user, clip.addPrint)
    else:
      if user['DN'].lower().count(clip.username.lower()):
        printUser(user, clip.addPrint)


if __name__ == "__main__":
  printUsers()
