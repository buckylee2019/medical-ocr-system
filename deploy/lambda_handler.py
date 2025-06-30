import json
import base64
from app import app
from werkzeug.serving import WSGIRequestHandler

def lambda_handler(event, context):
    """
    AWS Lambda handler for Flask application
    """
    try:
        # Handle API Gateway event
        if 'httpMethod' in event:
            # Convert API Gateway event to WSGI environ
            environ = {
                'REQUEST_METHOD': event['httpMethod'],
                'PATH_INFO': event['path'],
                'QUERY_STRING': event.get('queryStringParameters', ''),
                'CONTENT_TYPE': event.get('headers', {}).get('content-type', ''),
                'CONTENT_LENGTH': str(len(event.get('body', ''))),
                'HTTP_HOST': event.get('headers', {}).get('host', ''),
                'wsgi.input': event.get('body', ''),
                'wsgi.url_scheme': 'https',
            }
            
            # Add headers
            for key, value in event.get('headers', {}).items():
                key = 'HTTP_' + key.upper().replace('-', '_')
                environ[key] = value
            
            # Handle binary content
            if event.get('isBase64Encoded', False):
                environ['wsgi.input'] = base64.b64decode(event['body'])
            
            # Create response
            response_data = []
            
            def start_response(status, headers):
                response_data.append(status)
                response_data.append(headers)
            
            # Call Flask app
            result = app(environ, start_response)
            
            # Format response for API Gateway
            response_body = b''.join(result).decode('utf-8')
            
            return {
                'statusCode': int(response_data[0].split()[0]),
                'headers': dict(response_data[1]),
                'body': response_body,
                'isBase64Encoded': False
            }
            
    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
