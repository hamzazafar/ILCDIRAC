'''
Created on Apr 26, 2010

@author: sposs
'''

from DIRAC import gConfig,gLogger

def resolveDeps(sysconfig,appli,appversion):
  deps = gConfig.getSections('/Operations/AvailableTarBalls/%s/%s/%s/Dependencies'%(sysconfig,appli,appversion),'')
  depsarray = []
  if deps['OK']:
    for dep in deps['Value']:
      vers = gConfig.getOption('/Operations/AvailableTarBalls/%s/%s/%s/Dependencies/%s/version'%(sysconfig,appli,appversion,dep),'')
      depvers = ''
      if vers['OK']:
        depvers = vers['Value']
      else:
        gLogger.error("Retrieving dependency version for %s failed, skipping to next !"%(dep))
        continue
      dep_tar = gConfig.getOption('/Operations/AvailableTarBalls/%s/%s/%s/TarBall'%(sysconfig,dep,depvers),'')
      if dep_tar['OK']:
        depsarray.append(dep_tar["Value"])
      else:
        gLogger.error("Dependency %s version %s is not defined in CS, please check !"%(dep["app"],dep["version"]))         
  else:
    gLogger.verbose("Could not find any dependency, ignoring")
  return depsarray

  