#!/usr/bin/env python

import boto3, botocore
import json, os, time, re, sys
import urllib.request, urllib.parse, urllib.error, urllib.request, urllib.error, urllib.parse, base64
import airspeed
from ConfigManager import ConfigManager, getFromMap

import logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# The post method is designed to be invoked by WSO2's API Manager when a user requests a subscription.
# An email will be sent to the API owners for approval, with links back to the get method.
# When a user clicks on the approve or reject link the get method will call the APIM to update the subscription request.

# Project level TODOs
# TODO: Update documentation

# Code level TODOs
# TODO: Allow prevention of emails via value in the context for testing.  Instead print them to the console.

# Extra Features
# TODO: UI for pending approvals, with ability to resend.

def post(event, context):
    try:
        return RequestHandler(event, context).post()
    except RequestError as e:
        return messageResponse(e.message, e.statusCode)
    except Exception as e:
        logger.exception(e)
        return messageResponse(str(e), 500)

def get(event, context):
    try:
        return RequestHandler(event, context).get()
    except RequestError as e:
        return messageResponse(e.message, e.statusCode)
    except Exception as e:
        logger.exception(e)
        return messageResponse(str(e), 500)

class RequestHandler:
    def __init__(self, event, context):
        self.event = event
        self.context = context
        self.config = ConfigManager(self)

    def post(self):
        logger.debug("Post called with event: %s", self.event)
        logger.debug("Post called with context: %s", self.context)

        requires(self.event, ['body'], 'Request did not contain a body!')

        item = self.item = json.loads(self.event['body'])
        item = {k:v for k,v in item.items() if v}  # Remove blank entries as they aren't allowed in the DB
        item["requestDT"] = time.strftime("%c %Z")
        item["status"] = "Waiting for Approval"

        requires(item, ['workflowReference', 'subscriberId', 'apiName', 'callbackUrl'], "Body must contain {key}.")

        logger.debug("Saving item to DB")
        save(item)

        logger.debug("New request received, sending out emails")
        self.sendNewRequestEmails()

        logger.debug("Responding.")
        return messageResponse("Subscription Request Accepted")


    def get(self):
        logger.debug("Get called with event: %s", self.event)
        logger.debug("Get called with context: %s", self.context)

        errorMessage = ""

        workflowReference = getRequiredFromMap(self.event, 'pathParameters/workflowReference', "A WorkflowReferenceId must be set on the url.")

        self.item = getItem(workflowReference)

        action = getFromMap(self.event, 'queryStringParameters/action', None)
        if (action == 'approve') or (action == 'reject'):
            if self.item['status'] != "Waiting for Approval":
                errorMessage = "Request was already {item[status]} by {item[approver]} at {item[responseDT]}!".format(item=self.item)
            else:
                self.approveReject(workflowReference, action)

        if getFromMap(self.event, 'headers/Accept', None) == "application/json":
            resp = {'errorMessage':errorMessage}
            resp.update(self.item)
            return respond(resp)

        return {
            'statusCode': 200,
            'body': self.processTemplate(self.config.get("templates/webpage/html"), {'errorMessage':errorMessage}),
            'headers': {
                'Content-Type': 'text/html',
            },
        }

    def approveReject(self, workflowReference, action):
        item = self.item
        if action == 'approve':
            item['status'] = "APPROVED"
        else:
            item['status'] = "REJECTED"

        item['approver'] = getRequiredFromMap(self.event, 'queryStringParameters/approver', "Must provide an approver query parameter when attempting to " + action)
        item["responseDT"] = time.strftime("%c %Z")

        payload = {
            'status':item['status'],
            'description':item['status'] + " by the AWS WSO2 Subscription service."
        }

        workflow_url = item['callbackUrl']

        # Support for more recent version of APIM which uses REST for workflow submission
        rest_style = "WORKFLOW_REFERENCE_ID" in workflow_url

        if rest_style:
            workflow_url = workflow_url.replace("WORKFLOW_REFERENCE_ID", workflowReference)
            payload = json.dumps(payload).encode("utf-8")
        else:
            payload['workflowReference'] = workflowReference
            payload = urllib.parse.urlencode(payload).encode("utf-8")

        req = urllib.request.Request(url=workflow_url, data=payload)

        if rest_style:
            req.add_header('Content-Type', 'application/json')

        req.add_header("Authorization", "Basic " + self.getAdminCreds())

        # TODO: switch this to workflow_url
        logger.debug("Calling %s to %s workflow", item['callbackUrl'], action)

        try:
            urllib.request.urlopen(req, timeout=20)
        except Exception as e:
            logger.exception("Failed to approve the workflow on the remote server.")
            raise RequestError("Failed to approve the workflow on the remote server. The server returned " + str(e)
                               + "  URL:" + workflow_url
                               + "  Payload:" + payload)

        logger.debug("Workflow approval submitted successfully")

        save(item)

        self.sendCompletedRequestEmails()

    def templateTest(self):
        # workflowReference = getRequiredFromMap(self.event, 'pathParameters/workflowReference', "A WorkflowReferenceId must be set on the url.")
        # self.item = getItem(workflowReference)
        # self.item['approver'] = 'admin'
        item = self.item = json.loads(self.event['body'])
        item = {k:v for k,v in item.items() if v}  # Remove blank entries as they aren't allowed in the DB
        item["requestDT"] = time.strftime("%c %Z")
        item["status"] = "Waiting for Approval"

        requires(item, ['workflowReference', 'subscriberId', 'apiName', 'callbackUrl'], "Body must contain {key}.")

        for name, template in list(self.config.get("templates").items()):
            print("*********")
            print(("Template " + name))
            print("")
            if 'html' in template:
                print(( self.processTemplate(template['html'])))

    def buildCallbackUrl(self):
        return "{protocol}://{host}:{port}/{context[stage]}/subscriptionRequests".format(
            protocol=self.event['headers']['X-Forwarded-Proto'],
            host=self.event['headers']['Host'],
            port=self.event['headers']['X-Forwarded-Port'],
            context=self.event['requestContext']
            )

    def processTemplate(self, template, extra={}):
        if not template:
            return ''

        v = {'request':self.item,
             'json':json.dumps(self.item, indent=4),
             'extra':extra}

        v['properties'] = self.config.get('properties', {}, globalOnly=True).copy()
        v['properties'].update(self.config.get('properties', {}, instanceOnly=True))

        if 'to' in extra:
            baseurl = self.buildCallbackUrl() + "/{item[workflowReference]}?approver={extra[to]}&action=".format(item=self.item, extra=extra)
            v['approveUrl'] = baseurl + "approve"
            v['rejectUrl'] = baseurl + "reject"

        return airspeed.Template(template).merge(v)

    def sendTemplateEmail(self, key, to):
        logger.debug("Sending %s email to %s", key, to)

        prefix = ""

        filters = self.config.get('permitted_emails', [])
        if filters and not any(re.match(f, to) for f in filters):
            prefix = "Message was origionally sent to restricted address " + to
            to = self.config.get('fallback_email', '')

        if not to:
            return

        template = self.config.get("templates/" + key)
        subject = self.processTemplate(template['subject'])
        html = self.processTemplate(template.get('html', ''), {'to':to})
        text = self.processTemplate(template.get('text', ''), {'to':to})

        if not html and not text:
            raise EnvironmentError("Template " + key + " doesn't have a valid html or text template.")

        if prefix:
            if html:
                html = "<p>" + prefix + "</p><hr/>" + html
            if text:
                text = prefix + "\n----------------\n\n" + text

        self.sendEmail(to, subject, text, html)
        logger.debug("Email Sent.")

    def sendEmail(self, to, subject, text, html):

        message={
            'Subject': {'Data': subject},
            'Body': {}
        }
        if text:
            message['Body']['Text'] = {'Data':text}
        if html:
            message['Body']['Html'] = {'Data':html}

        if getFromMap(self.event, 'queryStringParameters/simulate', None):
            logger.debug("Simulating email to " + to)
            logger.debug("**** Begin Simulated Email ****")
            if html:
                logger.debug(message['Body']['Html']['Data'])
            else:
                logger.debug(message['Body']['Text']['Data'])
            logger.debug("**** End Simulated Email ****")
            return

        emailClient = boto3.client('ses')
        response = emailClient.send_email(
            Source=self.config.get("source_email_address"),
            Destination={'ToAddresses': [to]},
            Message=message
        )
        logger.debug("Email sent to approvers %s", to)
        return response

    def getAdminCreds(self):
        username = self.config.get('username', errorMessage="The username for the current APIM have not been set.")
        password = self.config.get('password', errorMessage="The password for the current APIM have not been set.")
        creds = '%s:%s' % (username, password)
        b64creds = base64.b64encode(creds.encode('ascii'))
        return b64creds.decode("ascii")

    def sendNewRequestEmails(self):
        bEmail = getFromMap(self.item, 'apiBusinessOwnerEmail', '')
        tEmail = getFromMap(self.item, 'apiTechnicalOwnerEmail', '')
        noEmail = self.config.get('no_owner_email_address')
        sEmail = self.config.get('properties/subscriber_email', '')

        if bEmail:
            self.sendTemplateEmail("business_owner_request", bEmail)

        if tEmail:
            self.sendTemplateEmail("technical_owner_request", tEmail)

        if not bEmail and not tEmail:
            self.item['apiTechnicalOwnerName'] = self.config.get('no_owner_name', 'The Default Approver')
            self.item['apiTechnicalOwnerEmail'] = noEmail
            self.sendTemplateEmail("no_owner_request", noEmail)

        if sEmail:
            self.sendTemplateEmail("subscriber_request", sEmail)

    def sendCompletedRequestEmails(self):
        approvers = [getFromMap(self.item, 'apiBusinessOwnerEmail', ''), getFromMap(self.item, 'apiTechnicalOwnerEmail', '')]
        approvers = [e for e in approvers if e]
        if not approvers:
            approvers = [self.config.get('no_owner_email_address')]

        for email in approvers:
            if email == self.item['approver']:
                if self.item['status'] == 'APPROVED':
                    template = 'request_approver'
                else:
                    template = 'request_rejecter'
            else:
                if self.item['status'] == 'APPROVED':
                    template = 'request_approval'
                else:
                    template = 'request_rejection'

            self.sendTemplateEmail(template, email)

        sEmail = self.config.get('properties/subscriber_email', '')
        if sEmail:
            if self.item['status'] == 'APPROVED':
                self.sendTemplateEmail("subscriber_request_approval", sEmail)
            else:
                self.sendTemplateEmail("subscriber_request_rejected", sEmail)

