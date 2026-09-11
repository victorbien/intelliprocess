import os
import boto3
from botocore.exceptions import ClientError

def get_s3_client():
    # Automatically picks up local credentials from 'aws configure' or SAM environment
    return boto3.client('s3', region_name='ap-southeast-2')

def test_bucket_connection():
    # Use environment variable, fallback to hardcoded name for local script testing
    bucket_name = os.environ.get('DOCUMENT_BUCKET', 'intelliprocess-ai-documents')
    s3_client = get_s3_client()
    
    try:
        # Test connection by listing the first 1 object (checks permission & existence)
        s3_client.list_objects_v2(Bucket=bucket_name, MaxKeys=1)
        print(f" Successfully connected to S3 bucket: {bucket_name}")
        return True
    except ClientError as e:
        print(f"❌ Connection failed: {e.response['Error']['Message']}")
        return False

if __name__ == "__main__":
    test_bucket_connection()