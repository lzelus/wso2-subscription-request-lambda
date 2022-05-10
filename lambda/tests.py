#!/usr/bin/env python


import unittest
from ConfigManager import ConfigManager, getFromMap
from wso2_subscription_approval import RequestHandler
import airspeed



class Tests(unittest.TestCase):

    def test_one(self):
        testConfig = {}
        exampleGet = {u'body': None, u'resource': u'/subscriptionRequests/{workflowReference}', u'requestContext': {u'resourceId': u'86aip8', u'apiId': u'n4zdmn1w9e', u'resourcePath': u'/subscriptionRequests/{workflowReference}', u'httpMethod': u'GET', u'requestId': u'cd2d87db-c303-11e6-b8dc-613344667c2c', u'accountId': u'693896114532', u'identity': {u'apiKey': None, u'userArn': None, u'cognitoAuthenticationType': None, u'accessKey': None, u'caller': None, u'userAgent': u'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/54.0.2840.98 Safari/537.36', u'user': None, u'cognitoIdentityPoolId': None, u'cognitoIdentityId': None, u'cognitoAuthenticationProvider': None, u'sourceIp': u'132.239.181.86', u'accountId': None}, u'stage': u'Prod'}, u'queryStringParameters': {}, u'httpMethod': u'GET', u'pathParameters': {u'workflowReference': u'aa8a36b7-56f2-40d3-b8bc-1c524ac9acc5'}, u'headers': {u'Via': u'1.1 69ecfaf49062e67077b5f6c4aaf1881f.cloudfront.net (CloudFront)', u'Accept-Language': u'en-US,en;q=0.8', u'CloudFront-Is-Desktop-Viewer': u'true', u'CloudFront-Is-SmartTV-Viewer': u'false', u'CloudFront-Is-Mobile-Viewer': u'false', u'X-Forwarded-For': u'132.239.181.86, 205.251.214.113', u'CloudFront-Viewer-Country': u'US', u'Accept': u'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8', u'Upgrade-Insecure-Requests': u'1', u'X-Forwarded-Port': u'443', u'Host': u'n4zdmn1w9e.execute-api.us-west-2.amazonaws.com', u'X-Forwarded-Proto': u'https', u'X-Amz-Cf-Id': u'PI_q8UmyQPkFLU9gezaJm6sVXULxMwmQtAvUuHUT7lHjiogzKnQROw==', u'CloudFront-Is-Tablet-Viewer': u'false', u'Cache-Control': u'max-age=0', u'User-Agent': u'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/54.0.2840.98 Safari/537.36', u'CloudFront-Forwarded-Proto': u'https', u'Accept-Encoding': u'gzip, deflate, sdch, br'}, u'stageVariables': None, u'path': u'/subscriptionRequests/aa8a36b7-56f2-40d3-b8bc-1c524ac9acc5', u'isBase64Encoded': False}
        
        RequestHandler(exampleGet, {'test-config': testConfig})
    
    def test_two(self):
        c = {}
        print(airspeed.Template("test").merge(c))
        self.assertEqual(airspeed.Template("test").merge(c), "test")
    
    def test_Name(self):
        c = {'name':'Bob'}
        self.assertEqual(airspeed.Template("${name}").merge(c), "Bob")

    def test_Email(self):
        c = {'name':'Bob', 'email':'bob@bob.com'}
        self.assertEqual(airspeed.Template("${name}-${email}").merge(c), "Bob-bob@bob.com")

    def test_NoEmail(self):
        c = {'name':'Bob'}
        t = "#if(${email})${name}-${email}#else${name}#end"
        self.assertEqual(airspeed.Template(t).merge(c), "Bob")

    def test_EmptyEmail(self):
        c = {'name':'Bob', 'email':''}
        t = "#if(${email})${name}-${email}#else${name}#end"
        self.assertEqual(airspeed.Template(t).merge(c), "Bob")

    def test_EmptyEmail(self):
        c = {'name':'Bob', 'email':''}
        t = "#if(${email}&&${name})${name}-${email}#elseif(${email})${email}#else${name}#end"
        self.assertEqual(airspeed.Template(t).merge({'name':'Bob', 'email':''}), "Bob")
        self.assertEqual(airspeed.Template(t).merge({'name':'Bob', 'email':'bob@bob.com'}), "Bob-bob@bob.com")
        self.assertEqual(airspeed.Template(t).merge({'name':'', 'email':'bob@bob.com'}), "bob@bob.com")
        


if __name__ == '__main__':
    unittest.main()