from datetime import datetime, timedelta
import copy, os
import yaml
import boto3

import logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

NO_DEFAULT = object()
CACHE_DURATION = 5 * 60

class ConfigManager(object):
    """Processes the config yaml file.  Including features like S3 lookup, processing values as templates and overriding values for specific instances."""
    
    def __init__(self, requestHandler):
        self.requestHandler = requestHandler
        self.globalConfig = None
        self.instanceConfig = None

    def get(self, path, default=NO_DEFAULT, errorMessage="Configuration doesn't include a required setting for {path}.", globalOnly=False, instanceOnly=False):
        if not instanceOnly:
            try:
                return getFromMap(self.getInstanceConfig(), path, NO_DEFAULT)
            except KeyError:
                pass
        
        if not globalOnly:
            try:
                return getFromMap(self.getGlobalConfig(), path, NO_DEFAULT)
            except KeyError:
                pass
        
        if default is NO_DEFAULT:
            raise EnvironmentError(errorMessage.format(path=path))
        else:
            return default

    def getGlobalConfig(self):
        if not self.globalConfig:
            self.initConfigs()
        return self.globalConfig

    def getInstanceConfig(self):
        if not self.instanceConfig:
            self.initConfigs()
        return self.instanceConfig
    
    def initConfigs(self):
        if self.requestHandler.context and type(self.requestHandler.context) is dict and 'test-config' in self.requestHandler.context:
            logger.debug("Using context provided test-config")
            self.globalConfig = self.requestHandler.context['test-config']
        else:
            logger.debug("Loading Config")
            self.globalConfig = loadConfig()
        
        for server in getFromMap(self.globalConfig, "apimInstances"):
            if server['name'] in self.requestHandler.item['callbackUrl']:
                logger.debug("Loading config for " + server['name'])
                self.instanceConfig = server

        if not self.instanceConfig:
            raise EnvironmentError("The callback url " + self.requestHandler.item['callbackUrl'] + " doesn't match any configured APIM instances.")

        self.processProperties(self.globalConfig)
        self.processProperties(self.instanceConfig)

    def processProperties(self, config):
        if 'properties' in config:
            for k,v in config['properties'].items():
                config['properties'][k] = self.requestHandler.processTemplate(v)

cachedConfig = None
configExpires = datetime.now()

def loadConfig():
    global cachedConfig, configExpires
    if not cachedConfig or datetime.now() >= configExpires:
        cachedConfig = getRawConfig()
        configExpires = datetime.now() + timedelta(seconds=CACHE_DURATION)
    
    return copy.deepcopy(cachedConfig)

def getRawConfig():
    if 'ConfigS3' in os.environ:
        configS3Uri = os.environ['ConfigS3']
        logger.debug("Pulling config from %s", configS3Uri)
        resp = getConfigFromS3(configS3Uri)
        if resp:
            logger.debug("Config successfully retrieved from " + configS3Uri)
            return yaml.safe_load(resp['Body'])

    logger.debug("Loading default config file")
    with open("config.yaml", 'r') as stream:
        return yaml.safe_load(stream)
    
def getConfigFromS3(s3path):
    if not s3path.startswith("s3://") or not s3path.endswith(".yaml"):
        raise EnvironmentError("ConfigS3 environment variable must start with s3:// and end with .yaml.  It is " + s3path)

    bucket, key = s3path[len("s3://"):].split("/", 1)

    s3 = boto3.resource('s3')
    obj = s3.Object(bucket,key)

    try:
        return obj.get()
    except botocore.exceptions.ClientError as e:
        logger.debug("Config wasn't found at " + s3path + ". Attempting to upload default config.", exc_info=True)
        try:
            with open("config.yaml", 'r') as stream:
                obj.put(Body=stream)
            logger.debug("Default config uploaded to %s", s3path)
            return obj.get()
        except botocore.exceptions.ClientError as e:
            logger.exception("Couldn't put new default on s3. Will use built in default.")
            return None
    
def getFromMap(sourcemap, key, default=NO_DEFAULT):
    cur = sourcemap
    for p in key.split("/"):
        try:
            cur = cur[p]
        except (KeyError, TypeError):
            if default != NO_DEFAULT:
                return default
            raise
    return cur

