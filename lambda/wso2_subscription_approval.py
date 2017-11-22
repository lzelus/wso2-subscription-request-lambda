#!/usr/bin/env python

import boto3, botocore
import json, os, time, re, sys
import urllib, urllib2, base64
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
        item = {k:v for k,v in item.viewitems() if v}  # Remove blank entries as they aren't allowed in the DB
        item["requestDT"] = time.strftime("%c %Z")
        item["status"] = "Waiting for Approval"
        
        requires(item, ['workflowReference', 'subscriberId', 'apiName', 'callbackUrl'], "Body must contain {key}.")
        
        logger.debug("Saving item to DB")
        save(item)
        
        logger.debug("New request recieved, sending out emails")
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
    
        
        data = urllib.urlencode({
            'workflowReference':workflowReference,
            'status':item['status'],
            'description':item['status'] + " by the AWS WSO2 Subscription service."
        })

        req = urllib2.Request(url=item['callbackUrl'], data=data)

        req.add_header("Authorization", "Basic " + self.getAdminCreds())

        logger.debug("Calling %s to approve workflow", item['callbackUrl'])

        try:
            urllib2.urlopen(req, timeout=6)
        except Exception as e:
            logger.exception("Failed to approve the workflow on the remote server.")
            raise RequestError("Failed to approve the workflow on the remote server. The server returned " + str(e))
    
        logger.debug("Workflow approval submitted successfully")
    
        save(item)
        
        self.sendCompletedRequestEmails()
    
    def templateTest(self):
        # workflowReference = getRequiredFromMap(self.event, 'pathParameters/workflowReference', "A WorkflowReferenceId must be set on the url.")
        # self.item = getItem(workflowReference)
        # self.item['approver'] = 'admin'
        item = self.item = json.loads(self.event['body'])
        item = {k:v for k,v in item.viewitems() if v}  # Remove blank entries as they aren't allowed in the DB
        item["requestDT"] = time.strftime("%c %Z")
        item["status"] = "Waiting for Approval"
        
        requires(item, ['workflowReference', 'subscriberId', 'apiName', 'callbackUrl'], "Body must contain {key}.")
        
        for name, template in self.config.get("templates").items():
            print "*********"
            print "Template " + name
            print ""
            if template.has_key('html'):
                print self.processTemplate(template['html'])

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
        return base64.b64encode('%s:%s' % (username, password))
        
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
    print workflowReference
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
        exampleGet = {u'body': None, u'resource': u'/subscriptionRequests/{workflowReference}', u'requestContext': {u'resourceId': u'86aip8', u'apiId': u'n4zdmn1w9e', u'resourcePath': u'/subscriptionRequests/{workflowReference}', u'httpMethod': u'GET', u'requestId': u'cd2d87db-c303-11e6-b8dc-613344667c2c', u'accountId': u'693896114532', u'identity': {u'apiKey': None, u'userArn': None, u'cognitoAuthenticationType': None, u'accessKey': None, u'caller': None, u'userAgent': u'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/54.0.2840.98 Safari/537.36', u'user': None, u'cognitoIdentityPoolId': None, u'cognitoIdentityId': None, u'cognitoAuthenticationProvider': None, u'sourceIp': u'132.239.181.86', u'accountId': None}, u'stage': u'Prod'}, u'queryStringParameters': {}, u'httpMethod': u'GET', u'pathParameters': {u'workflowReference': u'aa8a36b7-56f2-40d3-b8bc-1c524ac9acc5'}, u'headers': {u'Via': u'1.1 69ecfaf49062e67077b5f6c4aaf1881f.cloudfront.net (CloudFront)', u'Accept-Language': u'en-US,en;q=0.8', u'CloudFront-Is-Desktop-Viewer': u'true', u'CloudFront-Is-SmartTV-Viewer': u'false', u'CloudFront-Is-Mobile-Viewer': u'false', u'X-Forwarded-For': u'132.239.181.86, 205.251.214.113', u'CloudFront-Viewer-Country': u'US', u'Accept': u'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8', u'Upgrade-Insecure-Requests': u'1', u'X-Forwarded-Port': u'443', u'Host': u'n4zdmn1w9e.execute-api.us-west-2.amazonaws.com', u'X-Forwarded-Proto': u'https', u'X-Amz-Cf-Id': u'PI_q8UmyQPkFLU9gezaJm6sVXULxMwmQtAvUuHUT7lHjiogzKnQROw==', u'CloudFront-Is-Tablet-Viewer': u'false', u'Cache-Control': u'max-age=0', u'User-Agent': u'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/54.0.2840.98 Safari/537.36', u'CloudFront-Forwarded-Proto': u'https', u'Accept-Encoding': u'gzip, deflate, sdch, br'}, u'stageVariables': None, u'path': u'/subscriptionRequests/aa8a36b7-56f2-40d3-b8bc-1c524ac9acc5', u'isBase64Encoded': False}
        print get(exampleGet, {'test-config': testConfig})
    
        examplePost = {u'body': u'{"subscriberclaims": {"http://wso2.org/claims/organization": "org", "http://wso2.org/claims/country": "country", "http://wso2.org/claims/emailaddress": "admin@admin.com", "http://wso2.org/claims/mobile": "12345", "http://wso2.org/claims/streetaddress": "add", "http://wso2.org/claims/role": "admin,Internal/subscriber,Internal/everyone", "http://wso2.org/claims/telephone": "1234", "http://wso2.org/claims/givenname": "first", "http://wso2.org/claims/lastname": "last"}, "apiTechnicalOwnerEmail": "", "apiProvider": "admin", "apiName": "MergePDF", "callbackUrl": "https://api.ucsd.edu:8243/services/WorkflowCallbackService", "apiBusinessOwnerName": "BusinessOwner", "subscriberId": "admin", "applicationName": "DefaultApplication", "tier": "Unlimited", "apiTechnicalOwnerName": "", "apiVersion": "1.0.0", "workflowReference": "aa8a36b7-56f2-40d3-b8bc-1c524ac9acc5", "apiBusinessOwnerEmail": "bo@example.com", "apiContext": "/mergePDF/1.0.0"}', u'resource': u'/subscriptionRequests', u'requestContext': {u'resourceId': u'i9mp34', u'apiId': u'n4zdmn1w9e', u'resourcePath': u'/subscriptionRequests', u'httpMethod': u'POST', u'requestId': u'363c9b25-c320-11e6-9af8-9d9abcfb8998', u'accountId': u'693896114532', u'identity': {u'apiKey': None, u'userArn': None, u'cognitoAuthenticationType': None, u'accessKey': None, u'caller': None, u'userAgent': u'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/54.0.2840.98 Safari/537.36', u'user': None, u'cognitoIdentityPoolId': None, u'cognitoIdentityId': None, u'cognitoAuthenticationProvider': None, u'sourceIp': u'132.239.181.86', u'accountId': None}, u'stage': u'Prod'}, u'queryStringParameters': None, u'httpMethod': u'POST', u'pathParameters': None, u'headers': {u'Origin': u'chrome-extension://fhbjgbiflinjbdggehcddcbncdddomop', u'Content-Type': u'application/json', u'Via': u'1.1 0c146399837c7d36c1f0f9d2636f8cf8.cloudfront.net (CloudFront)', u'Accept-Language': u'en-US,en;q=0.8', u'CloudFront-Is-Desktop-Viewer': u'true', u'CloudFront-Is-SmartTV-Viewer': u'false', u'CloudFront-Is-Mobile-Viewer': u'false', u'X-Forwarded-For': u'132.239.181.86, 205.251.214.61', u'CloudFront-Viewer-Country': u'US', u'Accept': u'*/*', u'User-Agent': u'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/54.0.2840.98 Safari/537.36', u'X-Forwarded-Port': u'443', u'Host': u'n4zdmn1w9e.execute-api.us-west-2.amazonaws.com', u'X-Forwarded-Proto': u'https', u'X-Amz-Cf-Id': u'75wuMnW1L15AtFAd8Y7-qD5RV6t5JGZ90Pf20EZ1b3xMU3UGT-BbyA==', u'CloudFront-Is-Tablet-Viewer': u'false', u'Cache-Control': u'no-cache', u'Postman-Token': u'8f080e24-8c91-7255-5c3d-f359e8700fff', u'CloudFront-Forwarded-Proto': u'https', u'Accept-Encoding': u'gzip, deflate, br'}, u'stageVariables': None, u'path': u'/subscriptionRequests', u'isBase64Encoded': False}
        # Warning: this will generate an email.
        # post(examplePost, {})

        getWithApprove = {u'body': None, u'resource': u'/subscriptionRequests/{workflowReference}', u'requestContext': {u'resourceId': u'86aip8', u'apiId': u'n4zdmn1w9e', u'resourcePath': u'/subscriptionRequests/{workflowReference}', u'httpMethod': u'GET', u'requestId': u'cd2d87db-c303-11e6-b8dc-613344667c2c', u'accountId': u'693896114532', u'identity': {u'apiKey': None, u'userArn': None, u'cognitoAuthenticationType': None, u'accessKey': None, u'caller': None, u'userAgent': u'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/54.0.2840.98 Safari/537.36', u'user': None, u'cognitoIdentityPoolId': None, u'cognitoIdentityId': None, u'cognitoAuthenticationProvider': None, u'sourceIp': u'132.239.181.86', u'accountId': None}, u'stage': u'Prod'}, u'queryStringParameters': {u'action': u'approve', u'approver': u'admin'}, u'httpMethod': u'GET', u'pathParameters': {u'workflowReference': u'aa8a36b7-56f2-40d3-b8bc-1c524ac9acc5'}, u'headers': {u'Via': u'1.1 69ecfaf49062e67077b5f6c4aaf1881f.cloudfront.net (CloudFront)', u'Accept-Language': u'en-US,en;q=0.8', u'CloudFront-Is-Desktop-Viewer': u'true', u'CloudFront-Is-SmartTV-Viewer': u'false', u'CloudFront-Is-Mobile-Viewer': u'false', u'X-Forwarded-For': u'132.239.181.86, 205.251.214.113', u'CloudFront-Viewer-Country': u'US', u'Accept': u'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8', u'Upgrade-Insecure-Requests': u'1', u'X-Forwarded-Port': u'443', u'Host': u'n4zdmn1w9e.execute-api.us-west-2.amazonaws.com', u'X-Forwarded-Proto': u'https', u'X-Amz-Cf-Id': u'PI_q8UmyQPkFLU9gezaJm6sVXULxMwmQtAvUuHUT7lHjiogzKnQROw==', u'CloudFront-Is-Tablet-Viewer': u'false', u'Cache-Control': u'max-age=0', u'User-Agent': u'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/54.0.2840.98 Safari/537.36', u'CloudFront-Forwarded-Proto': u'https', u'Accept-Encoding': u'gzip, deflate, sdch, br'}, u'stageVariables': None, u'path': u'/subscriptionRequests/aa8a36b7-56f2-40d3-b8bc-1c524ac9acc5', u'isBase64Encoded': False}
        get(getWithApprove, {'test-config': testConfig})
        
        RequestHandler(examplePost, {'test-config': testConfig}).templateTest()

    except Exception as e:
        logger.exception(e)
        raise e, None, sys.exc_info()[2]