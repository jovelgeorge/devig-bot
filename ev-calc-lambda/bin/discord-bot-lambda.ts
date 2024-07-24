#!/usr/bin/env node
import 'source-map-support/register';
import * as cdk from 'aws-cdk-lib';
import { DiscordBotLambdaStack } from '../lib/discord-bot-lambda-stack';

const app = new cdk.App();
new DiscordBotLambdaStack(app, 'DiscordBotLambdaStack', {
  env: { 
    account: process.env.CDK_DEFAULT_ACCOUNT, 
    region: process.env.CDK_DEFAULT_REGION 
  },
});