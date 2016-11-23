from __future__ import print_function

import json
import boto3
import time
import airspeed
import logging
from logging.config import fileConfig

fileConfig('logger.ini')
logger = logging.getLogger()

emailClient = boto3.client('ses')
db = boto3.resource('dynamodb')

s3 = boto3.resource('s3')


class RequestError(Exception):

    def __init__(self, statusCode, message):
        self.statusCode = statusCode
        self.message = message

    def getStatusCode(self):
        return self.statusCode

    def getMessage(self):
        return self.message

    def __str__(self):
        return '{"statusCode": "%s", "message": "%s"}' % (self.statusCode, self.message)


def respond(err, res=None):
    if err:
        errorMsg = dict(message=err.getMessage(), error=err.getStatusCode())
        body = json.dumps(errorMsg)
        err.setMessage = body
        raise err
    else:
        statusCode = '200'
        body = json.dumps(res)

    return {
        'statusCode': statusCode,
        'body': body,
        'headers': {
            'Content-Type': 'application/json',
        },
    }


def lambda_handler(event, context):

    # be sure event format is correct
    if not isinstance(
            event, dict) or "params" not in event or "body-json" not in event:
        return respond(RequestError(
            "BadInput", "Invalid event structure - Check API Gateway configuration"))

# if event contains a test configuration then use it
    if isinstance(event, dict) and "test-config" in event:
        config = event['test-config']
    else:
        # Read configuration
        object = s3.Object('byu-wso2', 'wso2subscriptionapproval.config')
        config = json.loads(object.get()["Body"].read())

    table = db.Table('WSO2SubscriptionRequest')


# configure logging
    if "debug" in event["params"]["querystring"] and event[
            "params"]["querystring"]["debug"] == "True":
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.WARN)

# configure sending of email
    if "simulate" in event["params"]["querystring"] and event[
            "params"]["querystring"]["simulate"] == "True":
        simulateEmail = True
    else:
        simulateEmail = False

    logger.debug("Received event: " + json.dumps(event))

    item = event['body-json']

    subscriberEmail = ""
    if "subscriberEmail" in item and item["subscriberEmail"]:
        subscriberEmail = item["subscriberEmail"]
        logger.debug("subscriberEmail = " + subscriberEmail)
        sendEmail(
            config,
            [subscriberEmail],
            config['subscriber_request'],
            item,
            simulateEmail)
    else:
        item['status'] = "Bad Request - no subscriber email address"
        table.put_item(Item=item)
        return respond(RequestError(
            "BadInput", "Subscriber Email Address required to process request"))

    businessOwnerEmail = ""
    if "apiBusinessOwnerEmail" in item:
        businessOwnerEmail = item["apiBusinessOwnerEmail"]
        logger.debug("businessOwnerEmail = " + businessOwnerEmail)
        if businessOwnerEmail:
            sendEmail(
                config,
                [businessOwnerEmail],
                config['business_owner_request'],
                item,
                simulateEmail)

    technicalOwnerEmail = ""
    if "apiTechnicalOwnerEmail" in item:
        technicalOwnerEmail = item["apiTechnicalOwnerEmail"]
        logger.debug("technicalOwnerEmail = " + technicalOwnerEmail)
        if technicalOwnerEmail:
            sendEmail(
                config,
                [technicalOwnerEmail],
                config['technical_owner_request'],
                item,
                simulateEmail)

    if (not businessOwnerEmail) and (not technicalOwnerEmail):
        item["apiBusinessOwnerEmail"] = config['no_owner_email_address']
        item["apiBusinessOwnerName"] = "WSO2 Administrator"
        item["apiTechnicalOwnerEmail"] = config['no_owner_email_address']
        item["apiTechnicalOwnerName"] = "WSO2 Administrator"
        sendEmail(config, [config['no_owner_email_address']],
                  config['no_owner_request'], item, simulateEmail)

    item["requestDT"] = time.strftime("%c %Z")
    item["status"] = "Waiting for Approval"

    table.put_item(Item=item)

    return respond(None, item)

def sendEmail(config, addresses, emailConfig, item, simulateEmail):
    """
    Send email to the address specified. if the simuateEmail flag is set it will process the template but not
    send the email.
    """
    logger.debug("sending to " + str(addresses))

    subject = emailConfig['email_subject']
    object = s3.Object('byu-wso2', emailConfig['template'])
    emailTemplate = airspeed.Template(object.get()["Body"].read())
    email = emailTemplate.merge(item)
    logger.debug("email: " + email)
    if not simulateEmail:
        response = emailClient.send_email(
            Source=config['source_email_address'],
            Destination={
                'ToAddresses': addresses
            },
            Message={
                'Subject': {
                    'Data': subject
                },
                'Body': {
                    'Text': {
                        'Data': email,
                    }
                }
            }
        )
        str(response['ResponseMetadata']['HTTPStatusCode'])
