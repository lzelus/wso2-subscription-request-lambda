## WSO2 Subscription approval on AWS Lambda
This is a set of AWS lambda functions to send emails when a user attempts to subscribe to an API in WSO2's api manager and to update the APIM when the approver responds.

In order to get sufficient information, an extended version of the wso2's SubscriptionCreationWorkFlow is needed.  
Additionally this replacement also uses a more modern http client library which avoids problems with SNI when invoking AWS services.

See the UCSD SubscriptionCreationWorkflowExecutor project for an implementation developed in parallel with this effort.

The process is as follows:
![Restricted Subscription Overall Process](docimages/WSO2RestrictedSubscription.png "Restricted Subscription Overall Process")

### Requirements
To Deploy you will need:

1. aws cli installed and configured wth access keys
1. A S3 Bucket for deployment.  This is where coudformation will store your code for the other AWS services.
1. (OPTIONAL) An S3 Bucket to store the configuration (see [Configuration](#Configuration)).

To Run you will need:

1. SES must be configured and approved to send email, from the "sender" address and to the api owners.

To test locally you will need:

1. AWS Boto3 must be installed and configured with access keys for local development and testing.
1. Uses [Airspeed](https://github.com/purcell/airspeed) for Velocity compatible template processing. 

### Packaging
This distribution does not include a copy of the 3rd party libraries used.  To get a local copy to be included in your deployment:

1. Use `pip install --upgrade --target lambda airspeed `
   this will install Airspeed and its dependent packages into the lambda directory.

1. Use `pip install --upgrade --target lambda PyYaml `
   this will install PyYaml and its dependent packages into the lambda directory.

### Deployment
This project uses aws cloud formation to setup and deploy the neccessary resources.

1. Update the lambda/conig.yaml file with your default settings.  These can be overriden at runtime by providing a S3 location (see [Configuration](#Configuration)).
1. Package the code / resources and upload them to S3:

        aws cloudformation package --template-file cloudFormationConfig.yaml --output-template-file cloudFormationConfig-s3.yaml --s3-bucket [[YOUR DEPLOYMENT S3 BUCKET]]

1. Create the server stack.  The "STACK NAME" is a unique prefix that is applied to all resources (lambda functions, IAM roles, DynamoDB Tables, etc.).
     Use this prefix to identify and seperate different deployments, allowing you to have a dev and a prod deployment in the same aws environment.

        aws cloudformation deploy --template-file cloudFormationConfig-s3.yaml --capabilities CAPABILITY_IAM --stack-name [[STACK NAME]]

     Alternativly if you are using S3 to store your configuration  (see [Configuration](#Configuration)), use the command:

        aws cloudformation deploy --template-file cloudFormationConfig-s3.yaml --capabilities CAPABILITY_IAM --stack-name [[STACK NAME]] --parameter-overrides S3Bucket=[[YOUR S3 CONFIG BUCKET]] S3Path=[[THE FOLDER WITHIN THE BUCKET TO USE]]

### Configuration
The functions are configured by a file called config.yaml.  The default version is stored in the lambda directory and is deployed with your code.
You can also upload a configuration to S3, see below.

#### Global settings
The following settings can be specified:

* no_owner_email_address - the email address to use when the API has no business or technical owner.
* no_owner_name - (optional) the name of the approver to use when the API has no business or technical owner.
* source_email_address - the email address in the "from" line on all outbound emails
* properties - a set of key/values that will be available to the email templates.  Usefull for oft repeated content, like an email footer.
* permitted_emails - (optional) A list of permitted email addresses.  If set, emails destined for addresses not on this list will not be sent.
    This is usefull if SES isn't fully configured to allow unrestricted sending.
    Supports Regex (e.g. .*@mycompany.com)
* fallback_email - (optional) If set, any emails blocked because it is not in the permitted_emails list will be sent to this address instead.

#### API Manager Instances
The apimInstances section contains settings for particular apim installs.   When a request comes in the instance is selected by looking for it's name
in the callback url.  It is an error is no instance name can be found in the callback url. 

Each instance is configured with the following settings:

* name - the string to identify in the callback url.  Usually the host name.
* username - the username to use when approving or rejecting on the APIM
* password - the password to use when approving or rejecting on the APIM

Additionally any of the global settings can also be set on an instance, overriding the global setting when processing requests matching that instance.

#### Templates
The templates section defines what the emails and web page should look like.  They are velocity templates and the following variables are avialable:

* request - The subscription request including the details sent by the server. Some noteable elements are:
  * apiName
  * apiName
  * apiContext
  * apiProvider
  * apiVersion
  * apiTechnicalOwnerEmail
  * apiTechnicalOwnerName
  * apiBusinessOwnerEmail
  * apiBusinessOwnerName
  * applicationName - The application that will be using this subscription.
  * subscriberId - The ID of the user making the request.
  * subscriberClaims - The claims (user details) of the subscriber (e.g. ).  These will vary based on your configuration.
  * tier
  * workflowReference
  * callbackUrl - The url of the api manager's workflow callback service.
  * status - the status of the request: "Waiting for Approval", "ACCEPTED" or "REJECTED"
  * approver - the user who made the approve/reject decision
* approveurl - The url to open in a browser if you want to approve the request.
* rejecturl - The url to open in a browser if you want to reject the request.
* json - The request object as a json string
* properties - a map of the properties defined in the config file.  Includes global and instance properties.

Each email template should have a subject and a html or text body (or both).

See the default config file for more information.

#### Configuration on S3
You can specify an evironment variable (or generate it in the cloudformation template) where the functions should look for this file.
If you specify this variable and there isn't a config file already there, the default one will be copied to that s3 location.

You can get the current config from s3 via

    aws s3 cp s3://BUCKET/PATH/config.yaml config.yaml

After modifications you can update the copy on the server with the reverse operation

    aws s3 cp config.yaml s3://BUCKET/PATH/config.yaml

The lambda functions cache the configuration from S3.  It can take up to 5 min for the lambda start using the new config file.

###Testing and Debugging

#### Email Simulation
This lambda will accept a query parameter `simulate=True` to enable running the lambda but not actually sending the emails. All other
logic is implemented as expected.

#### Testing
The /test directory contains a set of unit tests for the lambda. The lambda will accept an alternate configuration
if it is specified as a `test-config` entry in the event dictionary passed into the handle_lambda function.

#### Debug Logging
This lambda will accept a query parameter `debug=True` to turn on debug level logging into either the local or CloudWatch logs.