def getTable():
    requires(os.environ, ['SubscriptionTable'], 'The envrionment variable {key} must be set to the name of the DynamoDB table to use.')
    dynamodb = boto3.resource('dynamodb')
    return dynamodb.Table(os.environ['SubscriptionTable'])

def save(item):
    getTable().put_item(Item=item)
    logger.debug("Request stored in DB")

def getItem(workflowReference):
    print( workflowReference)
    response = getTable().get_item(
        Key={
            'workflowReference': workflowReference
        }
    )

    if "Item" not in response:
        logger.debug("Entry not found")
        raise RequestError("Invalid WorkflowReference " + workflowReference, 422)

    logger.debug("read table entry ")
    logger.debug(response["Item"])
    return response["Item"]

class RequestError(Exception):
    def __init__(self, message, statusCode=500):
        self.statusCode = statusCode
        self.message = message

    def __str__(self):
        return '{"statusCode": "%s", "message": "%s"}' % (self.statusCode, self.message)

def respond(res, statusCode=200):
    return {
        'statusCode': statusCode,
        'body': json.dumps(res),
        'headers': {
            'Content-Type': 'application/json',
        },
    }

def messageResponse(message, statusCode=200):
    return respond({'message':message}, statusCode)

def requires(source, keys, error_message):
    for k in keys:
        getRequiredFromMap(source, k, error_message)

