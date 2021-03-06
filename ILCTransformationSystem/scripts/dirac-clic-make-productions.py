'''
Create productions for the DDSim/Marlin software chain

Options:

   -p, --printConfigFile      Create the template to create productions
   -f, --configFile <file>    Defines the file with the parameters to create a production
   -x, --enable               Disable dry-run mode and actually create the production
   --additionalName       Define a string to add to the production name if the original name already exists


:since: July 14, 2017
:author: A Sailer
'''

#pylint disable=wrong-import-position

import ConfigParser
import os

from DIRAC.Core.Base import Script
from DIRAC import S_OK, S_ERROR, gLogger

from ILCDIRAC.Core.Utilities.OverlayFiles import energyWithUnit, energyToInt

PRODUCTION_PARAMETERS= 'Production Parameters'
PP= 'Production Parameters'
APPLICATION_LIST = ['Marlin', 'DDSim', 'Overlay', 'Whizard2']
LIST_ATTRIBUTES = ['ignoreMetadata']
STRING_ATTRIBUTES = ['configPackage', 'configVersion']


def listify(value):
  """Turn a comma separate string into a list."""
  if isinstance(value, list):
    return value
  return [val.strip() for val in value.split(',') if val.strip()]


class Params(object):
  """Parameter Object"""
  def __init__(self):
    self.prodConfigFilename = None
    self.dumpConfigFile = False
    self.dryRun = True
    self.additionalName = None

  def setProdConf(self,fileName):
    if not os.path.exists( fileName ):
      return S_ERROR("ERROR: File %r not found" % fileName )
    self.prodConfigFilename = fileName
    return S_OK()
  def setDumpConf(self, _):
    self.dumpConfigFile = True
    return S_OK()
  def setEnable(self, _):
    self.dryRun = False
    return S_OK()
  def setAddName(self, addName):
    self.additionalName = addName
    return S_OK()

  def registerSwitches(self):
    Script.registerSwitch("f:", "configFile=", "Set config file for production", self.setProdConf)
    Script.registerSwitch("x", "enable", "create productions, if off dry-run", self.setEnable)
    Script.registerSwitch("p", "printConfigFile", "Print a config file to stdout", self.setDumpConf)
    Script.registerSwitch("", "additionalName=", "Name to add to the production", self.setAddName)
    Script.setUsageMessage("""%s --configFile=myProduction""" % ("dirac-clic-make-productions", ) )


