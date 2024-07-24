import * as cdk from 'aws-cdk-lib';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as apigateway from 'aws-cdk-lib/aws-apigateway';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import { Construct } from 'constructs';

export class DiscordBotLambdaStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // Create DynamoDB table
    const table = new dynamodb.Table(this, 'UserDataTable', {
      partitionKey: { name: 'user_id', type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
    });

    // Create Lambda function
    const botFunction = new lambda.DockerImageFunction(this, 'DiscordBotFunction', {
      code: lambda.DockerImageCode.fromImageAsset('./src/app'),
      memorySize: 256,
      timeout: cdk.Duration.seconds(30),
      environment: {
        DISCORD_PUBLIC_KEY: process.env.DISCORD_PUBLIC_KEY || '',
        DYNAMODB_TABLE: table.tableName,
      },
    });

    // Grant Lambda function read/write permissions to DynamoDB table
    table.grantReadWriteData(botFunction);

    // Create API Gateway
    const api = new apigateway.LambdaRestApi(this, 'DiscordBotApi', {
      handler: botFunction,
      proxy: false,
    });

    const interactions = api.root.addResource('interactions');
    interactions.addMethod('POST');
  }
}