def getRequiredFromMap(sourcemap, key, errorMessage):
    try:
        return getFromMap(sourcemap, key)
    except KeyError:
        raise RequestError("Required value not set. " + errorMessage.format(key=key), 400)


if __name__ == '__main__':
    logging.basicConfig()

    if os.path.isdir('lambda'):
        os.chdir('lambda')
    os.environ['SubscriptionTable'] = "mid-apisub-dev-SubTable-8LMVLTGPDK1P"
    os.environ['ConfigS3'] = "s3://middleware-tests/configs/mid-apisub-dev/config.yaml"

    import yaml
    with open("../config.yaml", 'r') as stream:
        testConfig = yaml.load(stream)

    # s3 = boto3.resource('s3')
    # obj = s3.Object('middleware-tests', 'configs/mid-apisub-dev/config.yaml')
    # with open("config.yaml", 'r') as stream:
    #     obj.put(Body=stream)

    try:
        exampleGet = {'body': None, 'resource': '/subscriptionRequests/{workflowReference}', 'requestContext': {'resourceId': '86aip8', 'apiId': 'n4zdmn1w9e', 'resourcePath': '/subscriptionRequests/{workflowReference}', 'httpMethod': 'GET', 'requestId': 'cd2d87db-c303-11e6-b8dc-613344667c2c', 'accountId': '693896114532', 'identity': {'apiKey': None, 'userArn': None, 'cognitoAuthenticationType': None, 'accessKey': None, 'caller': None, 'userAgent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/54.0.2840.98 Safari/537.36', 'user': None, 'cognitoIdentityPoolId': None, 'cognitoIdentityId': None, 'cognitoAuthenticationProvider': None, 'sourceIp': '132.239.181.86', 'accountId': None}, 'stage': 'Prod'}, 'queryStringParameters': {}, 'httpMethod': 'GET', 'pathParameters': {'workflowReference': 'aa8a36b7-56f2-40d3-b8bc-1c524ac9acc5'}, 'headers': {'Via': '1.1 69ecfaf49062e67077b5f6c4aaf1881f.cloudfront.net (CloudFront)', 'Accept-Language': 'en-US,en;q=0.8', 'CloudFront-Is-Desktop-Viewer': 'true', 'CloudFront-Is-SmartTV-Viewer': 'false', 'CloudFront-Is-Mobile-Viewer': 'false', 'X-Forwarded-For': '132.239.181.86, 205.251.214.113', 'CloudFront-Viewer-Country': 'US', 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8', 'Upgrade-Insecure-Requests': '1', 'X-Forwarded-Port': '443', 'Host': 'n4zdmn1w9e.execute-api.us-west-2.amazonaws.com', 'X-Forwarded-Proto': 'https', 'X-Amz-Cf-Id': 'PI_q8UmyQPkFLU9gezaJm6sVXULxMwmQtAvUuHUT7lHjiogzKnQROw==', 'CloudFront-Is-Tablet-Viewer': 'false', 'Cache-Control': 'max-age=0', 'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/54.0.2840.98 Safari/537.36', 'CloudFront-Forwarded-Proto': 'https', 'Accept-Encoding': 'gzip, deflate, sdch, br'}, 'stageVariables': None, 'path': '/subscriptionRequests/aa8a36b7-56f2-40d3-b8bc-1c524ac9acc5', 'isBase64Encoded': False}
        print(( get(exampleGet, {'test-config': testConfig})))

        examplePost = {'body': '{"subscriberclaims": {"http://wso2.org/claims/organization": "org", "http://wso2.org/claims/country": "country", "http://wso2.org/claims/emailaddress": "admin@admin.com", "http://wso2.org/claims/mobile": "12345", "http://wso2.org/claims/streetaddress": "add", "http://wso2.org/claims/role": "admin,Internal/subscriber,Internal/everyone", "http://wso2.org/claims/telephone": "1234", "http://wso2.org/claims/givenname": "first", "http://wso2.org/claims/lastname": "last"}, "apiTechnicalOwnerEmail": "", "apiProvider": "admin", "apiName": "MergePDF", "callbackUrl": "https://api.ucsd.edu:8243/services/WorkflowCallbackService", "apiBusinessOwnerName": "BusinessOwner", "subscriberId": "admin", "applicationName": "DefaultApplication", "tier": "Unlimited", "apiTechnicalOwnerName": "", "apiVersion": "1.0.0", "workflowReference": "aa8a36b7-56f2-40d3-b8bc-1c524ac9acc5", "apiBusinessOwnerEmail": "bo@example.com", "apiContext": "/mergePDF/1.0.0"}', 'resource': '/subscriptionRequests', 'requestContext': {'resourceId': 'i9mp34', 'apiId': 'n4zdmn1w9e', 'resourcePath': '/subscriptionRequests', 'httpMethod': 'POST', 'requestId': '363c9b25-c320-11e6-9af8-9d9abcfb8998', 'accountId': '693896114532', 'identity': {'apiKey': None, 'userArn': None, 'cognitoAuthenticationType': None, 'accessKey': None, 'caller': None, 'userAgent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/54.0.2840.98 Safari/537.36', 'user': None, 'cognitoIdentityPoolId': None, 'cognitoIdentityId': None, 'cognitoAuthenticationProvider': None, 'sourceIp': '132.239.181.86', 'accountId': None}, 'stage': 'Prod'}, 'queryStringParameters': None, 'httpMethod': 'POST', 'pathParameters': None, 'headers': {'Origin': 'chrome-extension://fhbjgbiflinjbdggehcddcbncdddomop', 'Content-Type': 'application/json', 'Via': '1.1 0c146399837c7d36c1f0f9d2636f8cf8.cloudfront.net (CloudFront)', 'Accept-Language': 'en-US,en;q=0.8', 'CloudFront-Is-Desktop-Viewer': 'true', 'CloudFront-Is-SmartTV-Viewer': 'false', 'CloudFront-Is-Mobile-Viewer': 'false', 'X-Forwarded-For': '132.239.181.86, 205.251.214.61', 'CloudFront-Viewer-Country': 'US', 'Accept': '*/*', 'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/54.0.2840.98 Safari/537.36', 'X-Forwarded-Port': '443', 'Host': 'n4zdmn1w9e.execute-api.us-west-2.amazonaws.com', 'X-Forwarded-Proto': 'https', 'X-Amz-Cf-Id': '75wuMnW1L15AtFAd8Y7-qD5RV6t5JGZ90Pf20EZ1b3xMU3UGT-BbyA==', 'CloudFront-Is-Tablet-Viewer': 'false', 'Cache-Control': 'no-cache', 'Postman-Token': '8f080e24-8c91-7255-5c3d-f359e8700fff', 'CloudFront-Forwarded-Proto': 'https', 'Accept-Encoding': 'gzip, deflate, br'}, 'stageVariables': None, 'path': '/subscriptionRequests', 'isBase64Encoded': False}
        # Warning: this will generate an email.
        # post(examplePost, {})

        getWithApprove = {'body': None, 'resource': '/subscriptionRequests/{workflowReference}', 'requestContext': {'resourceId': '86aip8', 'apiId': 'n4zdmn1w9e', 'resourcePath': '/subscriptionRequests/{workflowReference}', 'httpMethod': 'GET', 'requestId': 'cd2d87db-c303-11e6-b8dc-613344667c2c', 'accountId': '693896114532', 'identity': {'apiKey': None, 'userArn': None, 'cognitoAuthenticationType': None, 'accessKey': None, 'caller': None, 'userAgent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/54.0.2840.98 Safari/537.36', 'user': None, 'cognitoIdentityPoolId': None, 'cognitoIdentityId': None, 'cognitoAuthenticationProvider': None, 'sourceIp': '132.239.181.86', 'accountId': None}, 'stage': 'Prod'}, 'queryStringParameters': {'action': 'approve', 'approver': 'admin'}, 'httpMethod': 'GET', 'pathParameters': {'workflowReference': 'aa8a36b7-56f2-40d3-b8bc-1c524ac9acc5'}, 'headers': {'Via': '1.1 69ecfaf49062e67077b5f6c4aaf1881f.cloudfront.net (CloudFront)', 'Accept-Language': 'en-US,en;q=0.8', 'CloudFront-Is-Desktop-Viewer': 'true', 'CloudFront-Is-SmartTV-Viewer': 'false', 'CloudFront-Is-Mobile-Viewer': 'false', 'X-Forwarded-For': '132.239.181.86, 205.251.214.113', 'CloudFront-Viewer-Country': 'US', 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8', 'Upgrade-Insecure-Requests': '1', 'X-Forwarded-Port': '443', 'Host': 'n4zdmn1w9e.execute-api.us-west-2.amazonaws.com', 'X-Forwarded-Proto': 'https', 'X-Amz-Cf-Id': 'PI_q8UmyQPkFLU9gezaJm6sVXULxMwmQtAvUuHUT7lHjiogzKnQROw==', 'CloudFront-Is-Tablet-Viewer': 'false', 'Cache-Control': 'max-age=0', 'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/54.0.2840.98 Safari/537.36', 'CloudFront-Forwarded-Proto': 'https', 'Accept-Encoding': 'gzip, deflate, sdch, br'}, 'stageVariables': None, 'path': '/subscriptionRequests/aa8a36b7-56f2-40d3-b8bc-1c524ac9acc5', 'isBase64Encoded': False}
        get(getWithApprove, {'test-config': testConfig})

        RequestHandler(examplePost, {'test-config': testConfig}).templateTest()

    except Exception as e:
        logger.exception(e)
        raise e
