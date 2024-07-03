import base64
import requests
import ujson
import io


class Szurubooru:
    def __init__(self, endpoint_url='https://thisfoxgirldoesnotexist.com', credentials=None):
        self.endpoint_url = endpoint_url
        self.auth_data = base64.b64encode(
            f'{credentials[0]}:{credentials[1]}'.encode('UTF-8')
        ).decode('ASCII') if credentials else None

    def post_request(self, method, **data):
        response = requests.post(
            f'{self.endpoint_url}/{method}',
            headers={
                'Authorization': f'Token {self.auth_data}',
                'Accept': 'application/json'
            },
            **data
        )
        response_data = response.json()

        if response.status_code != 200:
            raise SzurubooruError(response_data)

        return response_data

    def upload(self, content, **metadata):
        return self.post_request(
            'api/posts',
            files={
                'metadata': (None, ujson.dumps(metadata)),
                'content': ('image.jpeg', io.BytesIO(content))
            }
        )

    def comment(self, text, post_id):
        return self.post_request(
            'api/comments',
            json={
                'text': text,
                'postId': post_id
            }
        )

    def delete_post(self, post_id, version=1):
        return self.post_request(
            f'api/post/{post_id}',
            json={'version': version},
            method='delete'
        )

    def list_posts(self, offset, limit, query):
        response = requests.get(
            f'{self.endpoint_url}/api/posts/?offset={offset}&limit={limit}&query={query}',
            headers={
                'Authorization': f'Token {self.auth_data}',
                'Accept': 'application/json'
            }
        )
        data = response.json()

        if response.status_code != 200:
            raise SzurubooruError(data)

        return data

    def feature(self, post_id):
        return self.post_request(
            'api/featured-post',
            json={'id': post_id}
        )


class SzurubooruError(Exception):
    def __init__(self, message):
        super().__init__(message)
