import unittest
import sys, os, logging, copy, json
import boto3

import test_config
import wso2_subscription_approval

testDir = os.path.dirname(__file__)
lambdaDir = os.path.abspath(os.path.join(testDir, "../lambda"))
os.chdir(lambdaDir)

os.environ['SubscriptionTable'] = "mid-apisub-dev-SubTable-8LMVLTGPDK1P"

class TestLambda_handler(unittest.TestCase):
    
    def getTable(self):
        db = boto3.resource('dynamodb')
        return db.Table(os.environ['SubscriptionTable'])
    
    def getItem(self, workflow="testWorkflow1"):
        response = self.getTable().get_item(Key={'workflowReference': workflow})
        return response.get('Item', None)
    
    def setUp(self):
        self.deleteRecords()
        self.getTable().put_item(Item=test_config.testItem)
    
    def tearDown(self):
        self.deleteRecords()
    
    def deleteRecords(self):
        for wf in ['testWorkflow1', 'testWorkflow2']:
            self.getTable().delete_item(Key={'workflowReference': wf})

    def test_post(self):
        self.assertIsNone(self.getItem('testWorkflow2'))
        response = wso2_subscription_approval.post(examplePost, {})
        
        self.assertEqual(response['statusCode'], 200)
        self.assertIn("Subscription Request Accepted", response['body'])
        
        item = self.getItem('testWorkflow2')
        self.assertIsNotNone(item)
        self.assertEqual(item['apiName'], 'BioTest')
        

    def test_invalid_post(self):
        """Tests that the event struture passed in has the required elements"""
        
        testevent = json.loads("""
        {
          "params": {
            "path": {},
            "querystring": {
              "simulate": "True"
            }
          }
        }
        """)
        response = wso2_subscription_approval.post(testevent, {})
        self.assertEqual(response['statusCode'], 400)
    
    def test_get(self):
        """Tests looking up the current status of a request"""
        
        response = wso2_subscription_approval.get(test_config.exampleGet, {})
        self.assertEqual(response['statusCode'], 200)
        self.assertIn("BioTest", response['body'])
        self.assertIn("<html>", response['body'])
        self.assertEqual(response['headers']['Content-Type'], 'text/html')
        

examplePost = {
    u'resource': u'/subscriptionRequests',
    u'requestContext': {
        u'resourceId': u'i9mp34', 
        u'apiId': u'n4zdmn1w9e',
        u'resourcePath': u'/subscriptionRequests',
        u'httpMethod': u'POST',
        u'requestId': u'363c9b25-c320-11e6-9af8-9d9abcfb8998',
        u'accountId': u'XXXXXXXXXX',
        u'stage': u'Prod'},
    u'queryStringParameters': {u'simulate': u'true'},
    u'httpMethod': u'POST',
    u'pathParameters': None,
    u'headers': {
        u'X-Forwarded-Port': u'443',
        u'Host': u'n4zdmn1w9e.execute-api.us-west-2.amazonaws.com',
        u'X-Forwarded-Proto': u'https',
    },
    u'stageVariables': None, 
    u'path': u'/subscriptionRequests', 
    u'isBase64Encoded': False
}

examplePost['body'] = """{
    "subscriberclaims": {
        "http://wso2.org/claims/organization": "org", 
        "http://wso2.org/claims/country": "country", 
        "http://wso2.org/claims/emailaddress": "jsmith@api.com", 
        "http://wso2.org/claims/mobile": "12345", 
        "http://wso2.org/claims/streetaddress": "add", 
        "http://wso2.org/claims/role": "admin,Internal/subscriber,Internal/everyone", 
        "http://wso2.org/claims/telephone": "1234", 
        "http://wso2.org/claims/givenname": "first", 
        "http://wso2.org/claims/lastname": "last"
    }, 
    "apiProvider": "dyl011", 
    "workflowReference": "testWorkflow2", 
    "apiContext": "/biotest/v1", 
    "apiVersion": "v1", 
    "tier": "Unlimited", 
    "apiName": "BioTest", 
    "applicationName": "TestApp",
    "apiTechnicalOwnerName": "Owner, Technical", 
    "apiTechnicalOwnerEmail": "tech@api.com", 
    "apiBusinessOwnerName": "Owner, Business", 
    "apiBusinessOwnerEmail": "business@api.com", 
    "subscriberId": "jsmith", 
    "callbackUrl": "https://api.com:8243/services/WorkflowCallbackService"
}"""

if __name__ == '__main__':
    logging.basicConfig()
    logging.getLogger(__name__).setLevel(logging.DEBUG)
    logger = logging.getLogger(__name__)
    unittest.main()