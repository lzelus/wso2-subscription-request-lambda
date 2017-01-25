from unittest import TestCase

import boto3

import lambda_function
import json


class TestLambda_handler(TestCase):

    def setUp(self):
        self.deleteRecord()

    def tearDown(self):
        self.deleteRecord()

    def deleteRecord(self):
        db = boto3.resource('dynamodb')
        table = db.Table('WSO2SubscriptionRequest')
        response = table.get_item(
            Key={
                'workflowReference': 'test1'
            }
        )
        if "Item" in response:
            table.delete_item(
                Key={
                'workflowReference': 'test1'
                }
            )

    def test_success(self):
        """Tests a successful run - uses the simluate querystring parameter to not actually send the emails"""

        print "\n\nrunning test_success"
        print "-------------------------------------------\n\n"

        testevent = json.loads("""
{
  "body": "{\\"taggedRestricted\\": \\"true\\",\\"apiVersion\\": \\"v1\\",\\"apiContext\\": \\"/byuapi/echo/v1\\",\\"applicationName\\": \\"testapp\\",\\"tier\\": \\"Unlimited\\",\\"apiTechnicalOwnerName\\": \\"technical\\",\\"workflowReference\\": \\"test1\\",\\"apiProvider\\": \\"BYU/bdm4\\",\\"apiBusinessOwnerName\\": \\"business\\",\\"apiName\\": \\"EchoService\\",\\"subscriberName\\": \\"Moore, Brent D\\",\\"subscriberId\\": \\"BYU/bdm4\\",\\"taggedDevelopment\\": \\"true\\",\\"subscriberEmail\\": \\"bdm4@byu.edu\\",\\"apiBusinessOwnerEmail\\": \\"bdm4@byu.edu\\",\\"apiTechnicalOwnerEmail\\": \\"brent_moore@byu.edu\\"}",
  "headers": {
    "Accept": "*/*",
    "Accept-Encoding": "gzip, deflate",
    "CloudFront-Forwarded-Proto": "https",
    "CloudFront-Is-Desktop-Viewer": "true",
    "CloudFront-Is-Mobile-Viewer": "false",
    "CloudFront-Is-SmartTV-Viewer": "false",
    "CloudFront-Is-Tablet-Viewer": "false",
    "CloudFront-Viewer-Country": "US",
    "Content-Type": "application/json",
    "Host": "zo60u45plb.execute-api.us-west-2.amazonaws.com",
    "User-Agent": "PostmanRuntime/3.0.9",
    "Via": "1.1 199c9bce22bd411402daf00db8dbb17d.cloudfront.net (CloudFront)",
    "X-Amz-Cf-Id": "6bQFsGxtvTkQvmTm7hzPkvChhLMBxivOnc7Z45GdcSoQlcxOm3KSRw==",
    "X-Forwarded-For": "45.56.28.214, 205.251.214.107",
    "X-Forwarded-Port": "443",
    "X-Forwarded-Proto": "https",
    "cache-control": "no-cache"
  },
  "httpMethod": "POST",
  "isBase64Encoded": "false",
  "path": "/subscriptionRequests",
  "pathParameters": "",
  "queryStringParameters": {
    "debug": "True",
    "simulate": "True"
  },
  "requestContext": {
    "accountId": "035170473189",
    "apiId": "zo60u45plb",
    "httpMethod": "POST",
    "identity": {
      "accessKey": "",
      "accountId": "",
      "apiKey": "",
      "caller": "",
      "cognitoAuthenticationProvider": "",
      "cognitoAuthenticationType": "",
      "cognitoIdentityId": "",
      "cognitoIdentityPoolId": "",
      "sourceIp": "45.56.28.214",
      "user": "",
      "userAgent": "PostmanRuntime/3.0.9",
      "userArn": ""
    },
    "requestId": "b6cd9fa7-c66e-11e6-8efc-11e6514ac918",
    "resourceId": "6f74y3",
    "resourcePath": "/subscriptionRequests",
    "stage": "bdmtest"
  },
  "resource": "/subscriptionRequests",
  "stageVariables":
  {
      "approvalBaseURL": "https://zo60u45plb.execute-api.us-west-2.amazonaws.com/bdmtest/subscriptionApprovals"
  }
  ,
  "test-config": {
    "business_owner_request": {
      "email_subject": "API subscription request",
      "template": "bo_request.tem"
    },
    "no_owner_email_address": "no-owner-email",
    "no_owner_request": {
      "email_subject": "API subscription received with no owners",
      "template": "no_owner_request.tem"
    },
    "request_action_email_addresses": [
      "brent_moore@byu.edu",
      "bdm4aws@byu.edu"
    ],
    "request_action_required": {
      "email_subject": "API subscription action required",
      "template": "temp_action_required.tem"
    },
    "source_email_address": "bdm4aws@byu.edu",
    "subscriber_request": {
      "email_subject": "API subscription request received",
      "template": "subscriber_request.tem"
    },
    "technical_owner_request": {
      "email_subject": "API subscription request",
      "template": "to_request.tem"
    }
  }
}

            """)

        testcontext = testevent['requestContext']
        result = lambda_function.lambda_handler(testevent, testcontext)
        print("result from test " + str(result))
        self.assertEqual(
            200,
            result['statusCode'],
            "statusCode should be 200")
        return

    def test_invalid_event(self):
        """Tests that the event struture passed in has the required elements"""

        print "\n\nrunning test_invalid_event"
        print "-------------------------------------------\n\n"
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

        result = lambda_function.lambda_handler(testevent, None)
        print("result from test " + str(result))
        self.assertEqual(400, result['statusCode'],"statusCode should be 400")
        body = json.loads(result['body'])
        self.assertEqual("Invalid event structure - Check API Gateway configuration", body['message'],"invalid event")

        return

    def test_no_owner_emails(self):
        """Tests to be sure that if no owner emails are present in the request it is sent to the
        proper no-owner-email default email address"""

        print "\n\nrunning test_no_owner_emails"
        print "-------------------------------------------\n\n"
        testevent = json.loads("""
 {
   "body": "{\\"taggedRestricted\\": \\"true\\",\\"apiVersion\\": \\"v1\\",\\"apiContext\\": \\"/byuapi/echo/v1\\",\\"applicationName\\": \\"testapp\\",\\"tier\\": \\"Unlimited\\",\\"apiTechnicalOwnerName\\": \\"technical\\",\\"workflowReference\\": \\"test1\\",\\"apiProvider\\": \\"BYU/bdm4\\",\\"apiBusinessOwnerName\\": \\"business\\",\\"apiName\\": \\"EchoService\\",\\"subscriberName\\": \\"Moore, Brent D\\",\\"subscriberId\\": \\"BYU/bdm4\\",\\"subscriberEmail\\": \\"bdm4@byu.edu\\",\\"taggedDevelopment\\": \\"true\\"}",
   "headers": {
     "Accept": "*/*",
     "Accept-Encoding": "gzip, deflate",
     "CloudFront-Forwarded-Proto": "https",
     "CloudFront-Is-Desktop-Viewer": "true",
     "CloudFront-Is-Mobile-Viewer": "false",
     "CloudFront-Is-SmartTV-Viewer": "false",
     "CloudFront-Is-Tablet-Viewer": "false",
     "CloudFront-Viewer-Country": "US",
     "Content-Type": "application/json",
     "Host": "zo60u45plb.execute-api.us-west-2.amazonaws.com",
     "User-Agent": "PostmanRuntime/3.0.9",
     "Via": "1.1 199c9bce22bd411402daf00db8dbb17d.cloudfront.net (CloudFront)",
     "X-Amz-Cf-Id": "6bQFsGxtvTkQvmTm7hzPkvChhLMBxivOnc7Z45GdcSoQlcxOm3KSRw==",
     "X-Forwarded-For": "45.56.28.214, 205.251.214.107",
     "X-Forwarded-Port": "443",
     "X-Forwarded-Proto": "https",
     "cache-control": "no-cache"
   },
   "httpMethod": "POST",
   "isBase64Encoded": "false",
   "path": "/subscriptionRequests",
   "pathParameters": "",
   "queryStringParameters": {
     "debug": "True",
     "simulate": "True"
   },
   "requestContext": {
     "accountId": "035170473189",
     "apiId": "zo60u45plb",
     "httpMethod": "POST",
     "identity": {
       "accessKey": "",
       "accountId": "",
       "apiKey": "",
       "caller": "",
       "cognitoAuthenticationProvider": "",
       "cognitoAuthenticationType": "",
       "cognitoIdentityId": "",
       "cognitoIdentityPoolId": "",
       "sourceIp": "45.56.28.214",
       "user": "",
       "userAgent": "PostmanRuntime/3.0.9",
       "userArn": ""
     },
     "requestId": "b6cd9fa7-c66e-11e6-8efc-11e6514ac918",
     "resourceId": "6f74y3",
     "resourcePath": "/subscriptionRequests",
     "stage": "bdmtest"
   },
   "resource": "/subscriptionRequests",
  "stageVariables":
  {
      "approvalBaseURL": "https://zo60u45plb.execute-api.us-west-2.amazonaws.com/bdmtest/subscriptionApprovals"
  },
   "test-config": {
     "business_owner_request": {
       "email_subject": "API subscription request",
       "template": "bo_request.tem"
     },
     "no_owner_email_address": "no-owner-email",
     "no_owner_request": {
       "email_subject": "API subscription received with no owners",
       "template": "no_owner_request.tem"
     },
     "request_action_email_addresses": [
       "brent_moore@byu.edu",
       "bdm4aws@byu.edu"
     ],
     "request_action_required": {
       "email_subject": "API subscription action required",
       "template": "temp_action_required.tem"
     },
     "source_email_address": "bdm4aws@byu.edu",
     "subscriber_request": {
       "email_subject": "API subscription request received",
       "template": "subscriber_request.tem"
     },
     "technical_owner_request": {
       "email_subject": "API subscription request",
       "template": "to_request.tem"
     }
   }
 }

        """)

        result = lambda_function.lambda_handler(testevent, None)
        print("result from test " + str(result))
        result_body = json.loads(result['body'])
        self.assertEqual(
            200,
            result['statusCode'],
            "statusCode should be 200")
        self.assertEqual(
            "WSO2 Administrator",
            result_body['apiBusinessOwnerName'],
            "Business Owner should be WSO2 Administrator")
        self.assertEqual(
            "WSO2 Administrator",
            result_body['apiTechnicalOwnerName'],
            "Technical Owner should be WSO2 Administrator")
        self.assertEqual(
            "no-owner-email",
            result_body['apiTechnicalOwnerEmail'],
            "Technical Owner Email should be no-owner-email")
        self.assertEqual(
            "no-owner-email",
            result_body['apiBusinessOwnerEmail'],
            "Business Owner Email should be no-owner-email")
        return

    def test_no_subscriber(self):
        """Tests to be sure there is always a subscriber email address"""

        print "\n\nrunning test_no_subscriber"
        print "-------------------------------------------\n\n"

        testevent = json.loads("""
 {
  "body": "{\\"taggedRestricted\\": \\"true\\",\\"apiVersion\\": \\"v1\\",\\"apiContext\\": \\"/byuapi/echo/v1\\",\\"applicationName\\": \\"testapp\\",\\"tier\\": \\"Unlimited\\",\\"apiTechnicalOwnerName\\": \\"technical\\",\\"workflowReference\\": \\"test1\\",\\"apiProvider\\": \\"BYU/bdm4\\",\\"apiBusinessOwnerName\\": \\"business\\",\\"apiName\\": \\"EchoService\\",\\"subscriberName\\": \\"Moore, Brent D\\",\\"subscriberId\\": \\"BYU/bdm4\\",\\"taggedDevelopment\\": \\"true\\",\\"apiBusinessOwnerEmail\\": \\"bdm4@byu.edu\\",\\"apiTechnicalOwnerEmail\\": \\"brent_moore@byu.edu\\"}",
   "headers": {
     "Accept": "*/*",
     "Accept-Encoding": "gzip, deflate",
     "CloudFront-Forwarded-Proto": "https",
     "CloudFront-Is-Desktop-Viewer": "true",
     "CloudFront-Is-Mobile-Viewer": "false",
     "CloudFront-Is-SmartTV-Viewer": "false",
     "CloudFront-Is-Tablet-Viewer": "false",
     "CloudFront-Viewer-Country": "US",
     "Content-Type": "application/json",
     "Host": "zo60u45plb.execute-api.us-west-2.amazonaws.com",
     "User-Agent": "PostmanRuntime/3.0.9",
     "Via": "1.1 199c9bce22bd411402daf00db8dbb17d.cloudfront.net (CloudFront)",
     "X-Amz-Cf-Id": "6bQFsGxtvTkQvmTm7hzPkvChhLMBxivOnc7Z45GdcSoQlcxOm3KSRw==",
     "X-Forwarded-For": "45.56.28.214, 205.251.214.107",
     "X-Forwarded-Port": "443",
     "X-Forwarded-Proto": "https",
     "cache-control": "no-cache"
   },
   "httpMethod": "POST",
   "isBase64Encoded": "false",
   "path": "/subscriptionRequests",
   "pathParameters": "",
   "queryStringParameters": {
     "debug": "True",
     "simulate": "True"
   },
   "requestContext": {
     "accountId": "035170473189",
     "apiId": "zo60u45plb",
     "httpMethod": "POST",
     "identity": {
       "accessKey": "",
       "accountId": "",
       "apiKey": "",
       "caller": "",
       "cognitoAuthenticationProvider": "",
       "cognitoAuthenticationType": "",
       "cognitoIdentityId": "",
       "cognitoIdentityPoolId": "",
       "sourceIp": "45.56.28.214",
       "user": "",
       "userAgent": "PostmanRuntime/3.0.9",
       "userArn": ""
     },
     "requestId": "b6cd9fa7-c66e-11e6-8efc-11e6514ac918",
     "resourceId": "6f74y3",
     "resourcePath": "/subscriptionRequests",
     "stage": "bdmtest"
   },
   "resource": "/subscriptionRequests",
  "stageVariables":
  {
      "approvalBaseURL": "https://zo60u45plb.execute-api.us-west-2.amazonaws.com/bdmtest/subscriptionApprovals"
  },
   "test-config": {
     "business_owner_request": {
       "email_subject": "API subscription request",
       "template": "bo_request.tem"
     },
     "no_owner_email_address": "no-owner-email",
     "no_owner_request": {
       "email_subject": "API subscription received with no owners",
       "template": "no_owner_request.tem"
     },
     "request_action_email_addresses": [
       "brent_moore@byu.edu",
       "bdm4aws@byu.edu"
     ],
     "request_action_required": {
       "email_subject": "API subscription action required",
       "template": "temp_action_required.tem"
     },
     "source_email_address": "bdm4aws@byu.edu",
     "subscriber_request": {
       "email_subject": "API subscription request received",
       "template": "subscriber_request.tem"
     },
     "technical_owner_request": {
       "email_subject": "API subscription request",
       "template": "to_request.tem"
     }
   }
 }
        """)

        testcontext = testevent['requestContext']
        result = lambda_function.lambda_handler(testevent, testcontext)
        print("result from test " + str(result))
        self.assertEqual(400, result['statusCode'],"statusCode should be 400")
        body = json.loads(result['body'])
        self.assertEqual("Subscriber Email Address required to process request", body['message'],"subscriber email required")

        return