class CLICDetProdChain( object ):
  """ create applications and productions for clic physics studies 2017


  :param str prodGroup: basename of the production group the productions are part of
  :param str process: name of the process to generate or use in meta data search
  :param str detectorModel: Detector Model to use in simulation/reconstruction
  :param str softwareVersion: softwareVersion to use for generation/simulation/reconstruction
  :param str configVersion: Steering file version to use for simulation/reconstruction
  :param str configPackage: Steering file package to use for simulation/reconstruction
  :param float energy: energy to use for generation or meta data search
  :param in eventsPerJob: number of events per job
  :param in numberOfTasks: number of production jobs/task to create (default is 1)
  :param str productionLogLevel: log level to use in production jobs
  :param str outputSE: output SE for production jobs
  :param str finalOutputSE: final destination for files when moving transformations are enabled
  :param str additionalName: additionalName to add to the transformation name in case a
        transformation with that name already exists
  :param str cliReco: additional CLI options for reconstruction, optional
  :param str whizard2Version: specify which version of Whizard 2 to use, optional
  :param str whizard2SinFile: path to sindarin file to be used with Whizard2

  """

  class Flags( object ):
    """ flags to enable or disable productions

    :param bool dryRun: if False no productions are created
    :param bool gen: if True create generation production
    :param bool spl: if True create split production
    :param bool sim: if True create simulation production
    :param bool rec: if True create reconstruction production
    :param bool over: if True create reconstruction production with overlay, if `rec` is False this flag is also False
    :param bool move: if True create moving transformations, the other move flags only take effect if this one is True
    :param bool moveGen: if True move GEN files after they have been used in the production, also for split files
    :param bool moveSim: if True move SIM files after they have been used in the production
    :param bool moveRev: if True move REC files when they were created
    :param bool moveDst: if True move DST files when they were created
    """

    def __init__( self ):
      # general flag to create anything at all
      self._dryRun = True

      #create transformations
      self._gen = False
      self._spl = False
      self._sim = False
      self._rec = False
      self._over = False

      # create moving transformations
      self._moves = False
      self._moveGen = False
      self._moveSim = False
      self._moveRec = False
      self._moveDst = False

      ## list of tuple to preserve order
      self._prodTypes = [ ('gen', 'Gen'), ('spl', 'Split'), ('sim', 'Sim'), ('rec', 'Rec'), ('over', 'RecOver') ]
      self._moveTypes = [ ('moveGen', 'Gen'), ('moveSim', 'Sim'), ('moveRec', 'Rec'), ('moveDst', 'Dst') ]

    @property
    def dryRun( self ): #pylint: disable=missing-docstring
      return self._dryRun
    @property
    def gen( self ): #pylint: disable=missing-docstring
      return self._gen
    @property
    def spl( self ): #pylint: disable=missing-docstring
      return self._spl
    @property
    def sim( self ): #pylint: disable=missing-docstring
      return self._sim
    @property
    def rec( self ): #pylint: disable=missing-docstring
      return self._rec
    @property
    def over( self ): #pylint: disable=missing-docstring
      return self._over
    @property
    def move( self ): #pylint: disable=missing-docstring
      return not self._dryRun and self._moves
    @property
    def moveGen( self ): #pylint: disable=missing-docstring
      return not self._dryRun and (self._gen or self._spl) and self._moves and self._moveGen
    @property
    def moveSim( self ): #pylint: disable=missing-docstring
      return not self._dryRun and self._sim and self._moves and self._moveSim
    @property
    def moveRec( self ): #pylint: disable=missing-docstring
      return not self._dryRun and (self._rec or self._over) and self._moves and self._moveRec
    @property
    def moveDst( self ): #pylint: disable=missing-docstring
      return not self._dryRun and (self._rec or self._over) and self._moves and self._moveDst


    def __str__( self ):
      pDict = vars(self)
      self.updateDictWithFlags( pDict )
      return """

#Productions to create: %(prodOpts)s
ProdTypes = %(prodTypes)s

move = %(_moves)s

#Datatypes to move: %(moveOpts)s
MoveTypes = %(moveTypes)s
""" %( vars(self) )

    def updateDictWithFlags( self, pDict ):
      """ add flags and values to pDict """
      for attr in dir(self):
        if isinstance( getattr(type(self), attr, None), property):
          pDict.update( { attr: str(getattr(self, attr)) } )

      pDict.update( prodOpts = ", ".join([ pTuple[1] \
                                           for pTuple in self._prodTypes ] ) )
      pDict.update( prodTypes = ", ".join([ pTuple[1] \
                                            for pTuple in self._prodTypes \
                                            if getattr( self, pTuple[0]) ] ) )
      pDict.update( moveOpts = ", ".join([ pTuple[1] \
                                            for pTuple in self._moveTypes ] ) )
      pDict.update( moveTypes = ", ".join([ pTuple[1] \
                                            for pTuple in self._moveTypes \
                                            if getattr( self, '_'+pTuple[0] ) ] ) )


    def __splitStringToOptions( self, config, tuples, optString, prefix='_'):
      """ split the option string into separate values and set the corresponding flag """
      prodsToCreate = config.get( PRODUCTION_PARAMETERS, optString )
      for prodType in prodsToCreate.split(','):
        if not prodType:
          continue
        found = False
        for attribute, name in tuples:
          if name.capitalize() == prodType.strip().capitalize():
            setattr( self, prefix+attribute, True )
            found = True
            break
        if not found:
          raise AttributeError( "Unknown parameter: %r " % prodType )

    def loadFlags( self, config ):
      """ load flags values from configfile """
      self.__splitStringToOptions( config, self._prodTypes, 'ProdTypes', prefix='_' )
      self.__splitStringToOptions( config, self._moveTypes, 'MoveTypes', prefix='_' )
      self._moves = config.getboolean( PP, 'move' )

  def __init__(self, params=None, group='ilc_prod'):

    from DIRAC.ConfigurationSystem.Client.Helpers.Operations import Operations
    self._ops = Operations( vo='ilc' )

    self._machine = {'ilc_prod': 'clic',
                     'fcc_prod': 'fccee',
                     }[group]

    self.prodGroup = 'several'
    prodPath = os.path.join('/Production', self._machine.upper())
    self.basepath = self._ops.getValue(os.path.join(prodPath, 'BasePath'))

    self.detectorModel = self._ops.getValue(os.path.join(prodPath, 'DefaultDetectorModel'))
    self.softwareVersion = self._ops.getValue(os.path.join(prodPath, 'DefaultSoftwareVersion'))
    self.configVersion = self._ops.getValue(os.path.join(prodPath, 'DefaultConfigVersion'))
    self.configPackage = self._ops.getValue(os.path.join(prodPath, 'DefaultConfigPackage'))
    self.productionLogLevel = 'VERBOSE'
    self.outputSE = 'CERN-DST-EOS'

    self.ddsimSteeringFile = 'clic_steer.py'
    self.marlinSteeringFile = 'clicReconstruction.xml'

    self.eventsPerJobs = ''
    self.numberOfTasks = ''
    self.energies = ''
    self.processes = ''
    self.prodIDs = ''
    self.eventsInSplitFiles = ''

    # final destination for files once they have been used
    self.finalOutputSE = self._ops.getValue( 'Production/CLIC/FailOverSE' )

    self.additionalName = params.additionalName

    self.overlayEvents = ''
    self._overlayEventType = None

    self.cliRecoOption = ''
    self.cliReco = ''

    self.whizard2Version = self._ops.getValue('Production/CLIC/DefaultWhizard2Version')
    self.whizard2SinFile = ''

    self.ignoreMetadata = []

    self.applicationOptions = {appName: [] for appName in APPLICATION_LIST}

    self._flags = self.Flags()

    self.loadParameters( params )

    self._flags._dryRun = params.dryRun #pylint: disable=protected-access




  def meta( self, prodID, process, energy ):
    """ return meta data dictionary, always new"""
    metaD = {'ProdID': str(prodID),
             'EvtType': process,
             'Energy' : self.metaEnergy( energy ),
             'Machine': self._machine,
             }
    for key in self.ignoreMetadata:
      metaD.pop(key)
    return metaD



  def loadParameters( self, parameter ):
    """ load parameters from config file """

    if parameter.prodConfigFilename is not None:
      defaultValueDict = vars(self)
      self._flags.updateDictWithFlags( defaultValueDict )
      config = ConfigParser.SafeConfigParser( defaults=defaultValueDict, dict_type=dict )
      config.read( parameter.prodConfigFilename )
      self._flags.loadFlags( config )

      self.prodGroup = config.get(PP, 'prodGroup')
      self.detectorModel = config.get(PP, 'detectorModel')
      self.softwareVersion = config.get(PP, 'softwareVersion')
      if config.has_option(PP, 'clicConfig'):
        self.configVersion = config.get(PP, 'clicConfig')

      # Check if Whizard version is set, otherwise use default from CS
      if config.has_option(PP, 'whizard2Version'):
        self.whizard2Version = config.get(PP, 'whizard2Version')

      if config.has_option(PP, 'whizard2SinFile'):
        self.whizard2SinFile = config.get(PP, 'whizard2SinFile').replace(' ', '').split(',')

      self.processes = config.get(PP, 'processes').split(',')
      self.energies = config.get(PP, 'energies').split(',')
      self.eventsPerJobs = config.get(PP, 'eventsPerJobs').split(',')
      if config.has_option(PP, 'numberOfTasks'):
        self.numberOfTasks = config.get(PP, 'numberOfTasks').split(',')
      else:
        self.numberOfTasks = []

      self.productionLogLevel = config.get(PP, 'productionloglevel')
      self.outputSE = config.get(PP, 'outputSE')

      # final destination for files once they have been used
      self.finalOutputSE = config.get(PP, 'finalOutputSE')

      if config.has_option(PP, 'additionalName'):
        self.additionalName = config.get(PP, 'additionalName')

      if config.has_option(PP, 'cliReco'):
        self.cliRecoOption = config.get(PP, 'cliReco')

      for attribute in LIST_ATTRIBUTES:
        if config.has_option(PP, attribute):
          setattr(self, attribute, listify(config.get(PP, attribute)))

      for attribute in STRING_ATTRIBUTES:
        if config.has_option(PP, attribute):
          setattr(self, attribute, config.get(PP, attribute))

      self.overlayEvents = self.checkOverlayParameter(config.get(PP, 'overlayEvents')) \
                           if config.has_option(PP, 'overlayEvents') else ''

      self._overlayEventType = 'gghad' + self.overlayEvents.lower()

      if config.has_option(PP, 'prodIDs'):
        self.prodIDs = config.get(PP, 'prodIDs').split(',')
      else:
        self.prodIDs = []

      ##for split only
      self.eventsInSplitFiles = config.get(PP, 'eventsInSplitFiles').split(',')

      self.processes = [ process.strip() for process in self.processes if process.strip() ]
      self.energies = [ float(eng.strip()) for eng in self.energies if eng.strip() ]
      self.eventsPerJobs = [ int( epj.strip() ) for epj in self.eventsPerJobs if epj.strip() ]
      ## these do not have to exist so we fill them to the same length if they are not set
      self.prodIDs = [ int( pID.strip() ) for pID in self.prodIDs if pID.strip() ]
      self.prodIDs = self.prodIDs if self.prodIDs else [ 1 for _ in self.energies ]

      # if one of the lists only has size 1 and there is a longer list we extend
      # the list to the maximum size assuming the values are re-used
      maxLength = 0
      parameterLists = [self.processes, self.energies, self.eventsPerJobs, self.whizard2SinFile]
      for parList in parameterLists:
        maxLength = len(parList) if len(parList) > maxLength else maxLength
      for parList in parameterLists:
        if len(parList) == 1 and maxLength > 1:
          parList.extend([parList[0]] * (maxLength - 1))

      if not (self.processes and self.energies and self.eventsPerJobs) and self.prodIDs:
        eventsPerJobSave = list(self.eventsPerJobs) if self.eventsPerJobs else None
        self._getProdInfoFromIDs()
        self.eventsPerJobs = eventsPerJobSave if eventsPerJobSave else self.eventsPerJobs

      self.numberOfTasks = [int(nbtask.strip()) for nbtask in self.numberOfTasks if nbtask.strip()]
      self.numberOfTasks = self.numberOfTasks if self.numberOfTasks else [1 for _ in self.energies]

      if len(self.processes) != len(self.energies) or \
         len(self.energies) != len(self.eventsPerJobs) or \
         len( self.prodIDs) != len(self.eventsPerJobs):
        raise AttributeError( "Lengths of Processes, Energies, and EventsPerJobs do not match" )

      if self._flags.gen:
        if len(self.numberOfTasks) != len(self.energies) or \
           len(self.whizard2SinFile) != len(self.energies):
          raise AttributeError("Lengths of numberOfTasks, whizard2SinFile, and Energies do not match")

      self.eventsInSplitFiles = [ int( epb.strip() ) for epb in self.eventsInSplitFiles if epb.strip() ]
      self.eventsInSplitFiles = self.eventsInSplitFiles if self.eventsInSplitFiles else [ -1 for _ in self.energies ]

      if self._flags.spl and len(self.eventsInSplitFiles) != len(self.energies):
        raise AttributeError( "Length of eventsInSplitFiles does not match: %d vs %d" %(
          len(self.eventsInSplitFiles), \
          len(self.energies) ) )

      # read options from application sections
      config2 = ConfigParser.SafeConfigParser(dict_type=dict)
      config2.optionxform = str  # do not transform options to lowercase
      config2.read(parameter.prodConfigFilename)
      for appName in APPLICATION_LIST:
        try:
          self.applicationOptions[appName] = config2.items(appName)
        except ConfigParser.NoSectionError:
          pass

    if parameter.dumpConfigFile:
      print self
      raise RuntimeError('')

  def _getProdInfoFromIDs(self):
    """get the processName, energy and eventsPerJob from the MetaData catalog

    :raises: AttributeError if some of the information cannot be found
    :returns: None
    """
    if not self.prodIDs:
      raise AttributeError("No prodIDs defined")

    self.eventsPerJobs = []
    self.processes = []
    self.energies = []
    from DIRAC.TransformationSystem.Client.TransformationClient import TransformationClient
    from DIRAC.Resources.Catalog.FileCatalogClient import FileCatalogClient
    trc = TransformationClient()
    fc = FileCatalogClient()
    for prodID in self.prodIDs:
      gLogger.notice("Getting information for %s" % prodID)
      tRes = trc.getTransformation(str(prodID))
      if not tRes['OK']:
        raise AttributeError("No prodInfo found for %s" % prodID)
      self.eventsPerJobs.append(int(tRes['Value']['EventsPerTask']))
      lfnRes = fc.findFilesByMetadata({'ProdID': prodID})
      if not lfnRes['OK'] or not lfnRes['Value']:
        raise AttributeError("Could not find files for %s: %s " % (prodID, lfnRes.get('Message', lfnRes.get('Value'))))
      path = os.path.dirname(lfnRes['Value'][0])
      fileRes = fc.getDirectoryUserMetadata(path)
      self.processes.append(fileRes['Value']['EvtType'])
      self.energies.append(fileRes['Value']['Energy'])
      gLogger.notice("Found (Evts,Type,Energy): %s %s %s " %
                     (self.eventsPerJobs[-1], self.processes[-1], self.energies[-1]))

  def _productionName( self, metaDict, parameterDict, prodType ):
    """ create the production name """
    workflowName = "%s_%s_clic_%s" %( parameterDict['process'],
                                      metaDict['Energy'],
                                      prodType,
                                    )
    if isinstance( self.additionalName, basestring):
      workflowName += "_" + self.additionalName
    return workflowName

  def __str__( self ):
    pDict = vars(self)
    appOptionString = ''
    for appName in APPLICATION_LIST:
      appOptionString += '[%s]\n#ApplicationAttributeName=Value\n\n' % appName

    pDict.update({'ProductionParameters':PRODUCTION_PARAMETERS})
    pDict.update({'ApplicationOptions': appOptionString})
    return """
%(ApplicationOptions)s
[%(ProductionParameters)s]
prodGroup = %(prodGroup)s
detectorModel = %(detectorModel)s
softwareVersion = %(softwareVersion)s
whizard2Version = %(whizard2Version)s
whizard2SinFile = %(whizard2SinFile)s
configVersion = %(configVersion)s
configPackage = %(configPackage)s
eventsPerJobs = %(eventsPerJobs)s
## Number of jobs/task to generate (default = 1)
# numberOfTasks =

energies = %(energies)s
processes = %(processes)s
## optional prodid to search for input files
# prodIDs =

## number of events for input files to split productions
eventsInSplitFiles = %(eventsInSplitFiles)s

productionLogLevel = %(productionLogLevel)s
outputSE = %(outputSE)s

finalOutputSE = %(finalOutputSE)s

## optional additional name
# additionalName = %(additionalName)s

## optional marlin CLI options
# cliReco = %(cliReco)s

## optional energy to use for overlay: e.g. 3TeV
# overlayEvents = %(overlayEvents)s


%(_flags)s


""" %( pDict )

  @staticmethod
  def metaEnergy(energy):
    """Return string of the energy with no non-zero digits."""
    if isinstance(energy, basestring):
      return energy
    energy = ("%1.2f" % energy).rstrip('0').rstrip('.')
    return energy

  @staticmethod
  def checkOverlayParameter( overlayParameter ):
    """ check that the overlay parameter has the right formatting, XTeV or YYYGeV """
    if not overlayParameter:
      return overlayParameter
    if not any( overlayParameter.endswith( unit ) for unit in ('GeV', 'TeV') ):
      raise RuntimeError( "OverlayParameter %r does not end with unit: X.YTeV, ABCGeV" % overlayParameter )

    return overlayParameter


  @staticmethod
  def getParameterDictionary( process ):
    """ Create the proper structures to build all the prodcutions for the samples with *ee_*, *ea_*, *aa_*. """
    plist = []
    if 'ee_' in process:
      plist.append({'process': process,'pname1':'e1', 'pname2':'E1', "epa_b1":'F', "epa_b2":'F', "isr_b1":'T', "isr_b2":'T'})
    elif 'ea_' in process:
      plist.append({'process': process,'pname1':'e1', 'pname2':'E1', "epa_b1":'F', "epa_b2":'T', "isr_b1":'T', "isr_b2":'F'})
      plist.append({'process': process,'pname1':'e1', 'pname2':'A', "epa_b1":'F', "epa_b2":'F', "isr_b1":'T', "isr_b2":'F'})
      plist.append({'process': process.replace("ea_","ae_"),'pname1':'e1', 'pname2':'E1', "epa_b1":'T', "epa_b2":'F', "isr_b1":'F', "isr_b2":'T'})
      plist.append({'process': process.replace("ea_","ae_"),'pname1':'A', 'pname2':'E1', "epa_b1":'F', "epa_b2":'F', "isr_b1":'F', "isr_b2":'T'})
    elif 'aa_' in process:
      plist.append({'process':process,'pname1':'e1', 'pname2':'E1', "epa_b1":'T', "epa_b2":'T', "isr_b1":'F', "isr_b2":'F'})
      plist.append({'process':process,'pname1':'e1', 'pname2':'A', "epa_b1":'T', "epa_b2":'F', "isr_b1":'F', "isr_b2":'F'})
      plist.append({'process':process,'pname1':'A', 'pname2':'E1', "epa_b1":'F', "epa_b2":'T', "isr_b1":'F', "isr_b2":'F'})
      plist.append({'process':process,'pname1':'A', 'pname2':'A', "epa_b1":'F', "epa_b2":'F', "isr_b1":'F', "isr_b2":'F'})
    else:
      plist.append({'process':process,'pname1':'e1', 'pname2':'E1', "epa_b1":'F', "epa_b2":'F', "isr_b1":'T', "isr_b2":'T'})
    return plist

  @staticmethod
  def overlayParameterDict():
    """ return dictionary that sets the parameters for the overlay application

    keys are float or int
    values are lambda functions acting on an overlay application object
    """

    return {
      350. : ( lambda overlay: [ overlay.setBXOverlay( 30 ), overlay.setGGToHadInt( 0.0464 ), overlay.setProcessorName( 'Overlay350GeV') ] ),
      380. : ( lambda overlay: [ overlay.setBXOverlay( 30 ), overlay.setGGToHadInt( 0.0464 ), overlay.setProcessorName( 'Overlay380GeV') ] ),
      420. : ( lambda overlay: [ overlay.setBXOverlay( 30 ), overlay.setGGToHadInt( 0.17 ),   overlay.setProcessorName( 'Overlay420GeV') ] ),
      500. : ( lambda overlay: [ overlay.setBXOverlay( 30 ), overlay.setGGToHadInt( 0.3 ),    overlay.setProcessorName( 'Overlay500GeV') ] ),
      1400.: ( lambda overlay: [ overlay.setBXOverlay( 30 ), overlay.setGGToHadInt( 1.3 ),    overlay.setProcessorName( 'Overlay1.4TeV') ] ),
      3000.: ( lambda overlay: [ overlay.setBXOverlay( 30 ), overlay.setGGToHadInt( 3.2 ),    overlay.setProcessorName( 'Overlay3TeV') ] ),
    }

  @staticmethod
  def createSplitApplication( eventsPerJob, eventsPerBaseFile, splitType='stdhep' ):
    """ create Split application """
    from ILCDIRAC.Interfaces.API.NewInterface.Applications import StdHepSplit, SLCIOSplit

    if splitType.lower() == 'stdhep':
      stdhepsplit = StdHepSplit()
      stdhepsplit.setVersion("V3")
      stdhepsplit.setNumberOfEventsPerFile( eventsPerJob )
      stdhepsplit.datatype = 'gen'
      stdhepsplit.setMaxRead( eventsPerBaseFile )
      return stdhepsplit

    if  splitType.lower() == 'lcio':
      split = SLCIOSplit()
      split.setNumberOfEventsPerFile( eventsPerJob )
      return stdhepsplit

    raise NotImplementedError( 'unknown splitType: %s ' % splitType )

  def addOverlayOptionsToMarlin( self, energy ):
    """ add options to marlin that are needed for running with overlay """
    energyString = self.overlayEvents if self.overlayEvents else energyWithUnit( energy )
    self.cliReco += ' --Config.Overlay=%s ' % energyString

  def createWhizard2Application(self, meta, eventsPerJob, sinFile):
    """ create Whizard2 Application """
    from ILCDIRAC.Interfaces.API.NewInterface.Applications import Whizard2

    whiz = Whizard2()
    whiz.setVersion(self.whizard2Version)
    whiz.setSinFile(sinFile)
    whiz.setEvtType(meta['EvtType'])
    whiz.setNumberOfEvents(eventsPerJob)
    whiz.setEnergy(meta['Energy'])
    self._setApplicationOptions("Whizard2", whiz)

    return whiz

  def createDDSimApplication( self ):
    """ create DDSim Application """
    from ILCDIRAC.Interfaces.API.NewInterface.Applications import DDSim

    ddsim = DDSim()
    ddsim.setVersion( self.softwareVersion )
    ddsim.setSteeringFile(self.ddsimSteeringFile)
    ddsim.setDetectorModel( self.detectorModel )

    self._setApplicationOptions("DDSim", ddsim)

    return ddsim

  def createOverlayApplication( self, energy ):
    """ create Overlay Application """
    from ILCDIRAC.Interfaces.API.NewInterface.Applications import OverlayInput
    overlay = OverlayInput()
    overlay.setMachine( 'clic_opt' )
    overlay.setEnergy( energy )
    overlay.setBackgroundType( self._overlayEventType )
    overlay.setDetectorModel( self.detectorModel )
    try:
      overlayEnergy = energyToInt( self.overlayEvents ) if self.overlayEvents else energy
      self.overlayParameterDict().get( overlayEnergy ) ( overlay )
    except TypeError:
      raise RuntimeError( "No overlay parameters defined for %r GeV and %s " % ( energy, self._overlayEventType ) )

    if self.overlayEvents:
      overlay.setUseEnergyForFileLookup( False )

    self._setApplicationOptions("Overlay", overlay)

    return overlay

  def createMarlinApplication(self, energy, over):
    """ create Marlin Application without overlay """
    from ILCDIRAC.Interfaces.API.NewInterface.Applications import Marlin
    marlin = Marlin()
    marlin.setDebug()
    marlin.setVersion( self.softwareVersion )
    marlin.setDetectorModel( self.detectorModel )
    marlin.detectortype = self.detectorModel

    if over:
      self.addOverlayOptionsToMarlin( energy )

    self.cliReco = ' '.join([self.cliRecoOption, self.cliReco])
    marlin.setExtraCLIArguments(self.cliReco)
    self.cliReco = ''

    marlin.setSteeringFile(self.marlinSteeringFile)

    self._setApplicationOptions("Marlin", marlin)

    return marlin

  def createGenerationProduction(self, meta, prodName, parameterDict, eventsPerJob, nbTasks, sinFile):
    """ create generation production """
    gLogger.notice("*" * 80 + "\nCreating generation production: %s " % prodName)
    genProd = self.getProductionJob()
    genProd.setProdType('MCGeneration')
    genProd.setWorkflowName(self._productionName(meta, parameterDict, 'gen'))
    # Add the application
    res = genProd.append(self.createWhizard2Application(meta, eventsPerJob, sinFile))
    if not res['OK']:
      raise RuntimeError("Error creating generation production: %s" % res['Message'])
    genProd.addFinalization(True, True, True, True)
    if not prodName:
      raise RuntimeError("Error creating generation production: prodName empty")
    genProd.setDescription(prodName)
    res = genProd.createProduction()
    if not res['OK']:
      raise RuntimeError("Error creating generation production: %s" % res['Message'])

    genProd.addMetadataToFinalFiles({'BeamParticle1': parameterDict['pname1'],
                                     'BeamParticle2': parameterDict['pname2'],
                                     'EPA_B1': parameterDict['epa_b1'],
                                     'EPA_B2': parameterDict['epa_b2'],
                                    }
                                   )

    res = genProd.finalizeProd()
    if not res['OK']:
      raise RuntimeError("Error finalizing generation production: %s" % res['Message'])

    genProd.setNbOfTasks(nbTasks)
    generationMeta = genProd.getMetadata()
    return generationMeta

  def createSimulationProduction( self, meta, prodName, parameterDict ):
    """ create simulation production """
    gLogger.notice( "*"*80 + "\nCreating simulation production: %s " % prodName )
    simProd = self.getProductionJob()
    simProd.setProdType( 'MCSimulation' )
    simProd.setConfigPackage(appName=self.configPackage, version=self.configVersion)
    res = simProd.setInputDataQuery( meta )
    if not res['OK']:
      raise RuntimeError( "Error creating Simulation Production: %s" % res['Message'] )
    simProd.setWorkflowName( self._productionName( meta, parameterDict, 'sim') )
    #Add the application
    res = simProd.append( self.createDDSimApplication() )
    if not res['OK']:
      raise RuntimeError( "Error creating simulation Production: %s" % res[ 'Message' ] )
    simProd.addFinalization(True,True,True,True)
    description = "Model: %s" % self.detectorModel
    if prodName:
      description += ", %s"%prodName
    simProd.setDescription( description )
    res = simProd.createProduction()
    if not res['OK']:
      raise RuntimeError( "Error creating simulation production: %s" % res['Message'] )

    simProd.addMetadataToFinalFiles( { 'BeamParticle1': parameterDict['pname1'],
                                       'BeamParticle2': parameterDict['pname2'],
                                       'EPA_B1': parameterDict['epa_b1'],
                                       'EPA_B2': parameterDict['epa_b2'],
                                     }
                                   )

    res = simProd.finalizeProd()
    if not res['OK']:
      raise RuntimeError( "Error finalizing simulation production: %s" % res[ 'Message' ] )

    simulationMeta = simProd.getMetadata()
    return simulationMeta

  def createReconstructionProduction(self, meta, prodName, parameterDict, over):
    """ create reconstruction production """
    gLogger.notice("*" * 80 + "\nCreating %s reconstruction production: %s " % ('overlay' if over else '', prodName))
    recProd = self.getProductionJob()
    productionType = 'MCReconstruction_Overlay' if over else 'MCReconstruction'
    recProd.setProdType( productionType )
    recProd.setConfigPackage(appName=self.configPackage, version=self.configVersion)

    res = recProd.setInputDataQuery( meta )
    if not res['OK']:
      raise RuntimeError( "Error setting inputDataQuery for Reconstruction production: %s " % res['Message'] )

    recType = 'rec_overlay' if over else 'rec'
    recProd.setWorkflowName( self._productionName( meta, parameterDict, recType ) )

    #Add overlay if needed
    if over:
      print "adding overlay", over
      res = recProd.append( self.createOverlayApplication( float( meta['Energy'] ) ) )
      if not res['OK']:
        raise RuntimeError( "Error appending overlay to reconstruction transformation: %s" % res['Message'] )

    #Add reconstruction
    res = recProd.append(self.createMarlinApplication(float(meta['Energy']), over))
    if not res['OK']:
      raise RuntimeError( "Error appending Marlin to reconstruction production: %s" % res['Message'] )
    recProd.addFinalization(True,True,True,True)

    description = "CLICDet2017 %s" % meta['Energy']
    description += "Overlay" if over else "No Overlay"
    if prodName:
      description += ", %s"%prodName
    recProd.setDescription( description )

    res = recProd.createProduction()
    if not res['OK']:
      raise RuntimeError( "Error creating reconstruction production: %s" % res['Message'] )

    recProd.addMetadataToFinalFiles( { 'BeamParticle1': parameterDict['pname1'],
                                       'BeamParticle2': parameterDict['pname2'],
                                       'EPA_B1': parameterDict['epa_b1'],
                                       'EPA_B2': parameterDict['epa_b2'],
                                     }
                                   )

    res = recProd.finalizeProd()
    if not res['OK']:
      raise RuntimeError( "Error finalising reconstruction production: %s " % res['Message'] )

    reconstructionMeta = recProd.getMetadata()
    return reconstructionMeta

  def createSplitProduction( self, meta, prodName, parameterDict, eventsPerJob, eventsPerBaseFile, limited=False ):
    """ create splitting transformation for splitting files """
    gLogger.notice( "*"*80 + "\nCreating split production: %s " % prodName )
    splitProd = self.getProductionJob()
    splitProd.setProdPlugin( 'Limited' if limited else 'Standard' )
    splitProd.setProdType( 'Split' )

    res = splitProd.setInputDataQuery(meta)
    if not res['OK']:
      raise RuntimeError( 'Split production: failed to set inputDataQuery: %s' % res['Message'] )
    splitProd.setWorkflowName( self._productionName( meta, parameterDict, 'stdhepSplit' ) )

    #Add the application
    res = splitProd.append( self.createSplitApplication( eventsPerJob, eventsPerBaseFile, 'stdhep' ) )
    if not res['OK']:
      raise RuntimeError( 'Split production: failed to append application: %s' % res['Message'] )
    splitProd.addFinalization(True,True,True,True)
    description = 'Splitting stdhep files'

    splitProd.setDescription( description )

    res = splitProd.createProduction()
    if not res['OK']:
      raise RuntimeError( "Failed to create split production: %s " % res['Message'] )

    splitProd.addMetadataToFinalFiles( { "BeamParticle1": parameterDict['pname1'],
                                         "BeamParticle2": parameterDict['pname2'],
                                         "EPA_B1": parameterDict['epa_b1'],
                                         "EPA_B2": parameterDict['epa_b2'],
                                       }
                                     )

    res = splitProd.finalizeProd()
    if not res['OK']:
      raise RuntimeError( 'Split production: failed to finalize: %s' % res['Message'] )

    return splitProd.getMetadata()


  def createMovingTransformation( self, meta, prodType ):
    """ create moving transformations for output files """

    sourceSE = self.outputSE
    targetSE = self.finalOutputSE
    prodID = meta['ProdID']
    try:
      dataTypes = { 'MCReconstruction': ('DST', 'REC'),
                    'MCReconstruction_Overlay': ('DST', 'REC'),
                    'MCSimulation': ('SIM',),
                    'MCGeneration': ('GEN',),
                  }[prodType]
    except KeyError:
      raise RuntimeError( "ERROR creating MovingTransformation" + repr(prodType) + "unknown" )

    if not any( getattr( self._flags, "move%s" % dataType.capitalize() ) for dataType in dataTypes ):
      gLogger.notice( "*"*80 + "\nNot creating moving transformation for prodID: %s, %s " % (meta['ProdID'], prodType ) )
      return

    from ILCDIRAC.ILCTransformationSystem.Utilities.DataTransformation import createDataTransformation
    for dataType in dataTypes:
      if getattr( self._flags, "move%s" % dataType.capitalize() ):
        gLogger.notice( "*"*80 + "\nCreating moving transformation for prodID: %s, %s, %s " % (meta['ProdID'], prodType, dataType ) )
        createDataTransformation('Moving', targetSE, sourceSE, prodID, dataType)

  def getProductionJob(self):
    """ return production job instance with some parameters set """
    from ILCDIRAC.Interfaces.API.NewInterface.ProductionJob import ProductionJob
    prodJob = ProductionJob()
    prodJob.setLogLevel(self.productionLogLevel)
    prodJob.setProdGroup(self.prodGroup)
    prodJob.setOutputSE(self.outputSE)
    prodJob.basepath = self.basepath
    prodJob.dryrun = self._flags.dryRun
    return prodJob

  def _updateMeta(self, outputDict, inputDict, eventsPerJob):
    """ add some values from the inputDict to the outputDict to fake the input dataquery result in dryRun mode """
    if not self._flags.dryRun:
      outputDict.clear()
      outputDict.update( inputDict )
      return

    for key, value in inputDict.iteritems():
      if key not in outputDict:
        outputDict[ key ] = value
    outputDict['NumberOfEvents'] = eventsPerJob

  def _setApplicationOptions(self, appName, app):
    """ set options for given application

    :param str appName: name of the application, for print out
    :param app: application instance
    """

    for option, value in self.applicationOptions[appName]:
      gLogger.notice("%s: setting option %s to %s" % (appName, option, value))
      setterFunc = 'set' + option
      if not hasattr(app, setterFunc):
        raise AttributeError("Cannot set %s for %s, check spelling!" % (option, appName))
      getattr(app, setterFunc)(value)

  def createTransformations(self, metaInput, sinFile, eventsPerJob, nbTasks, eventsPerBaseFile):
    """ create all the transformations we want to create """

    prodName = metaInput['EvtType']

    for parameterDict in self.getParameterDictionary( prodName ):
      splitMeta, genMeta, simMeta, recMeta, overMeta = None, None, None, None, None

      if self._flags.gen:
        genMeta = self.createGenerationProduction(metaInput, prodName, parameterDict, eventsPerJob,
                                                  nbTasks, sinFile)
        self._updateMeta(metaInput, genMeta, eventsPerJob)

      if self._flags.spl and eventsPerBaseFile == eventsPerJob:
        gLogger.notice("*" * 80 + "\nSkipping split transformation for %s\n" % prodName + "*" * 80)
      elif self._flags.spl:
        splitMeta = self.createSplitProduction( metaInput, prodName, parameterDict, eventsPerJob,
                                                eventsPerBaseFile, limited=False )
        self._updateMeta( metaInput, splitMeta, eventsPerJob )

      if self._flags.sim:
        simMeta = self.createSimulationProduction( metaInput, prodName, parameterDict )
        self._updateMeta( metaInput, simMeta, eventsPerJob )

      if self._flags.rec:
        recMeta = self.createReconstructionProduction(metaInput, prodName, parameterDict, over=False)

      if self._flags.over:
        overMeta = self.createReconstructionProduction(metaInput, prodName, parameterDict, over=True)

      if genMeta:
        self.createMovingTransformation(genMeta, 'MCGeneration')

      if splitMeta:
        self.createMovingTransformation( splitMeta, 'MCGeneration' )

      if simMeta:
        self.createMovingTransformation( simMeta, 'MCSimulation' )

      if recMeta:
        self.createMovingTransformation( recMeta, 'MCReconstruction' )

      if overMeta:
        self.createMovingTransformation(overMeta, 'MCReconstruction_Overlay')


  def createAllTransformations( self ):
    """ loop over the list of processes, energies and possibly prodIDs to create all the productions """

    for index, energy in enumerate( self.energies ):

      process = self.processes[index]
      prodID = self.prodIDs[index]
      eventsPerJob = self.eventsPerJobs[index]
      eventsPerBaseFile = self.eventsInSplitFiles[index]
      sinFile = self.whizard2SinFile[index] if self._flags.gen else ''
      nbTasks = self.numberOfTasks[index] if self._flags.gen else -1

      metaInput = self.meta(prodID, process, energy)
      self.createTransformations(metaInput, sinFile, eventsPerJob, nbTasks, eventsPerBaseFile)





if __name__ == "__main__":
  CLIP = Params()
  CLIP.registerSwitches()
  Script.parseCommandLine()
  from ILCDIRAC.Core.Utilities.CheckAndGetProdProxy import checkOrGetGroupProxy
  CHECKGROUP = checkOrGetGroupProxy(['ilc_prod', 'fcc_prod'])
  if not CHECKGROUP['OK']:
    exit(1)
  try:
    CHAIN = CLICDetProdChain(params=CLIP, group=CHECKGROUP['Value'])
    CHAIN.createAllTransformations()
  except (AttributeError, RuntimeError) as excp:
    if str(excp) != '':
      print "Failure to create transformations", repr(excp)
