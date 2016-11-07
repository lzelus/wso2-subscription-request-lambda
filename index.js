/*
 *    Copyright 2016 Brigham Young University
 *
 *    Licensed under the Apache License, Version 2.0 (the "License");
 *    you may not use this file except in compliance with the License.
 *    You may obtain a copy of the License at
 *
 *        http://www.apache.org/licenses/LICENSE-2.0
 *
 *    Unless required by applicable law or agreed to in writing, software
 *    distributed under the License is distributed on an "AS IS" BASIS,
 *    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 *    See the License for the specific language governing permissions and
 *    limitations under the License.
 *
 */

/**
 * Created by bdm4 on 9/22/16.
 */

'use strict';

console.log('Loading function');

var AWS = require("aws-sdk");

var docClient = new AWS.DynamoDB.DocumentClient();

exports.handler = function(event, context, callback) {

console.log('retrieving request:', event.params.path.workflowReference);

var table = "WSO2SubscriptionRequest";

const workflowReference = event.params.path.workflowReference;

const params = {
    "TableName": table,
    "Key":{
        "workflowReference": workflowReference
    }
};

var requestGetPromise = docClient.get(params).promise();

requestGetPromise.then(function(data) {
  if (data.Item) {
  console.log('Success');
    callback(null, {
        statusCode: '200',
        body: { 'SubscriptionRequest': data.Item},
        headers: {
            'Content-Type': 'application/json',
        },
    });
  }
  else {
    console.log('Not found');
    callback(JSON.stringify({
        statusCode: '404',
        body: { "message":"SubscriptionRequest not found"},
        headers: {
            'Content-Type': 'application/json',
        },
    }));
  }
}).catch(function(err) {
  console.log(err);
  callback(JSON.stringify({
        statusCode: '500',
        body: err,
        headers: {
            'Content-Type': 'application/json',
        },
    }));
});
};
