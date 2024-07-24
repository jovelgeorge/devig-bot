import os
import boto3
from botocore.exceptions import ClientError

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(os.environ['DYNAMODB_TABLE'])

def get_user_data(user_id: str) -> dict:
    try:
        response = table.get_item(Key={'user_id': user_id})
    except ClientError as e:
        print(e.response['Error']['Message'])
        return {}
    else:
        return response.get('Item', {})

def save_user_data(user_id: str, data: dict):
    try:
        table.put_item(Item={'user_id': user_id, **data})
    except ClientError as e:
        print(e.response['Error']['Message'])