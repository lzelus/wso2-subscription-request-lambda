from unittest import TestCase
import unittest
import sys, os, logging, copy

try:
    import wso2_subscription_approval
except ImportError:
    testdir = os.path.dirname(__file__)
    sys.path.insert(0, os.path.abspath(os.path.join(testdir, "../lambda")))
    import wso2_subscription_approval

from wso2_subscription_approval import *

class TestConfig(TestCase):

    def setUp(self):
        self.longMessage = True
    
    def test_basics(self):
        handler = makeDefaultHandler()

        self.assertEquals('testValue', handler.config.get('testKey'), "Simple lookup")
        self.assertEquals('defaultValue', handler.config.get('missingKey', 'defaultValue'), "Checking with default value.")

        with self.assertRaises(EnvironmentError):
            handler.config.get('missingKey')

    def test_apimInstance(self):
        handler = makeDefaultHandler()

        self.assertEquals('testValue', handler.config.get('testKey'))

        handler = makeDefaultHandler()
        handler.item['callbackUrl'] = "https://override.com:8243/services/WorkflowCallbackService"
        self.assertEquals('overriddenValue', handler.config.get('testKey'))
        
        with self.assertRaises(EnvironmentError):
            handler.config.get('missingKey')
    

class TestEmail(TestCase):
    
    def setUp(self):
        self.longMessage = True
        self.emails = []
    
    def makeHandler(self, event=None, context=None):
        handler = makeDefaultHandler(event,context)
        import types
        handler.sendEmail = types.MethodType(self.sendEmail, handler)
        return handler
    
    def sendEmail(self, requestHandler, to, subject, text, html):
        self.emails.append((to, subject, text, html))
    
    def getEmailTargets(self):
        return set([to for (to, subject, text, html) in self.emails])
        
    def test_NewRequestEmails(self):
        h = self.makeHandler()
        h.sendNewRequestEmails()
        self.assertEquals({'business@api.com', 'tech@api.com', 'jsmith@api.com'}, self.getEmailTargets())
    
    def test_SendNoOwnerEmail(self):
        h = self.makeHandler()
        h.item['apiBusinessOwnerEmail'] = ''
        h.item['apiTechnicalOwnerEmail'] = ''
        
        h.sendNewRequestEmails()
        
        self.assertEquals(2, len(self.emails), "Two emails should have been sent, no-owner and subscriber")
        (to, subject, text, html) = self.emails[0]
        self.assertEquals('no-owner@api.com', to)
    
    def test_RestrictedEmails(self):
        h = self.makeHandler()
        h.context['test-config']['permitted_emails'] = ['te.*@api.com']
        h.sendNewRequestEmails()
        self.assertEquals({'tech@api.com'}, self.getEmailTargets(), "The only email sent should be to tech")

        h = self.makeHandler()
        h.context['test-config']['permitted_emails'] = ['te.*@api.com']
        h.context['test-config']['fallback_email'] = 'fallback@api.com'
        h.sendNewRequestEmails()
        self.assertEquals({'tech@api.com', 'fallback@api.com'}, self.getEmailTargets(), "The only email sent should be to tech")
    
    def test_CompletedRequestEmails(self):
        h = self.makeHandler()
        h.item['approver'] = "tech@api.com"
        h.item['status'] = 'APPROVED'
        h.sendCompletedRequestEmails()
        self.assertEquals({'business@api.com', 'tech@api.com', 'jsmith@api.com'}, self.getEmailTargets())

def makeDefaultHandler(event=None, context=None):
    if not event:
        event = copy.deepcopy(exampleGet)
    
    if not context:
        context = copy.deepcopy(testContext)
    
    handler = wso2_subscription_approval.RequestHandler(event, context)
    handler.item = copy.deepcopy(testItem)
    return handler


import yaml
testconfig = yaml.load("""
testKey: testValue
no_owner_email_address: no-owner@api.com
properties:
  subscriber_email: |
      #if(${request.subscriberclaims["http://wso2.org/claims/emailaddress"]})${request.subscriberclaims["http://wso2.org/claims/emailaddress"]}#end
 
apimInstances:
    - name: api.com
    
    - name: override.com
      testKey: overriddenValue

templates:
    business_owner_request: &business_owner_request
        subject: Sample Subject
        html: Sample HTML
    
    technical_owner_request: *business_owner_request
    no_owner_request: *business_owner_request
    
    subscriber_request:
        subject: Sub Request
        text: |
            Your request to subscribe ${request.applicationName} to ${request.apiName} has been recieved.
    
    request_approver: *business_owner_request
    request_approval: *business_owner_request
    request_rejecter: *business_owner_request
    request_rejection: *business_owner_request
    subscriber_request_approval: *business_owner_request
    subscriber_request_rejected: *business_owner_request
""")

