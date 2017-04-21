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

        self.assertEqual('testValue', handler.config.get('testKey'), "Simple lookup")
        self.assertEqual('defaultValue', handler.config.get('missingKey', 'defaultValue'), "Lookup with default value.")

        with self.assertRaises(EnvironmentError):
            handler.config.get('missingKey')

    def test_apimInstance(self):
        handler = makeDefaultHandler()

        self.assertEqual('testValue', handler.config.get('testKey'))

        # now test that the value is different for requests comming from a different source
        handler = makeDefaultHandler()
        handler.item['callbackUrl'] = "https://override.com:8243/services/WorkflowCallbackService"
        self.assertEqual('overriddenValue', handler.config.get('testKey'))
        
        with self.assertRaises(EnvironmentError):
            handler.config.get('missingKey')
    
    def test_template(self):
        handler = makeDefaultHandler()
        
        self.assertEqual("Static", handler.processTemplate("Static"))
        self.assertEqual("testValue", handler.processTemplate("${properties.testProperty}"), "Property Usage")

class TestEmail(TestCase):
    
    def setUp(self):
        self.longMessage = True
        self.emails = []
    
    def makeHandler(self, event=None, context=None):
        handler = makeDefaultHandler(event,context)
        # Override the normal email sending method with local version to catch and check emails that would have been sent.
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
        self.assertEqual({'business@api.com', 'tech@api.com', 'jsmith@api.com'}, self.getEmailTargets())
    
    def test_SendNoOwnerEmail(self):
        h = self.makeHandler()
        h.item['apiBusinessOwnerEmail'] = ''
        h.item['apiTechnicalOwnerEmail'] = ''
        
        h.sendNewRequestEmails()
        
        self.assertEqual(2, len(self.emails), "Two emails should have been sent, no-owner and subscriber")
        (to, subject, text, html) = self.emails[0]
        self.assertEqual('no-owner@api.com', to)
    
    def test_RestrictedEmails(self):
        h = self.makeHandler()
        h.context['test-config']['permitted_emails'] = ['te.*@api.com']
        h.sendNewRequestEmails()
        self.assertEqual({'tech@api.com'}, self.getEmailTargets(), "The only email sent should be to tech")

        h = self.makeHandler()
        h.context['test-config']['permitted_emails'] = ['te.*@api.com']
        h.context['test-config']['fallback_email'] = 'fallback@api.com'
        h.sendNewRequestEmails()
        self.assertEqual({'tech@api.com', 'fallback@api.com'}, self.getEmailTargets(), "The only email sent should be to tech")
    
    def test_CompletedRequestEmails(self):
        h = self.makeHandler()
        h.item['approver'] = "tech@api.com"
        h.item['status'] = 'APPROVED'
        h.sendCompletedRequestEmails()
        self.assertEqual({'business@api.com', 'tech@api.com', 'jsmith@api.com'}, self.getEmailTargets())

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
  testProperty: testValue
 
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
    u'status': u'Waiting for Approval', 
    u'subscriberclaims': {
        u'http://wso2.org/claims/organization': u'org', 
        u'http://wso2.org/claims/emailaddress': u'jsmith@api.com', 
        u'http://wso2.org/claims/lastname': u'last', 
        u'http://wso2.org/claims/role': u'admin,Internal/subscriber,Internal/everyone', 
        u'http://wso2.org/claims/telephone': u'1234', 
        u'http://wso2.org/claims/mobile': u'12345', 
        u'http://wso2.org/claims/streetaddress': u'add', 
        u'http://wso2.org/claims/country': u'country', 
        u'http://wso2.org/claims/givenname': u'first'
    }, 
    u'apiTechnicalOwnerName': u'Owner, Technical', 
    u'apiProvider': u'dyl011', 
    u'apiBusinessOwnerName': u'Owner, Business', 
    u'workflowReference': u'testWorkflow1', 
    u'apiContext': u'/biotest/v1', 
    u'apiVersion': u'v1', 
    u'apiTechnicalOwnerEmail': u'tech@api.com', 
    u'tier': u'Unlimited', 
    u'requestDT': u'Wed Jan 25 17:58:15 2017 PST', 
    u'apiName': u'BioTest', 
    u'apiBusinessOwnerEmail': u'business@api.com', 
    u'callbackUrl': u'https://api.com:8243/services/WorkflowCallbackService', 
    u'subscriberId': u'jsmith', 
    u'applicationName': u'TestApp'
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
        u'accountId': u'XXXXXXXXX',
        u'stage': u'Prod'
    },
    u'queryStringParameters': {
        u'simulte': u'true'
    },
    u'httpMethod': u'GET',
    u'pathParameters': {
        u'workflowReference': u'testWorkflow1'
    },
    u'headers': {
        u'X-Forwarded-Port': u'443',
        u'Host': u'n4zdmn1w9e.execute-api.us-west-2.amazonaws.com',
        u'X-Forwarded-Proto': u'https',
        u'Accept': u'application/json'
    },
    u'stageVariables': None,
    u'path': u'/subscriptionRequests/aa8a36b7-56f2-40d3-b8bc-1c524ac9acc5',
    u'isBase64Encoded': False
}

if __name__ == '__main__':
    logging.basicConfig()
    logging.getLogger(__name__).setLevel(logging.DEBUG)
    unittest.main()