from DIRAC.Core.Utilities.Subprocess                      import shellCall
from ILCDIRAC.Workflow.Modules.ModuleBase                 import ModuleBase
from ILCDIRAC.Core.Utilities.CombinedSoftwareInstallation import LocalArea,SharedArea
from DIRAC                                                import S_OK, S_ERROR, gLogger
from ILCDIRAC.Core.Utilities.PrepareLibs                  import removeLibc

import DIRAC
import os
import sys

class LCIOConcatenate(ModuleBase):

    def __init__(self):

        ModuleBase.__init__(self)

        self.STEP_NUMBER = ''
        self.log         = gLogger.getSubLogger( "LCIOConcatenate" )
        self.args        = ''
        #self.result      = S_ERROR()
        self.jobID       = None

        # Step parameters

        self.applicationVersion = None
        self.applicationLog     = None
        self.outputSLCIOFile    = None

        #

        if os.environ.has_key('JOBID'):
            self.jobID = os.environ['JOBID']

        #

        print "%s initialized" % ( self.__str__() )

    def execute(self):

        # Get input variables

        result = self._resolveInputVariables()

        if not result['OK']:
            return result

        # Checks

        if not self.systemConfig:
            result = S_ERROR( 'No ILC platform selected' )

        if not os.environ.has_key("LCIO"):
            self.log.error("Environment variable LCIO was not defined, cannot do anything")
            return S_ERROR("Environment variable LCIO was not defined, cannot do anything")

        # removeLibc

        removeLibc( os.path.join( os.environ["LCIO"], "lib" ) )

        # Setting up script

        LD_LIBRARY_PATH = os.path.join( "$LCIO", "lib" )
        if os.environ.has_key('LD_LIBRARY_PATH'):
            LD_LIBRARY_PATH += ":" + os.environ['LD_LIBRARY_PATH']

        PATH = "$LCIO/bin"
        if os.environ.has_key('PATH'):
            PATH += ":" + os.environ['PATH']

        scriptContent = """
#!/bin/sh

################################################################################
# Dynamically generated script by LCIOConcatenate module                       #
################################################################################

declare -x LD_LIBRARY_PATH=%s
declare -x PATH=%s

lcio concat -f *.slcio -o %s

exit $?

""" %(
    LD_LIBRARY_PATH,
    PATH,
    self.outputSLCIOFile
)

        # Write script to file

        scriptPath = 'LCIOConcatenate_%s_Run_%s.tcl' %( self.applicationVersion, self.STEP_NUMBER )

        if os.path.exists(scriptPath):
            os.remove(scriptPath)

        script = open( scriptPath, 'w' )
        script.write( scriptContent )
        script.close()

        # Setup log file for application stdout

        if os.path.exists(self.applicationLog):
            os.remove(self.applicationLog)

        # Run code

        os.chmod( scriptPath, 0755 )

        command = '"./%s"' %( scriptPath )

        self.setApplicationStatus( 'LCIOConcatenate %s step %s' %( self.applicationVersion, self.STEP_NUMBER ) )
        self.stdError = ''

        self.result = shellCall(
            0,
            command,
            callbackFunction = self.redirectLogOutput,
            bufferLimit = 20971520
        )

        # Check results

        resultTuple = self.result['Value']
        status      = resultTuple[0]

        self.log.info( "Status after the application execution is %s" % str( status ) )

        if status:
            self.setApplicationStatus( "LCIOConcatenate Exited With Status %s" % status )
            return S_ERROR( "LCIOConcatenate Exited With Status %s" % status )

        # Return

        self.setApplicationStatus( 'LCIOConcatenate Finished successfully' )
        return S_OK( 'LCIOConcatenate Finished successfully' )

    def redirectLogOutput(self, fd, message):

        sys.stdout.flush()

        if self.applicationLog:

            log = open(self.applicationLog,'a')
            log.write(message+'\n')
            log.close()

        else:
            self.log.error("Application Log file not defined")

        if fd == 1:
            self.stdError += message

    def _resolveInputVariables(self):

        if self.workflow_commons.has_key('SystemConfig'):
            self.systemConfig = self.workflow_commons['SystemConfig']

        if self.step_commons.has_key('applicationVersion'):
            self.applicationVersion = self.step_commons['applicationVersion']

        # Logfile

        if self.step_commons.has_key('applicationLog'):
            self.applicationLog = self.step_commons['applicationLog']

        if not self.applicationLog:
            self.applicationLog = 'LCIOConcatenate_%s_Run_%s.log' %( self.applicationVersion, self.STEP_NUMBER )

        #

        if self.step_commons.has_key('outputSLCIOFile'):
            self.outputSLCIOFile = self.step_commons['outputSLCIOFile']

        if not self.outputSLCIOFile:
            return S_ERROR( 'No output file defined' )

        #

        return S_OK('Parameters resolved')
