# $HeadURL$
# $Id$
'''
Mokka analysis module. Called by Job Agent. 

@since:  Jan 29, 2010

@author: Stephane Poss and Przemyslaw Majewski
'''
from DIRAC.Core.Utilities.Subprocess                     import shellCall
from ILCDIRAC.Workflow.Modules.ModuleBase                import ModuleBase
from ILCDIRAC.Core.Utilities.CombinedSoftwareInstallation  import LocalArea,SharedArea
from ILCDIRAC.Core.Utilities.PrepareOptionFiles         import PrepareSteeringFile,GetNewLDLibs
from ILCDIRAC.Core.Utilities.SQLWrapper                   import SQLWrapper
from ILCDIRAC.Core.Utilities.ResolveDependencies          import resolveDepsTar
from ILCDIRAC.Core.Utilities.PrepareLibs import removeLibc

from ILCDIRAC.Core.Utilities.resolveIFpaths import resolveIFpaths
from ILCDIRAC.Core.Utilities.resolveOFnames import getProdFilename
from ILCDIRAC.Core.Utilities.InputFilesUtilities import getNumberOfevents
from DIRAC                                               import S_OK, S_ERROR, gLogger, gConfig

import DIRAC

import re, os, sys

#random string generator 
import string
from random import choice



class MokkaAnalysis(ModuleBase):
    """
    Specific Module to run a Mokka job.
    """
    def __init__(self):
        ModuleBase.__init__(self)
        self.enable = True
        self.STEP_NUMBER = ''
        self.log = gLogger.getSubLogger( "MokkaAnalysis" )
        self.steeringFile = ''
        self.stdhepFile = ''
        self.macFile = ''
        self.run_number = 0
        self.firstEventNumber = 1
        self.applicationName = 'Mokka'
        self.dbslice = ''
        self.numberOfEvents = 0
        self.startFrom = 0
        self.eventstring = ''

