"""
Module with functions to get proxies for specific groups
Special function to get production
Checks and potentially provides production proxy, called from :mod:`~ILCDIRAC.Interfaces.API.NewInterface.ProductionJob`

:since: Feb 10, 2011
:author: sposs, A.Sailer
"""
from subprocess import call

from DIRAC import S_OK, S_ERROR
from DIRAC.Core.Security.ProxyInfo import getProxyInfo

__RCSID__ = "$Id$"

def getNewProxy( group = "ilc_prod" ):
  """ Get a new production proxy

  :param str group: dirac group of the proxy to get
  :returns: statuscode of the dirac-proxy-init call: 0 success, otherwise error!
  """
  print 'Getting production proxy ...'
  return call( [ 'dirac-proxy-init', '-g', group ] )

def checkAndGetProdProxy():
  """ Check if current proxy is a production one, and if not call the :any:`getNewProxy` method.
  .. deprecated:: v25r0p0 use checkOrGetGroupProxy

  :returns: :func:`S_OK() <DIRAC:DIRAC.Core.Utilities.ReturnValues.S_OK>`, :func:`~DIRAC:DIRAC.Core.Utilities.ReturnValues.S_ERROR`
  """
  return checkOrGetGroupProxy( group="ilc_prod" )

def checkOrGetGroupProxy( group ):
  """Check if current proxy corresponds to the given group, and if not call the
  :any:`getNewProxy` method to obtain a proxy for this group

  :param group: dirac group of the desired proxy
  :type group: python:list, str
  :returns: :func:`~DIRAC:DIRAC.Core.Utilities.ReturnValues.S_OK`,
     :func:`~DIRAC:DIRAC.Core.Utilities.ReturnValues.S_ERROR`
  """
  result = getProxyInfo()
  groups = group
  if not isinstance(groups, (list, set, tuple)):
    groups = [groups]
  if result['OK'] and 'group' in result['Value']:
    if result['Value']['group'] in groups:
      return S_OK(result['Value']['group'])
    else:
      print "You don't have an %s proxy, trying to get one..." % group
  else:
    print "Error to get proxy information, trying to get proxy"

  if not len(groups) == 1:
    return S_ERROR("More than one proxy group possible, cannot continue, please get proper proxy")

  newProxyRetVal = getNewProxy(group=groups[0])
  if newProxyRetVal: ## != 0
    return S_ERROR("dirac-proxy-init failed")

  result = getProxyInfo()
  if result['OK'] and 'group' in result['Value']:
    if result['Value']['group'] in groups:
      return S_OK(result['Value']['group'])
    else:
      print 'You do not have a valid group'
      return S_ERROR( "Could not obtain valid group" )
  elif result['OK'] and 'group' not in result['Value']:
    return S_ERROR( "Could not obtain group information from proxy" )

  print 'Could not obtain proxy information: %s' % result['Message']
  return result
