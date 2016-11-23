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
              "body-json": {
                "taggedRestricted": "true",
                "apiVersion": "v1",
                "apiBusinessOwnerEmail": "bdm4@byu.edu",
                "apiContext": "/byuapi/echo/v1",
                "applicationName": "testapp",
                "tier": "Unlimited",
                "apiTechnicalOwnerName": "technical",
                "workflowReference": "test1",
                "apiProvider": "BYU/bdm4",
                "subscriberEmail": "brent_moore@byu.edu",
                "apiBusinessOwnerName": "business",
                "apiName": "EchoService",
                "subscriberName": "Moore, Brent D",
                "subscriberId": "BYU/bdm4",
                "apiTechnicalOwnerEmail": "brent_moore@byu.edu",
                "taggedDevelopment": "true"
              },
              "params": {
                "path": {},
                "querystring": {
                "simulate": "True"
                }
               },
              "stage-variables": {},
              "context": {
                "account-id": "",
                "user-arn": "",
                "request-id": "3eb7120b-813a-11e6-9c77-5167a6779e0b",
                "resource-id": "poee10",
                "resource-path": "/subscriptionApprovals/{workflowReference}"
              }
            }
        """)

        testcontext = testevent['context']
        result = lambda_function.lambda_handler(testevent, testcontext)
        print("result from test " + str(result))
        self.assertEqual(
            "200",
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

        try:
            result = lambda_function.lambda_handler(testevent, None)
            print("result from test " + str(result))
        except lambda_function.RequestError as err:
            print err
            self.assertEqual("BadInput", err.getStatusCode(),"statusCode should be BadInput")
        return

    def test_no_owner_emails(self):
        """Tests to be sure that if no owner emails are present in the request it is sent to the
        proper no-owner-email default email address"""

        print "\n\nrunning test_no_owner_emails"
        print "-------------------------------------------\n\n"
        testevent = json.loads("""
        {
          "body-json": {
            "taggedRestricted": "true",
            "apiVersion": "v1",
            "apiContext": "/byuapi/echo/v1",
            "applicationName": "testapp",
            "tier": "Unlimited",
            "workflowReference": "test1",
            "apiProvider": "BYU/bdm4",
            "subscriberEmail": "brent_moore@byu.edu",
            "apiName": "EchoService",
            "subscriberName": "Moore, Brent D",
            "subscriberId": "BYU/bdm4",
            "taggedDevelopment": "true"
          },
          "params": {
            "path": {},
            "querystring": {
            "simulate": "True"
            }
           },
          "stage-variables": {},
          "test-config": {
                  "subscriber_request":
                   {
                        "template" : "subscriber_request.tem",
                        "email_subject": "API subscription request received"
                    },
                  "business_owner_request":
                    {
                        "template": "bo_request.tem",
                        "email_subject" : "API subscription request"
                    },
                  "technical_owner_request":
                    {
                        "template": "to_request.tem",
                        "email_subject" : "API subscription request"
                    },
                  "request_action_required":
                    {
                        "template" : "temp_action_required.tem",
                        "email_subject": "API subscription action required"
                    },
                  "no_owner_request":
                    {
                        "template" : "no_owner_request.tem",
                        "email_subject": "API subscription received with no owners"
                    },
                  "request_action_email_addresses" :
                    [
                        "brent_moore@byu.edu",
                        "bdm4aws@byu.edu"
                    ],
                  "no_owner_email_address" : "no-owner-email",
                  "source_email_address": "bdm4aws@byu.edu"
                 }
        }
        """)

        result = lambda_function.lambda_handler(testevent, None)
        print("result from test " + str(result))
        result_body = json.loads(result['body'])
        self.assertEqual(
            "200",
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

        print "\n\nrunning test_success"
        print "-------------------------------------------\n\n"

        testevent = json.loads("""
            {
              "body-json": {
                "taggedRestricted": "true",
                "apiVersion": "v1",
                "apiBusinessOwnerEmail": "bdm4@byu.edu",
                "apiContext": "/byuapi/echo/v1",
                "applicationName": "testapp",
                "tier": "Unlimited",
                "apiTechnicalOwnerName": "technical",
                "workflowReference": "test1",
                "apiProvider": "BYU/bdm4",
                "apiBusinessOwnerName": "business",
                "apiName": "EchoService",
                "subscriberName": "Moore, Brent D",
                "subscriberId": "BYU/bdm4",
                "apiTechnicalOwnerEmail": "brent_moore@byu.edu",
                "taggedDevelopment": "true"
              },
              "params": {
                "path": {},
                "querystring": {
                "simulate": "True"
                }
               },
              "stage-variables": {},
              "context": {
                "account-id": "",
                "user-arn": "",
                "request-id": "3eb7120b-813a-11e6-9c77-5167a6779e0b",
                "resource-id": "poee10",
                "resource-path": "/subscriptionApprovals/{workflowReference}"
              }
            }
        """)

        testcontext = testevent['context']
        try:
            result = lambda_function.lambda_handler(testevent, testcontext)
            print("result from test " + str(result))
        except lambda_function.RequestError as err:
            print err
            self.assertEqual("BadInput", err.getStatusCode(),"statusCode should be BadInput")
        return