testContext = {
    'test-config': testconfig
}

testItem = {
    "applicationName": "TestApp", 
    "subscriberclaims": {
        "http://wso2.org/claims/pid": "PID1234", 
        "http://wso2.org/claims/lastname": "Smith", 
        "http://wso2.org/claims/eid": "EID1234", 
        "http://wso2.org/claims/role": "Internal/everyone", 
        "http://wso2.org/claims/networkuserid": "jsmith", 
        "http://wso2.org/claims/emailaddress": "jsmith@api.com", 
        "http://wso2.org/claims/adusername": "-", 
        "http://wso2.org/claims/givenname": "John", 
    }, 
    "apiProvider": "dyl011", 
    "workflowReference": "da2c82ab-009d-4af1-8d24-3524d318af85", 
    "apiContext": "/ims/v1", 
    "apiVersion": "v1", 
    "tier": "Unlimited", 
    "apiName": "BioTest", 
    "apiTechnicalOwnerName": "Owner, Technical", 
    "apiTechnicalOwnerEmail": "tech@api.com", 
    "apiBusinessOwnerName": "Owner, Business", 
    "apiBusinessOwnerEmail": "business@api.com", 
    "subscriberId": "jsmith", 
    "callbackUrl": "https://api.com:8243/services/WorkflowCallbackService"
}


exampleGet = {
    u'body': None,
        u'resource': u'/subscriptionRequests/{workflowReference}',
        u'requestContext': {
            u'resourceId': u'86aip8',
            u'apiId': u'n4zdmn1w9e',
            u'resourcePath': u'/subscriptionRequests/{workflowReference}', 
            u'httpMethod': u'GET', 
            u'requestId': u'cd2d87db-c303-11e6-b8dc-613344667c2c', 
            u'accountId': u'693896114532', 
            u'identity': {
                u'apiKey': None, 
                u'userArn': None, 
                u'cognitoAuthenticationType': None, 
                u'accessKey': None, 
                u'caller': None, 
                u'userAgent': u'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/54.0.2840.98 Safari/537.36', 
                u'user': None, 
                u'cognitoIdentityPoolId': None, 
                u'cognitoIdentityId': None, 
                u'cognitoAuthenticationProvider': None, 
                u'sourceIp': u'132.239.181.86', 
                u'accountId': None
            }, 
            u'stage': u'Prod'
        }, 
        u'queryStringParameters': {}, 
        u'httpMethod': u'GET', 
        u'pathParameters': {
            u'workflowReference': u'aa8a36b7-56f2-40d3-b8bc-1c524ac9acc5'
        }, 
        u'headers': {
            u'Via': u'1.1 69ecfaf49062e67077b5f6c4aaf1881f.cloudfront.net (CloudFront)', 
            u'Accept-Language': u'en-US,en;q=0.8', 
            u'CloudFront-Is-Desktop-Viewer': u'true', 
            u'CloudFront-Is-SmartTV-Viewer': u'false', 
            u'CloudFront-Is-Mobile-Viewer': u'false', 
            u'X-Forwarded-For': u'132.239.181.86, 205.251.214.113', 
            u'CloudFront-Viewer-Country': u'US', 
            u'Accept': u'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8', 
            u'Upgrade-Insecure-Requests': u'1', 
            u'X-Forwarded-Port': u'443', 
            u'Host': u'n4zdmn1w9e.execute-api.us-west-2.amazonaws.com', 
            u'X-Forwarded-Proto': u'https', 
            u'X-Amz-Cf-Id': u'PI_q8UmyQPkFLU9gezaJm6sVXULxMwmQtAvUuHUT7lHjiogzKnQROw==', 
            u'CloudFront-Is-Tablet-Viewer': u'false', 
            u'Cache-Control': u'max-age=0', 
            u'User-Agent': u'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/54.0.2840.98 Safari/537.36', 
            u'CloudFront-Forwarded-Proto': u'https', 
            u'Accept-Encoding': u'gzip, deflate, sdch, br'
        }, 
        u'stageVariables': None, 
        u'path': u'/subscriptionRequests/aa8a36b7-56f2-40d3-b8bc-1c524ac9acc5', 
        u'isBase64Encoded': False
}

if __name__ == '__main__':
    logging.basicConfig()
    unittest.main()