#############################################################################
    def applicationSpecificInputs(self):
      """ Resolve all input variables for the module here.
      @return: S_OK()
      """

      if self.step_commons.has_key('numberOfEvents'):
          self.numberOfEvents = self.step_commons['numberOfEvents']
          
      if self.step_commons.has_key('startFrom'):
        self.startFrom = self.step_commons['startFrom']

      if self.step_commons.has_key("steeringFile"):
        self.steeringFile = self.step_commons['steeringFile']

      if self.step_commons.has_key('stdhepFile'):
        self.stdhepFile = self.step_commons['stdhepFile']
      
      if self.step_commons.has_key('macFile'):
        self.macFile = self.step_commons['macFile']

      if self.step_commons.has_key('detectorModel'):
        self.detectorModel = self.step_commons['detectorModel']

      if self.step_commons.has_key("RandomSeed"):
        self.randomseed = self.step_commons["RandomSeed"]
      elif self.workflow_commons.has_key("IS_PROD"):  
        self.randomseed = int(str(int(self.workflow_commons["PRODUCTION_ID"]))+str(int(self.workflow_commons["JOB_ID"])))
      elif self.jobID:
        self.randomseed = self.jobID
        
      if self.step_commons.has_key('dbSlice'):
        self.dbslice = self.step_commons['dbSlice']
      
      if self.workflow_commons.has_key("IS_PROD"):
        if self.workflow_commons["IS_PROD"]:
          #self.outputFile = getProdFilename(self.outputFile,int(self.workflow_commons["PRODUCTION_ID"]),
          #                                  int(self.workflow_commons["JOB_ID"]))
          if self.workflow_commons.has_key('ProductionOutputData'):
            outputlist = self.workflow_commons['ProductionOutputData'].split(";")
            for obj in outputlist:
              if obj.lower().count("_sim_"):
                self.outputFile = os.path.basename(obj)
              elif obj.lower().count("_gen_"):
                self.stdhepFile = os.path.basename(obj)
          else:
            self.outputFile = getProdFilename(self.outputFile,int(self.workflow_commons["PRODUCTION_ID"]),
                                              int(self.workflow_commons["JOB_ID"]))
            if self.workflow_commons.has_key("WhizardOutput"):
              self.stdhepFile = getProdFilename(self.workflow_commons["WhizardOutput"],int(self.workflow_commons["PRODUCTION_ID"]),
                                                int(self.workflow_commons["JOB_ID"]))
      
      if self.InputData:
        if not self.workflow_commons.has_key("Luminosity") or not self.workflow_commons.has_key("NbOfEvents"):
          res = getNumberOfevents(self.InputData)
          if res.has_key("nbevts") and not self.workflow_commons.has_key("Luminosity") :
            self.workflow_commons["NbOfEvents"]=res["nbevts"]
            if not self.numberOfEvents:
              self.numberOfEvents=res["nbevts"]
          if res.has_key("lumi") and not self.workflow_commons.has_key("NbOfEvents"):
            self.workflow_commons["Luminosity"]=res["lumi"]

      if len(self.stdhepFile)==0 and not len(self.InputData)==0:
        inputfiles = self.InputData.split(";")
        for files in inputfiles:
          if files.lower().find(".stdhep")>-1 or files.lower().find(".hepevt")>-1:
            self.stdhepFile = files
            break
        
      return S_OK('Parameters resolved')
    
    def execute(self):
      """ Called by Agent
      
      Executes the following:
        - read the application parameters that where defined in ILCJob, and stored in the job definition
        - setup the SQL server and run it in the background, via a call to L{SQLWrapper}
        - prepare the steering fie using L{PrepareSteeringFile}
        - run Mokka and catch its return status
      @return: S_OK(), S_ERROR()
      
      """
      result = self.resolveInputVariables()
      if not result['OK']:
        return result
      #if not self.workflowStatus['OK'] or not self.stepStatus['OK']:
      #  self.log.info('Skip this module, failure detected in a previous step :')
      #  self.log.info('Workflow status : %s' %(self.workflowStatus))
      #  self.log.info('Step Status %s' %(self.stepStatus))
      #  return S_OK()

      self.result = S_OK()
       
      if not self.systemConfig:
        self.result = S_ERROR( 'No ILC platform selected' )
      elif not self.applicationLog:
        self.result = S_ERROR( 'No Log file provided' )

      if not self.result['OK']:
        return self.result

      if not self.workflowStatus['OK'] or not self.stepStatus['OK']:
        self.log.verbose('Workflow status = %s, step status = %s' %(self.workflowStatus['OK'],self.stepStatus['OK']))
        return S_OK('Mokka should not proceed as previous step did not end properly')

      cwd = os.getcwd()
      self.root = gConfig.getValue('/LocalSite/Root',cwd)
      self.log.info( "Executing Mokka %s"%(self.applicationVersion))
      self.log.info("Platform for job is %s" % ( self.systemConfig ) )
      self.log.info("Root directory for job is %s" % ( self.root ) )

      mokkaDir = gConfig.getValue('/Operations/AvailableTarBalls/%s/%s/%s/TarBall'%(self.systemConfig,"mokka",self.applicationVersion),'')
      if not mokkaDir:
        self.log.error('Could not get Tar ball name')
        return S_ERROR('Failed finding software directory')
      mokkaDir = mokkaDir.replace(".tgz","").replace(".tar.gz","")
      #mokkaDir = 'lddLib' ###Temporary while mokka tar ball are not redone.
      mySoftwareRoot = ''
      localArea = LocalArea()
      sharedArea = SharedArea()
      if os.path.exists('%s%s%s' %(localArea,os.sep,mokkaDir)):
        mySoftwareRoot = localArea
      elif os.path.exists('%s%s%s' %(sharedArea,os.sep,mokkaDir)):
        mySoftwareRoot = sharedArea
      else:
        self.log.error("Mokka: could not find installation directory!")
        return S_ERROR("Mokka installation could not be found")  
      myMokkaDir = os.path.join(mySoftwareRoot,mokkaDir)
      
      if not mySoftwareRoot:
        self.log.error('Directory %s was not found in either the local area %s or shared area %s' %(mokkaDir,localArea,sharedArea))
        return S_ERROR('Failed to discover software')


      ####Setup MySQL instance      
      MokkaDBrandomName =  '/tmp/MokkaDBRoot-' + self.GenRandString(8);
      
      #sqlwrapper = SQLWrapper(self.dbslice,mySoftwareRoot,"/tmp/MokkaDBRoot")#mySoftwareRoot)
      sqlwrapper = SQLWrapper(self.dbslice,mySoftwareRoot,MokkaDBrandomName)#mySoftwareRoot)
      result = sqlwrapper.makedirs()
      if not result['OK']:
        self.setApplicationStatus('MySQL setup failed to create directories.')
        return result
      result =sqlwrapper.mysqlSetup()
      if not result['OK']:
        self.setApplicationStatus('MySQL setup failed.')
        return result

      ##Need to fetch the new LD_LIBRARY_PATH
      new_ld_lib_path= GetNewLDLibs(self.systemConfig,"mokka",self.applicationVersion,mySoftwareRoot)

      ##Remove libc
      removeLibc(myMokkaDir)

      ###steering file that will be used to run
      mokkasteer = "mokka.steer"
      ###prepare steering file
      #first, I need to take the stdhep file, find its path (possible LFN)      
      if len(self.stdhepFile)>0:
        #self.stdhepFile = os.path.basename(self.stdhepFile)
        res = resolveIFpaths([self.stdhepFile])
        if not res['OK']:
          self.log.error("Generator file not found")
          return res
        self.stdhepFile = res['Value'][0]
      if len(self.macFile)>0:
        self.macFile = os.path.basename(self.macFile)
      ##idem for steering file
      self.steeringFile = os.path.basename(self.steeringFile)
      steerok = PrepareSteeringFile(self.steeringFile,mokkasteer,self.detectorModel,self.stdhepFile,
                                    self.macFile,self.numberOfEvents,self.startFrom,self.randomseed,self.debug,
                                    self.outputFile)
      if not steerok['OK']:
        self.log.error('Failed to create MOKKA steering file')
        return S_ERROR('Failed to create MOKKA steering file')

      ###Extra option depending on mokka version
      mokkaextraoption = ""
      if self.applicationVersion not in ["v07-02","v07-02fw","v07-02fwhp","MokkaRevision42","MokkaRevision43","MokkaRevision44",
                                         "Revision45"]:
        mokkaextraoption = "-U"

      scriptName = 'Mokka_%s_Run_%s.sh' %(self.applicationVersion,self.STEP_NUMBER)

      if os.path.exists(scriptName): os.remove(scriptName)
      script = open(scriptName,'w')
      script.write('#!/bin/sh \n')
      script.write('#####################################################################\n')
      script.write('# Dynamically generated script to run a production or analysis job. #\n')
      script.write('#####################################################################\n')
      #if(os.path.exists(sharedArea+"/initILCSOFT.sh")):
      #    script.write("%s/initILCSOFT.sh"%sharedArea)
      script.write("declare -x g4releases=%s\n" %(myMokkaDir))
      script.write("declare -x G4SYSTEM=Linux-g++\n")
      script.write("declare -x G4INSTALL=$g4releases/share/$g4version\n")
      #script.write("export G4SYSTEM G4INSTALL G4LIB CLHEP_BASE_DIR\n")
      script.write('declare -x G4LEDATA="$g4releases/sl4/g4data/g4dataEMLOW"\n')
      script.write('declare -x G4NEUTRONHPDATA="$g4releases/sl4/g4data/g4dataNDL"\n')
      script.write('declare -x G4LEVELGAMMADATA="$g4releases/sl4/g4data/g4dataPhotonEvap"\n')
      script.write('declare -x G4RADIOACTIVEDATA="$g4releases/sl4/g4data/g4dataRadiativeDecay"\n')
      ###No such data on the GRID (???)
      #script.write('G4ELASTICDATA="$g4releases/share/data/G4ELASTIC1.1"\n')
      script.write('declare -x G4ABLADATA="$g4releases/sl4/g4data/g4dataABLA"\n')
      #script.write("export G4LEDATA G4NEUTRONHPDATA G4LEVELGAMMADATA G4RADIOACTIVEDATA G4ABLADATA\n")
      
      #### Do something with the additional environment variables
      add_env = gConfig.getOptionsDict("/Operations/AvailableTarBalls/%s/%s/%s/AdditionalEnvVar"%(self.systemConfig,"mokka",self.applicationVersion))
      if add_env['OK']:
        for key in add_env['Value'].keys():
          script.write('declare -x %s=%s/%s\n'%(key,mySoftwareRoot,add_env['Value'][key]))
      else:
        self.log.verbose("No additional environment variables needed for this application")
      
      if(os.path.exists("./lib")):
        if new_ld_lib_path:
          script.write('declare -x LD_LIBRARY_PATH=./lib:%s:%s\n'%(myMokkaDir,new_ld_lib_path))
        else:
          script.write('declare -x LD_LIBRARY_PATH=./lib:%s\n' %(myMokkaDir))
      else:
        if new_ld_lib_path:
          script.write('declare -x LD_LIBRARY_PATH=%s:%s\n'%(myMokkaDir,new_ld_lib_path))
        else:
          script.write('declare -x LD_LIBRARY_PATH=%s\n'%(myMokkaDir))          
          
      script.write("declare -x PATH=%s:%s\n"%(myMokkaDir,os.environ['PATH']))
      
      script.write('echo =============================\n')
      script.write('echo Content of mokka.steer:\n')
      script.write('cat mokka.steer\n')
      script.write('echo =============================\n')
      script.write('echo Content of mokkamac.mac:\n')
      script.write('cat mokkamac.mac\n')
      script.write('echo =============================\n')
      script.write('echo LD_LIBRARY_PATH is\n')
      script.write('echo $LD_LIBRARY_PATH | tr ":" "\n"\n')
      script.write('echo =============================\n')
      script.write('echo PATH is\n')
      script.write('echo $PATH | tr ":" "\n"\n')
      script.write('env | sort >> localEnv.log\n')      
      script.write('echo =============================\n')
      
      ##Tear appart this mokka-wrapper
      comm = '%s/Mokka %s -hlocalhost:%s/mysql.sock %s\n'%(myMokkaDir,mokkaextraoption,sqlwrapper.getMokkaTMPDIR(),mokkasteer)
      print "Command : %s"%(comm)
      script.write(comm)
      script.write('declare -x appstatus=$?\n')
      #script.write('where\n')
      #script.write('quit\n')
      #script.write('EOF\n')

      script.write('exit $appstatus\n')

      script.close()
      if os.path.exists(self.applicationLog): os.remove(self.applicationLog)

      os.chmod(scriptName,0755)
      comm = 'sh -c "./%s"' %scriptName
      self.setApplicationStatus('Mokka %s step %s' %(self.applicationVersion,self.STEP_NUMBER))
      self.stdError = ''
      self.result = shellCall(0,comm,callbackFunction=self.redirectLogOutput,bufferLimit=20971520)
      #self.result = {'OK':True,'Value':(0,'Disabled Execution','')}
      resultTuple = self.result['Value']

      status = resultTuple[0]
      # stdOutput = resultTuple[1]
      # stdError = resultTuple[2]
      self.log.info( "Status after Mokka execution is %s" % str( status ) )
      result = sqlwrapper.mysqlCleanUp()
      if not os.path.exists(self.applicationLog):
        self.log.error("Something went terribly wrong, the log file is not present")
        self.setApplicationStatus('%s failed terribly, you are doomed!' %(self.applicationName))
        if not self.ignoreapperrors:
          return S_ERROR('%s did not produce the expected log' %(self.applicationName))
      ###Now change the name of Mokka output to the specified filename
      if os.path.exists("out.slcio"):
        if len(self.outputFile)>0:
          os.rename("out.slcio", self.outputFile)

      failed = False
      if not status == 0 and not status==106 and not status==10:
        self.log.error( "Mokka execution completed with errors:" )
        failed = True
      elif status==106 or status==10:
        self.log.info( "Mokka execution reached end of input generator file")
      else:
        self.log.info( "Mokka execution finished successfully")
        
      message = 'Mokka %s Successful' %(self.applicationVersion)
      if failed==True:
        self.log.error( "==================================\n StdError:\n" )
        self.log.error( self.stdError) 
        #self.setApplicationStatus('%s Exited With Status %s' %(self.applicationName,status))
        self.log.error('Mokka Exited With Status %s' %(status))
        message = 'Mokka Exited With Status %s' %(status)
        self.setApplicationStatus(message)
        if not self.ignoreapperrors:
          return S_ERROR(message)
      else:
        if status==106:
          message = 'Mokka %s reached end of input generator file' %(self.applicationVersion)
        self.setApplicationStatus(message)
      return S_OK(message)

    #############################################################################

    def GenRandString(self, length=8, chars=string.letters + string.digits):
      """Return random string of 8 chars
      """
      return ''.join([choice(chars) for i in range(length)])